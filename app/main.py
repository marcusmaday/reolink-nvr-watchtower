"""
Reolink NVR Home Assistant Enhanced API - FastAPI Backend

Complete REST + WebSocket API for Reolink NVR integration with Home Assistant.
Features:
  - Recording search and filtering
  - Event timeline indexing
  - Video clip generation
  - Real-time event streaming (WebSocket)
  - Storage management
"""

import os
import html
import logging
import asyncio
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Any
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Query, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse, RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from reolink_aio.api import Host
from reolink_aio.exceptions import ReolinkError

# Import our custom modules
from config import get_config, AppConfig
from nvr_client import NVRClient
from event_stream import EventStream, Event, EventType
from video_buffer import VideoBufferManager
from clip_generator import ClipGenerator, ClipMetadata
from timeline_index import TimelineIndex, TimelineEntry
from storage_manager import StorageManager
from rolling_buffer import RollingSegmentBuffer
from reolink_search import search_recordings, get_channels_info, EVENT_TYPE_MAP

logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG", "false").lower() == "true" else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

APP_CONFIG: AppConfig = get_config()
if APP_CONFIG.api.debug:
    logging.getLogger().setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)

# ─── Config (from env / HA add-on options) ────────────────────────────────────
NVR_HOST = APP_CONFIG.nvr.host
NVR_PORT = APP_CONFIG.nvr.port
NVR_USERNAME = APP_CONFIG.nvr.username
NVR_PASSWORD = APP_CONFIG.nvr.password
NVR_SSL = APP_CONFIG.nvr.use_https
DEBUG = APP_CONFIG.api.debug
API_PORT = APP_CONFIG.api.port
API_HOST = APP_CONFIG.api.host
ALLOW_CORS = APP_CONFIG.api.allow_cors
LOCAL_CLIP_ENABLED = APP_CONFIG.video_buffer.enabled
CLIP_QUALITY = APP_CONFIG.video_buffer.clip_quality.lower()
LOCAL_CLIP_SECONDS = max(
    APP_CONFIG.video_buffer.clip_duration_before + APP_CONFIG.video_buffer.clip_duration_after,
    int(os.getenv("LOCAL_CLIP_SECONDS", "12")),
    1,
)
BUFFER_RETENTION_SECONDS = max(
    APP_CONFIG.video_buffer.buffer_size_seconds,
    LOCAL_CLIP_SECONDS + 20,
)
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
ROLLING_BUFFER_CHANNEL = int(os.getenv("ROLLING_BUFFER_CHANNEL", "8"))
ROLLING_SEGMENT_SECONDS = int(os.getenv("ROLLING_SEGMENT_SECONDS", "2"))
CLIP_DURATION_BEFORE = max(APP_CONFIG.video_buffer.clip_duration_before, 10)
CLIP_DURATION_AFTER = max(APP_CONFIG.video_buffer.clip_duration_after, 5)
CLIPS_DIRECTORY = Path(APP_CONFIG.storage.clips_directory)
INDEX_FILE = APP_CONFIG.storage.index_file
RETENTION_DAYS = APP_CONFIG.storage.retention_days
MAX_STORAGE_MB = APP_CONFIG.storage.max_storage_mb
EXTERNAL_STORAGE_PATH = APP_CONFIG.storage.external_storage_path

# Global NVR host instance
nvr_host: Optional[Host] = None
timeline_index: Optional[TimelineIndex] = None
ui_clients: list[WebSocket] = []
clip_tasks: set[asyncio.Task] = set()
rolling_buffer: Optional[RollingSegmentBuffer] = None
storage_manager: Optional[StorageManager] = None


# ─── Pydantic models ──────────────────────────────────────────────────────────

class Clip(BaseModel):
    timestamp:        str
    end_timestamp:    str
    duration_seconds: int
    event_type:       str
    trigger:          str
    file_name:        str
    stream_url:       Optional[str] = None
    download_url:     Optional[str] = None


class SearchResponse(BaseModel):
    channel:     int
    start_date:  str
    end_date:    str
    event_type:  Optional[str]
    clips:       List[Clip]
    total_clips: int


class ChannelInfo(BaseModel):
    channel: int
    name:    str
    enabled: bool
    model:   Optional[str] = None


class DeviceInfo(BaseModel):
    model:            str
    firmware_version: str
    nvr_name:         str
    mac_address:      str
    is_nvr:           bool
    num_channels:     int


class HealthCheck(BaseModel):
    status:        str
    nvr_connected: bool
    nvr_host:      str


class EventIngestRequest(BaseModel):
    event_type: str
    channel: int
    timestamp: Optional[str] = None
    event_id: Optional[str] = None
    source: str = "home_assistant"
    title: Optional[str] = None
    message: Optional[str] = None
    camera_name: Optional[str] = None
    snapshot_url: Optional[str] = None
    clip_url: Optional[str] = None
    stream_url: Optional[str] = None
    download_url: Optional[str] = None
    live_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecentEvent(BaseModel):
    entry_id: str
    timestamp: str
    channel: int
    event_type: str
    clip_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    clip_status: Optional[str] = None
    title: Optional[str] = None
    message: Optional[str] = None
    camera_name: Optional[str] = None
    source: Optional[str] = None
    duration_seconds: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ─── Lifespan (startup / shutdown) ───────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global nvr_host, timeline_index, rolling_buffer, storage_manager

    logger.info("Starting Reolink NVR HA App...")
    logger.info("Connecting to NVR at %s:%s", NVR_HOST, NVR_PORT)

    try:
        nvr_host = Host(
            host=NVR_HOST,
            port=NVR_PORT,
            username=NVR_USERNAME,
            password=NVR_PASSWORD,
            use_https=NVR_SSL,
        )
        await nvr_host.get_host_data()
        logger.info("Connected to NVR: %s (%s channels)", nvr_host.nvr_name, nvr_host.num_channels)
    except ReolinkError as e:
        logger.error("Failed to connect to NVR: %s", e)
        nvr_host = None
    except Exception as e:
        logger.error("Unexpected error during startup: %s", e)
        nvr_host = None

    timeline_index = TimelineIndex(index_file=INDEX_FILE)
    logger.info("Timeline index initialized at %s", INDEX_FILE)

    storage_manager = StorageManager(
        clips_directory=str(CLIPS_DIRECTORY),
        timeline_index=timeline_index,
        retention_days=RETENTION_DAYS,
        max_storage_mb=MAX_STORAGE_MB,
        external_storage_path=EXTERNAL_STORAGE_PATH,
    )
    try:
        await storage_manager.start()
    except Exception as e:
        logger.error("Failed to start storage manager: %s", e)
        storage_manager = None

    if LOCAL_CLIP_ENABLED and nvr_host:
        try:
            rolling_buffer = RollingSegmentBuffer(
                nvr_client=nvr_host,
                channel=ROLLING_BUFFER_CHANNEL,
                storage_dir=str(CLIPS_DIRECTORY / "rolling_buffer" / f"channel_{ROLLING_BUFFER_CHANNEL}"),
                segment_seconds=ROLLING_SEGMENT_SECONDS,
                retention_seconds=BUFFER_RETENTION_SECONDS,
                ffmpeg_bin=FFMPEG_BIN,
                stream=_preferred_stream(),
            )
            await rolling_buffer.start()
        except Exception as e:
            logger.error("Failed to start rolling buffer: %s", e)
            rolling_buffer = None

    yield  # ← app runs here

    logger.info("Shutting down Reolink NVR HA App...")
    if rolling_buffer:
        try:
            await rolling_buffer.stop()
        except Exception as e:
            logger.error("Error stopping rolling buffer: %s", e)
    if storage_manager:
        try:
            await storage_manager.stop()
        except Exception as e:
            logger.error("Error stopping storage manager: %s", e)
    if nvr_host:
        try:
            await nvr_host.logout()
        except Exception as e:
            logger.error("Error during logout: %s", e)

# ─── App init ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Reolink NVR HA App",
    description="REST API wrapper for Reolink NVR recording search and filtering",
    version="0.4.16",
    lifespan=lifespan,
)

if ALLOW_CORS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ─── Helper ───────────────────────────────────────────────────────────────────

def _require_nvr():
    if not nvr_host:
        raise HTTPException(status_code=503, detail="NVR not connected. Check add-on logs.")


def _preferred_stream() -> str:
    return "main" if CLIP_QUALITY == "high" else "sub"


def _normalize_event_type(event_type: Optional[str]) -> Optional[str]:
    if event_type is None:
        return None
    normalized = event_type.strip().upper()
    return normalized if normalized in EVENT_TYPE_MAP else None


def _normalize_datetime_for_compare(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _timeline_entry_to_recent(entry: TimelineEntry) -> dict[str, Any]:
    metadata = entry.metadata or {}
    clip_source = entry.clip_path or metadata.get("clip_url") or metadata.get("download_url") or metadata.get("stream_url")
    live_source = metadata.get("live_url")
    clip_url = f"api/events/{entry.entry_id}/clip" if clip_source else None
    live_url = f"api/events/{entry.entry_id}/live" if live_source else None
    thumbnail_url = entry.thumbnail_path or metadata.get("thumbnail_url") or metadata.get("snapshot_url")
    return {
        "entry_id": entry.entry_id,
        "timestamp": entry.timestamp.isoformat(),
        "channel": entry.channel,
        "event_type": entry.event_type,
        "clip_url": clip_url,
        "raw_clip_url": clip_source,
        "live_url": live_url,
        "raw_live_url": live_source,
        "thumbnail_url": thumbnail_url,
        "clip_status": metadata.get("clip_status"),
        "title": metadata.get("title"),
        "message": metadata.get("message"),
        "camera_name": metadata.get("camera_name"),
        "source": metadata.get("source"),
        "duration_seconds": metadata.get("duration_seconds"),
        "metadata": metadata,
    }


def _parse_onvif_event_notifications(data: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(data)
    except Exception as e:
        logger.debug("Failed to parse ONVIF webhook payload: %s", e)
        return []

    namespace_wsn = "{http://docs.oasis-open.org/wsn/b-2}"
    namespace_schema = "{http://www.onvif.org/ver10/schema}"

    parsed: list[dict[str, Any]] = []
    for message in root.iter(f"{namespace_wsn}NotificationMessage"):
        topic_element = message.find(f"{namespace_wsn}Topic[@Dialect='http://www.onvif.org/ver10/tev/topicExpression/ConcreteSet']")
        if topic_element is None or not topic_element.text:
            continue

        rule = Path(topic_element.text).name
        if rule not in {"Motion", "MotionAlarm", "FaceDetect", "PeopleDetect", "VehicleDetect", "DogCatDetect", "Package", "Visitor"}:
            continue

        channel = None
        source_element = message.find(f".//{namespace_schema}SimpleItem[@Name='Source']")
        if source_element is None:
            source_element = message.find(f".//{namespace_schema}SimpleItem[@Name='VideoSourceConfigurationToken']")
        if source_element is not None and "Value" in source_element.attrib:
            try:
                channel = int(source_element.attrib["Value"])
            except ValueError:
                channel = None

        if channel is None:
            continue

        if rule in {"PeopleDetect", "FaceDetect", "DogCatDetect", "Package"}:
            event_type = "PERSON"
        elif rule == "Visitor":
            event_type = "DOORBELL"
        elif rule in {"Motion", "MotionAlarm"}:
            event_type = "MOTION"
        elif rule == "VehicleDetect":
            event_type = "VEHICLE"
        else:
            event_type = None

        if event_type is None:
            continue

        parsed.append({
            "channel": channel,
            "event_type": event_type,
            "rule": rule,
        })

    return parsed


def _create_event_entry(
    *,
    channel: int,
    event_type: str,
    timestamp: Optional[datetime] = None,
    camera_name: Optional[str] = None,
    source: str = "nvr_webhook",
    title: Optional[str] = None,
    message: Optional[str] = None,
    snapshot_url: Optional[str] = None,
    live_url: Optional[str] = None,
) -> TimelineEntry:
    event_timestamp = timestamp or datetime.now()
    entry = TimelineEntry(
        entry_id=f"{channel}_{event_timestamp.isoformat()}_{event_type}",
        timestamp=event_timestamp,
        channel=channel,
        event_type=event_type,
        clip_path=None,
        thumbnail_path=snapshot_url,
        metadata={
            "title": title or f"{event_type.title()} detected",
            "message": message or f"{event_type.title()} detected on channel {channel}",
            "camera_name": camera_name,
            "source": source,
            "snapshot_url": snapshot_url,
            "live_url": live_url,
            "clip_status": "pending",
            "clip_source": "local_rtsp",
        },
    )
    timeline_index.upsert_entry(entry)
    return entry


async def _broadcast_recent_event(entry: TimelineEntry):
    if not ui_clients:
        return

    payload = {
        "type": "event",
        "event": _timeline_entry_to_recent(entry),
    }

    alive_clients: list[WebSocket] = []
    for socket in list(ui_clients):
        try:
            await socket.send_json(payload)
            alive_clients.append(socket)
        except Exception:
            continue

    ui_clients[:] = alive_clients


async def _resolve_clip_for_event(
    channel: int,
    event_type: str,
    timestamp: datetime,
    stream: str = "sub",
    lookback_seconds: int = 90,
    lookahead_seconds: int = 180,
    retries: int = 2,
    retry_delay_seconds: float = 2.0,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    if not nvr_host:
        return None, None, None

    target_ts = timestamp

    async def _search_once() -> list[dict]:
        start_dt = target_ts - timedelta(seconds=lookback_seconds)
        end_dt = target_ts + timedelta(seconds=lookahead_seconds)
        return await search_recordings(
            host=nvr_host,
            channel=channel,
            start_dt=start_dt,
            end_dt=end_dt,
            event_type=event_type,
            stream=stream,
        )

    clips: list[dict] = []
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            clips = await _search_once()
            if clips:
                break
        except Exception as e:
            last_error = e
            logger.debug("Unable to resolve clip for event (attempt %d/%d): %s", attempt + 1, retries + 1, e)

        if attempt < retries:
            await asyncio.sleep(retry_delay_seconds)

    if not clips:
        if last_error:
            logger.debug("Unable to resolve clip for event after retries: %s", last_error)
        return None, None, None

    def _distance_seconds(clip: dict[str, Any]) -> float:
        try:
            clip_ts = _normalize_datetime_for_compare(datetime.fromisoformat(clip["timestamp"]))
        except Exception:
            return float("inf")
        return abs((_normalize_datetime_for_compare(clip_ts) - _normalize_datetime_for_compare(target_ts)).total_seconds())

    best_clip = min(clips, key=_distance_seconds)
    return (
        best_clip.get("download_url") or best_clip.get("stream_url"),
        best_clip.get("stream_url"),
        best_clip.get("download_url"),
    )


async def _hydrate_event_clip(entry: TimelineEntry) -> Optional[TimelineEntry]:
    metadata = entry.metadata or {}
    if metadata.get("clip_status") in {"pending", "generating", "failed"} and not entry.clip_path:
        return entry

    if entry.clip_path or (entry.metadata or {}).get("clip_url") or (entry.metadata or {}).get("download_url") or (entry.metadata or {}).get("stream_url"):
        return entry

    try:
        resolved_clip, resolved_stream, resolved_download = await _resolve_clip_for_event(
            channel=entry.channel,
            event_type=entry.event_type,
            timestamp=entry.timestamp,
        )
    except Exception as e:
        logger.debug("On-demand clip resolution failed for %s: %s", entry.entry_id, e)
        return entry

    if not (resolved_clip or resolved_stream or resolved_download):
        return entry

    updated_metadata = dict(entry.metadata or {})
    if resolved_stream:
        updated_metadata.setdefault("stream_url", resolved_stream)
    if resolved_download:
        updated_metadata.setdefault("download_url", resolved_download)

    updated_entry = TimelineEntry(
        entry_id=entry.entry_id,
        timestamp=entry.timestamp,
        channel=entry.channel,
        event_type=entry.event_type,
        clip_path=resolved_clip or resolved_download or resolved_stream,
        thumbnail_path=entry.thumbnail_path,
        metadata=updated_metadata,
    )
    timeline_index.upsert_entry(updated_entry)
    return updated_entry


def _event_clip_storage_path(channel: int, timestamp: datetime, event_type: str) -> Path:
    base_dir = CLIPS_DIRECTORY / "event_clips"
    day_dir = base_dir / f"channel_{channel}" / timestamp.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    clip_name = f"{timestamp.strftime('%Y%m%dT%H%M%S')}_{event_type.lower()}.mp4"
    return day_dir / clip_name


async def _generate_buffered_event_clip(entry: TimelineEntry) -> None:
    if not rolling_buffer:
        logger.debug("Rolling buffer unavailable for %s", entry.entry_id)
        return

    clip_path = _event_clip_storage_path(entry.channel, entry.timestamp, entry.event_type)
    clip_start = entry.timestamp - timedelta(seconds=max(CLIP_DURATION_BEFORE, 1))
    clip_end = entry.timestamp + timedelta(seconds=max(CLIP_DURATION_AFTER, 1))
    logger.debug(
        "Buffered clip window for %s: event=%s start=%s end=%s before=%ss after=%ss",
        entry.entry_id,
        entry.timestamp.isoformat(),
        clip_start.isoformat(),
        clip_end.isoformat(),
        CLIP_DURATION_BEFORE,
        CLIP_DURATION_AFTER,
    )
    try:
        logger.debug("Rolling buffer stats before clip for %s: %s", entry.entry_id, rolling_buffer.get_stats())
    except Exception:
        pass

    generating_metadata = dict(entry.metadata or {})
    generating_metadata["clip_status"] = "generating"
    generating_metadata["clip_source"] = "rolling_rtsp"
    generating_entry = TimelineEntry(
        entry_id=entry.entry_id,
        timestamp=entry.timestamp,
        channel=entry.channel,
        event_type=entry.event_type,
        clip_path=entry.clip_path,
        thumbnail_path=entry.thumbnail_path,
        metadata=generating_metadata,
    )
    timeline_index.upsert_entry(generating_entry)
    await _broadcast_recent_event(generating_entry)

    try:
        result_path = await rolling_buffer.build_clip(clip_start, clip_end, str(clip_path))
        if not result_path:
            raise RuntimeError("No buffered segments were available for the requested window")

        ready_metadata = dict(entry.metadata or {})
        ready_metadata["clip_status"] = "ready"
        ready_metadata["clip_source"] = "rolling_rtsp"
        ready_metadata["clip_file"] = result_path
        ready_metadata["duration_seconds"] = max(int((clip_end - clip_start).total_seconds()), 1)
        ready_entry = TimelineEntry(
            entry_id=entry.entry_id,
            timestamp=entry.timestamp,
            channel=entry.channel,
            event_type=entry.event_type,
            clip_path=result_path,
            thumbnail_path=entry.thumbnail_path,
            metadata=ready_metadata,
        )
        timeline_index.upsert_entry(ready_entry)
        await _broadcast_recent_event(ready_entry)
        logger.info("Buffered clip generated for %s: %s", entry.entry_id, result_path)
    except Exception as e:
        failed_metadata = dict(entry.metadata or {})
        failed_metadata["clip_status"] = "failed"
        failed_metadata["clip_source"] = "rolling_rtsp"
        failed_metadata["clip_error"] = str(e)
        failed_entry = TimelineEntry(
            entry_id=entry.entry_id,
            timestamp=entry.timestamp,
            channel=entry.channel,
            event_type=entry.event_type,
            clip_path=entry.clip_path,
            thumbnail_path=entry.thumbnail_path,
            metadata=failed_metadata,
        )
        timeline_index.upsert_entry(failed_entry)
        await _broadcast_recent_event(failed_entry)
        logger.error("Failed to generate buffered clip for %s: %s", entry.entry_id, e)

        # Fall back to a direct RTSP capture so a clip still exists while the
        # ring buffer warms up or if segment stitching misses the event window.
        await _capture_direct_event_clip(entry, clip_path)


async def _capture_direct_event_clip(entry: TimelineEntry, clip_path: Path) -> None:
    if not nvr_host:
        return

    try:
        rtsp_url = await nvr_host.get_rtsp_stream_source(entry.channel, stream=_preferred_stream())
    except Exception as e:
        logger.error("Direct RTSP fallback failed for %s: %s", entry.entry_id, e)
        return

    if not rtsp_url:
        logger.error("Direct RTSP fallback has no stream for %s", entry.entry_id)
        return

    clip_seconds = max(LOCAL_CLIP_SECONDS, 1)
    try:
        if clip_path.exists():
            clip_path.unlink()

        cmd = [
            FFMPEG_BIN,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-rtsp_transport",
            "tcp",
            "-i",
            rtsp_url,
            "-t",
            str(clip_seconds),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "28",
            "-pix_fmt",
            "yuv420p",
            "-an",
            "-movflags",
            "+faststart",
            str(clip_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError((stderr or b"").decode("utf-8", "ignore").strip() or f"ffmpeg exited with {proc.returncode}")
        if not clip_path.exists() or clip_path.stat().st_size == 0:
            raise RuntimeError("ffmpeg completed but clip file was not created")

        ready_metadata = dict(entry.metadata or {})
        ready_metadata["clip_status"] = "ready"
        ready_metadata["clip_source"] = "direct_rtsp"
        ready_metadata["clip_file"] = str(clip_path)
        ready_metadata["duration_seconds"] = clip_seconds
        ready_entry = TimelineEntry(
            entry_id=entry.entry_id,
            timestamp=entry.timestamp,
            channel=entry.channel,
            event_type=entry.event_type,
            clip_path=str(clip_path),
            thumbnail_path=entry.thumbnail_path,
            metadata=ready_metadata,
        )
        timeline_index.upsert_entry(ready_entry)
        await _broadcast_recent_event(ready_entry)
        logger.info("Direct RTSP fallback clip generated for %s: %s", entry.entry_id, clip_path)
    except Exception as e:
        logger.error("Direct RTSP fallback failed for %s: %s", entry.entry_id, e)


def _schedule_clip_generation(entry: TimelineEntry) -> None:
    if not LOCAL_CLIP_ENABLED:
        return

    if not rolling_buffer:
        logger.warning("Rolling buffer is not available; cannot generate pre-roll clip for %s", entry.entry_id)
        return

    task = asyncio.create_task(_generate_buffered_event_clip(entry))
    clip_tasks.add(task)

    def _done_callback(t: asyncio.Task) -> None:
        clip_tasks.discard(t)

    task.add_done_callback(_done_callback)


def _is_http_url(value: Optional[str]) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https")


def _entry_media_source(entry: TimelineEntry, kind: str) -> Optional[str]:
    metadata = entry.metadata or {}
    if kind == "clip":
        return (
            entry.clip_path
            or metadata.get("clip_url")
            or metadata.get("download_url")
            or metadata.get("stream_url")
        )
    if kind == "live":
        return metadata.get("live_url") or metadata.get("stream_url") or entry.clip_path
    return None


async def _proxy_http_media(url: str):
    import aiohttp

    timeout = aiohttp.ClientTimeout(total=120, connect=15, sock_connect=15, sock_read=120)
    last_error: Optional[Exception] = None

    for attempt in range(3):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as upstream:
                    if upstream.status >= 400:
                        text = await upstream.text()
                        raise HTTPException(
                            status_code=upstream.status,
                            detail=text[:500] or f"Upstream media request failed: {upstream.status}",
                        )

                    content_type = upstream.headers.get("Content-Type", "application/octet-stream")

                    async def body_iter():
                        async for chunk in upstream.content.iter_chunked(64 * 1024):
                            yield chunk

                    return StreamingResponse(body_iter(), media_type=content_type)
        except aiohttp.ServerDisconnectedError as e:
            last_error = e
            logger.warning("Upstream media server disconnected on attempt %d/3: %s", attempt + 1, e)
        except aiohttp.ClientError as e:
            last_error = e
            logger.warning("Upstream media request failed on attempt %d/3: %s", attempt + 1, e)

    raise HTTPException(status_code=502, detail=f"Unable to fetch media from source: {last_error}")


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/", summary="API root")
async def root(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept or "application/xhtml+xml" in accept:
        return HTMLResponse(_dashboard_html())
    return {
        "name": "Reolink NVR HA App",
        "version": "0.4.16",
        "status": "running",
        "docs": "/docs",
        "health": "/api/health",
        "app": "/app",
    }


@app.get("/api/health", response_model=HealthCheck, summary="Health check")
async def health_check():
    return HealthCheck(
        status="ok" if nvr_host else "error",
        nvr_connected=nvr_host is not None,
        nvr_host=NVR_HOST,
    )


@app.get("/api/device/info", response_model=DeviceInfo, summary="NVR device information")
async def get_device_info():
    _require_nvr()
    try:
        return DeviceInfo(
            model=nvr_host.model or "Unknown",
            firmware_version=nvr_host.sw_version or "Unknown",
            nvr_name=nvr_host.nvr_name or "Unknown",
            mac_address=nvr_host.mac_address or "Unknown",
            is_nvr=nvr_host.is_nvr,
            num_channels=nvr_host.num_channels,
        )
    except Exception as e:
        logger.error("Error getting device info: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/channels", response_model=List[ChannelInfo], summary="List all camera channels")
async def get_channels():
    _require_nvr()
    try:
        channels = await get_channels_info(nvr_host)
        return [ChannelInfo(**ch) for ch in channels]
    except Exception as e:
        logger.error("Error getting channels: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search", response_model=SearchResponse, summary="Search recordings by date and event type")
async def search(
    channel: int = Query(..., description="Camera channel number (0-based)"),
    start_date: str = Query(..., description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD (defaults to start_date)"),
    event_type: Optional[str] = Query(
        None,
        description=f"Filter by event type: {', '.join(EVENT_TYPE_MAP.keys())}",
    ),
    stream: str = Query("sub", description="Stream quality: 'sub' (default) or 'main'"),
):
    """
    Search NVR recordings by date range and optional event type.

    Returns a list of clips with timestamps, duration, and stream URLs.

    Event types:
    - **DOORBELL** — Doorbell button press (visitor)
    - **PERSON**   — Person / human detection
    - **MOTION**   — Motion detection (all motion)
    - **ANIMAL**   — Animal / pet detection
    - **VEHICLE**  — Vehicle detection
    - *(omit for all recordings)*
    """
    _require_nvr()

    # Validate channel
    if channel < 0 or channel >= nvr_host.num_channels:
        raise HTTPException(
            status_code=400,
            detail=f"Channel {channel} out of range. NVR has {nvr_host.num_channels} channels (0-based).",
        )

    # Validate dates
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt   = datetime.strptime(end_date or start_date, "%Y-%m-%d")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start_date must be ≤ end_date")

    # Validate event type
    if event_type:
        event_type_upper = event_type.upper()
        if event_type_upper not in EVENT_TYPE_MAP:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid event_type '{event_type}'. Must be one of: {', '.join(EVENT_TYPE_MAP.keys())}",
            )
        event_type = event_type_upper

    # Validate stream
    if stream not in ("sub", "main"):
        raise HTTPException(status_code=400, detail="stream must be 'sub' or 'main'")

    logger.info(
        "Search: channel=%s, start=%s, end=%s, event_type=%s, stream=%s",
        channel, start_date, end_date or start_date, event_type, stream,
    )

    try:
        raw_clips = await search_recordings(
            host=nvr_host,
            channel=channel,
            start_dt=start_dt,
            end_dt=end_dt,
            event_type=event_type,
            stream=stream,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ReolinkError as e:
        logger.error("Reolink API error during search: %s", e)
        raise HTTPException(status_code=502, detail=f"NVR API error: {e}")
    except Exception as e:
        logger.exception("Unexpected error during search")
        raise HTTPException(status_code=500, detail=str(e))

    clips = [Clip(**c) for c in raw_clips]

    for clip in clips:
        if _normalize_event_type(clip.event_type) is None:
            continue

        entry_id = f"{channel}_{clip.timestamp}_{clip.event_type}"
        entry = TimelineEntry(
            entry_id=entry_id,
            timestamp=datetime.fromisoformat(clip.timestamp),
            channel=channel,
            event_type=clip.event_type,
            clip_path=clip.download_url or clip.stream_url,
            thumbnail_path=None,
            metadata={
                "title": f"{clip.event_type.title()} event",
                "message": f"{clip.event_type.title()} detected on channel {channel}",
                "end_timestamp": clip.end_timestamp,
                "duration_seconds": clip.duration_seconds,
                "trigger": clip.trigger,
                "file_name": clip.file_name,
                "stream_url": clip.stream_url,
                "download_url": clip.download_url,
                "source": "search",
            },
        )
        timeline_index.upsert_entry(entry)
        await _broadcast_recent_event(entry)

    return SearchResponse(
        channel=channel,
        start_date=start_date,
        end_date=end_date or start_date,
        event_type=event_type,
        clips=clips,
        total_clips=len(clips),
    )

@app.get("/api/timeline", summary="Get event timeline")
async def get_timeline(
    hours: int = Query(24, description="How many hours back to query"),
    channel: Optional[int] = Query(None, description="Filter by channel"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(100, description="Maximum number of entries to return"),
):
    if event_type is not None and _normalize_event_type(event_type) is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event_type '{event_type}'. Must be one of: {', '.join(EVENT_TYPE_MAP.keys())}",
        )
    entries = timeline_index.get_entries(
        channel=channel,
        event_type=_normalize_event_type(event_type),
        since=datetime.now() - __import__('datetime').timedelta(hours=hours),
        limit=limit,
    )
    return {
        "hours": hours,
        "channel": channel,
        "event_type": event_type,
        "total": len(entries),
        "entries": [e.to_dict() for e in entries],
    }


@app.get("/api/events/recent", summary="Get recent player-ready events")
@app.get("/app/api/events/recent", include_in_schema=False)
async def get_recent_events(
    limit: int = Query(20, description="Maximum number of events to return"),
    channel: Optional[int] = Query(None, description="Filter by channel"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
):
    normalized_event_type = _normalize_event_type(event_type)
    if event_type is not None and normalized_event_type is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event_type '{event_type}'. Must be one of: {', '.join(EVENT_TYPE_MAP.keys())}",
        )
    entries = timeline_index.get_entries(
        channel=channel,
        event_type=normalized_event_type,
        limit=limit,
    )
    return {
        "limit": limit,
        "channel": channel,
        "event_type": normalized_event_type,
        "total": len(entries),
        "events": [_timeline_entry_to_recent(entry) for entry in entries],
    }


@app.post("/api/events/ingest", summary="Ingest a live event from Home Assistant or another source")
@app.post("/app/api/events/ingest", include_in_schema=False)
async def ingest_event(payload: EventIngestRequest):
    _require_nvr()

    event_type = _normalize_event_type(payload.event_type)
    if event_type is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event_type '{payload.event_type}'. Must be one of: {', '.join(EVENT_TYPE_MAP.keys())}",
        )

    if payload.channel < 0 or payload.channel >= nvr_host.num_channels:
        raise HTTPException(
            status_code=400,
            detail=f"Channel {payload.channel} out of range. NVR has {nvr_host.num_channels} channels (0-based).",
        )

    try:
        event_timestamp = datetime.fromisoformat(payload.timestamp) if payload.timestamp else datetime.now()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid timestamp: {e}")

    clip_url = payload.clip_url or payload.download_url or payload.stream_url
    stream_url = payload.stream_url
    download_url = payload.download_url
    clip_status = "ready" if clip_url else "pending"
    clip_source = "provided" if clip_url else "local_rtsp"

    entry = TimelineEntry(
        entry_id=payload.event_id or f"{payload.channel}_{event_timestamp.isoformat()}_{event_type}",
        timestamp=event_timestamp,
        channel=payload.channel,
        event_type=event_type,
        clip_path=clip_url,
        thumbnail_path=payload.snapshot_url,
        metadata={
            **payload.metadata,
            "title": payload.title or f"{event_type.title()} detected",
            "message": payload.message or f"{event_type.title()} detected on channel {payload.channel}",
            "camera_name": payload.camera_name,
            "source": payload.source,
            "snapshot_url": payload.snapshot_url,
            "stream_url": stream_url or payload.stream_url,
            "download_url": download_url or payload.download_url,
            "live_url": payload.live_url,
            "duration_seconds": payload.duration_seconds,
            "clip_status": clip_status,
            "clip_source": clip_source,
        },
    )
    timeline_index.upsert_entry(entry)
    await _broadcast_recent_event(entry)

    if not clip_url:
        _schedule_clip_generation(entry)

    return {
        "status": "accepted",
        "event": _timeline_entry_to_recent(entry),
    }


@app.post("/api/webhook/reolink", summary="Receive a Reolink ONVIF webhook event")
@app.post("/app/api/webhook/reolink", include_in_schema=False)
async def receive_reolink_webhook(request: Request):
    _require_nvr()
    body = (await request.body()).decode("utf-8", errors="ignore")
    if not body.strip():
        raise HTTPException(status_code=400, detail="Empty webhook payload")

    try:
        event_channels = await nvr_host.ONVIF_event_callback(body)
    except Exception as e:
        logger.error("Failed to process ONVIF webhook payload: %s", e)
        raise HTTPException(status_code=400, detail=f"Invalid ONVIF payload: {e}")

    parsed_events = _parse_onvif_event_notifications(body)
    if not parsed_events:
        return {"status": "ignored", "detail": "No supported event types found"}

    created: list[dict[str, Any]] = []
    for parsed in parsed_events:
        if event_channels and parsed["channel"] not in event_channels:
            continue
        camera_name = None
        try:
            camera_name = nvr_host.camera_name(parsed["channel"])
        except Exception:
            camera_name = None
        entry = _create_event_entry(
            channel=parsed["channel"],
            event_type=parsed["event_type"],
            camera_name=camera_name,
            source="nvr_webhook",
            title=f"{parsed['event_type'].title()} detected",
            message=f"{parsed['event_type'].title()} detected on channel {parsed['channel']}",
        )
        await _broadcast_recent_event(entry)
        _schedule_clip_generation(entry)
        created.append(_timeline_entry_to_recent(entry))

    if not created:
        return {"status": "ignored", "detail": "No matching channels found"}

    return {"status": "accepted", "events": created}


@app.get("/api/timeline/{entry_id}", summary="Get a single timeline entry")
@app.get("/app/api/timeline/{entry_id}", include_in_schema=False)
async def get_timeline_entry(entry_id: str):
    entry = timeline_index.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Timeline entry '{entry_id}' not found")
    return _timeline_entry_to_recent(entry)


@app.get("/api/events/{entry_id}/clip", summary="Get playable clip for a timeline event")
@app.get("/app/api/events/{entry_id}/clip", include_in_schema=False)
async def get_event_clip(entry_id: str):
    entry = timeline_index.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Timeline entry '{entry_id}' not found")

    entry = await _hydrate_event_clip(entry)

    source = _entry_media_source(entry, "clip")
    if not source:
        raise HTTPException(status_code=404, detail="No clip source stored for this event")

    if _is_http_url(source):
        return await _proxy_http_media(source)

    source_path = Path(source)
    if source_path.exists() and source_path.is_file():
        return FileResponse(source_path)

    raise HTTPException(
        status_code=422,
        detail=f"Clip source is not browser-playable: {source}",
    )


@app.get("/api/events/{entry_id}/live", summary="Open a live view for a timeline event")
@app.get("/app/api/events/{entry_id}/live", include_in_schema=False)
async def get_event_live(entry_id: str):
    entry = timeline_index.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Timeline entry '{entry_id}' not found")

    source = _entry_media_source(entry, "live")
    if not source:
        raise HTTPException(status_code=404, detail="No live source stored for this event")

    if source.startswith("/"):
        return RedirectResponse(source)

    if _is_http_url(source):
        return RedirectResponse(source)

    raise HTTPException(
        status_code=422,
        detail=f"Live source is not browser-playable: {source}",
    )


async def _live_mjpeg_stream(channel: int, stream: str = "sub"):
    if not nvr_host:
        raise HTTPException(status_code=503, detail="NVR not connected")

    try:
        rtsp_url = await nvr_host.get_rtsp_stream_source(channel, stream=stream)
    except Exception as e:
        logger.error("Failed to resolve live RTSP source for channel %s: %s", channel, e)
        raise HTTPException(status_code=502, detail=f"Failed to resolve live stream: {e}")

    if not rtsp_url:
        raise HTTPException(status_code=404, detail=f"No live stream available for channel {channel}")

    async def frame_generator():
        import asyncio

        proc = await asyncio.create_subprocess_exec(
            FFMPEG_BIN,
            "-hide_banner",
            "-loglevel",
            "error",
            "-rtsp_transport",
            "tcp",
            "-i",
            rtsp_url,
            "-an",
            "-vf",
            "scale=-2:720",
            "-r",
            "8",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "pipe:1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        buffer = bytearray()
        try:
            while True:
                chunk = await proc.stdout.read(64 * 1024)
                if not chunk:
                    break
                buffer.extend(chunk)
                while True:
                    start = buffer.find(b"\xff\xd8")
                    end = buffer.find(b"\xff\xd9", start + 2 if start != -1 else 0)
                    if start == -1 or end == -1 or end <= start:
                        break
                    frame = bytes(buffer[start:end + 2])
                    del buffer[:end + 2]
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        + f"Content-Length: {len(frame)}\r\n\r\n".encode()
                        + frame
                        + b"\r\n"
                    )
        finally:
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except Exception:
                    proc.kill()
                    await proc.wait()

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/live/{channel}/mjpeg", summary="Live MJPEG stream for a camera channel")
@app.get("/app/api/live/{channel}/mjpeg", include_in_schema=False)
async def get_live_mjpeg(channel: int, stream: str = Query("sub", description="Stream quality: 'sub' or 'main'")):
    if channel < 0 or channel >= (nvr_host.num_channels if nvr_host else 0):
        raise HTTPException(status_code=400, detail="Invalid channel")
    if stream not in ("sub", "main"):
        raise HTTPException(status_code=400, detail="stream must be 'sub' or 'main'")
    return await _live_mjpeg_stream(channel, stream=stream)


def _live_dashboard_html(channel: int = 8, event_type: Optional[str] = None) -> str:
    event_label = html.escape(event_type) if event_type else "Live"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Reolink Live</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0f1115;
      --panel: #171b22;
      --line: #263041;
      --text: #e6edf3;
      --muted: #9aa7b7;
      --accent: #5aa9ff;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ height: 100%; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      padding: 0.75rem;
    }}
    .topbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      padding: 0.75rem 0;
    }}
    .title {{
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
      min-width: 0;
    }}
    .title strong {{
      font-size: 1.1rem;
      line-height: 1.2;
    }}
    .title span {{
      color: var(--muted);
      font-size: 0.92rem;
    }}
    .chip {{
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 0.4rem 0.7rem;
      color: var(--text);
      text-decoration: none;
      background: rgba(255,255,255,0.03);
      white-space: nowrap;
    }}
    .viewer {{
      flex: 1;
      min-height: 0;
      border: 1px solid var(--line);
      border-radius: 0.75rem;
      overflow: hidden;
      background: #000;
    }}
    .viewer img {{
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
    }}
    .meta {{
      display: grid;
      gap: 0.35rem;
      color: var(--muted);
      font-size: 0.95rem;
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
    }}
  </style>
</head>
<body>
  <main>
    <div class="topbar">
      <div class="title">
        <strong>Front Door Live</strong>
        <span>{event_label} view • Channel {channel}</span>
      </div>
      <a class="chip" href="..">Back to events</a>
    </div>
    <div class="viewer">
      <img src="api/live/{channel}/mjpeg" alt="Live stream for channel {channel}">
    </div>
    <div class="meta">
      <div>Live stream is served inside the app.</div>
      <div>If the stream is unavailable, reload after a few seconds.</div>
    </div>
    <div class="actions">
      <a class="chip" href="..">Events</a>
      <a class="chip" href="api/live/{channel}/mjpeg?stream=main" target="_blank" rel="noreferrer">Open main stream</a>
    </div>
  </main>
</body>
</html>"""


@app.get("/app/live", response_class=HTMLResponse, summary="Open the live camera page")
@app.get("/app/live/", response_class=HTMLResponse, include_in_schema=False)
async def app_live(channel: int = Query(ROLLING_BUFFER_CHANNEL, description="Camera channel number"), event_type: Optional[str] = Query(None)):
    if channel < 0 or (nvr_host and channel >= nvr_host.num_channels):
        raise HTTPException(status_code=400, detail="Invalid channel")
    return HTMLResponse(_live_dashboard_html(channel=channel, event_type=event_type))


def _dashboard_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Reolink Enhanced API</title>
    <style>
    :root {
      color-scheme: dark;
      --bg: #0f1115;
      --panel: #171b22;
      --line: #263041;
      --text: #e6edf3;
      --muted: #9aa7b7;
      --accent: #5aa9ff;
      --warn: #ffcb6b;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    header {
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap: 12px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      background: rgba(15,17,21,.96);
      position: sticky;
      top: 0;
      z-index: 5;
    }
    header h1 { margin: 0; font-size: 18px; line-height: 1.2; }
    header .meta { color: var(--muted); font-size: 13px; line-height: 1.3; }
    main {
      display: grid;
      grid-template-columns: minmax(320px, 360px) minmax(0, 1fr);
      height: calc(100vh - 65px);
      overflow: hidden;
    }
    aside {
      border-right: 1px solid var(--line);
      background: var(--panel);
      overflow: auto;
      -webkit-overflow-scrolling: touch;
      min-height: 0;
    }
    section.player {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      min-height: 0;
      overflow: hidden;
    }
    .toolbar {
      display:flex;
      gap: 8px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      align-items:center;
      flex-wrap: wrap;
    }
    .chip, button {
      border: 1px solid var(--line);
      background: #12161d;
      color: var(--text);
      min-height: 42px;
      padding: 10px 12px;
      border-radius: 10px;
      cursor: pointer;
      font: inherit;
      touch-action: manipulation;
    }
    .chip.active { border-color: var(--accent); color: var(--accent); }
    .events { list-style:none; margin:0; padding:0; }
    .event {
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      cursor: pointer;
      min-height: 64px;
    }
    .event:hover { background: rgba(90,169,255,.08); }
    .event.active { background: rgba(90,169,255,.15); }
    .event .top { display:flex; justify-content:space-between; gap: 12px; font-size: 14px; align-items: flex-start; }
    .event .time { color: var(--muted); font-size: 12px; margin-top: 4px; line-height: 1.3; }
    .badge { font-size: 11px; text-transform: uppercase; letter-spacing: .04em; padding: 3px 7px; border-radius: 999px; background: rgba(90,169,255,.16); color: #d5ebff; white-space: nowrap; }
    .badge.doorbell { background: rgba(255,203,107,.18); color: #ffe4a0; }
    .player-wrap { padding: 16px; display:grid; gap: 14px; min-height: 0; overflow: hidden; }
    video, img.preview {
      width: 100%;
      max-height: 64vh;
      background: #000;
      border: 1px solid var(--line);
      border-radius: 10px;
      object-fit: contain;
    }
    .details {
      display: grid;
      gap: 8px;
      padding: 0 16px 16px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.35;
      overflow: hidden;
    }
    .details strong { color: var(--text); }
    .detail-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 10px;
      align-items: center;
    }
    .detail-pill {
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      padding: 0.3rem 0.55rem;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255,255,255,0.03);
      color: var(--text);
      font-size: 12px;
    }
    .detail-pill.doorbell {
      background: rgba(255,203,107,.18);
      color: #ffe4a0;
    }
    .detail-note {
      color: var(--muted);
      font-size: 13px;
    }
    .empty { padding: 20px; color: var(--muted); }
    .row { display:flex; gap: 8px; flex-wrap: wrap; align-items:center; }
    .muted { color: var(--muted); }
    a.chip { display: inline-flex; align-items: center; text-decoration: none; }
    @media (max-width: 900px) {
      main {
        grid-template-columns: 1fr;
        grid-template-rows: minmax(340px, 58vh) minmax(0, 1fr);
      }
      aside { border-right: 0; border-bottom: 1px solid var(--line); order: 2; }
      section.player { order: 1; }
      header { align-items: flex-start; flex-direction: column; }
      .toolbar { overflow-x: auto; flex-wrap: nowrap; }
      video, img.preview {
        max-height: none;
        height: min(100%, 58vh);
      }
      .player-wrap { padding: 12px; }
      .details { padding: 0 12px 12px; font-size: 13px; }
      .event { padding: 16px; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Reolink Enhanced API</h1>
      <div class="meta">Recent doorbell and person events with player-first playback</div>
    </div>
    <div class="meta" id="status">Connecting…</div>
  </header>
  <main>
    <aside>
      <div class="toolbar">
        <button class="chip active" data-filter="ALL">All</button>
        <button class="chip" data-filter="PERSON">Person</button>
        <button class="chip" data-filter="DOORBELL">Doorbell</button>
      </div>
      <ul id="events" class="events"></ul>
    </aside>
    <section class="player">
      <div class="toolbar">
        <div class="row">
          <button id="refresh">Refresh</button>
          <span class="muted" id="count">0 events</span>
        </div>
      </div>
      <div class="player-wrap">
        <video id="player" controls playsinline preload="metadata"></video>
        <img id="snapshot" class="preview" alt="Event snapshot" hidden>
      </div>
      <div class="details" id="details">
        <div class="empty">No events loaded.</div>
      </div>
    </section>
  </main>
  <script>
    const state = { events: [], filter: 'ALL', selected: null, socket: null };
    const deepLink = new URLSearchParams(window.location.search);
    const requestedEntryId = deepLink.get('event_id') || deepLink.get('entry_id');
    const requestedEventType = (() => {
      const raw = (deepLink.get('event_type') || '').trim().toUpperCase();
      return ['PERSON', 'DOORBELL'].includes(raw) ? raw : null;
    })();
    if (requestedEventType) state.filter = requestedEventType;
    const elEvents = document.getElementById('events');
    const elCount = document.getElementById('count');
    const elStatus = document.getElementById('status');
    const player = document.getElementById('player');
    const snapshot = document.getElementById('snapshot');
    const details = document.getElementById('details');

    function apiUrl(path) {
      return new URL(path, window.location.href).toString();
    }

    function wsUrl(path) {
      const url = new URL(path, window.location.href);
      url.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      return url.toString();
    }

    function badgeClass(eventType) {
      return eventType === 'DOORBELL' ? 'badge doorbell' : 'badge';
    }

    function formatTime(ts) {
      try { return new Date(ts).toLocaleString(); } catch (e) { return ts; }
    }

    function escapeHtml(value) {
      return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }

    function visibleEvents() {
      return state.filter === 'ALL' ? state.events : state.events.filter(e => e.event_type === state.filter);
    }

    function render() {
      const events = visibleEvents();
      elCount.textContent = `${events.length} event${events.length === 1 ? '' : 's'}`;
      elEvents.innerHTML = events.map(e => `
        <li class="event ${state.selected === e.entry_id ? 'active' : ''}" data-id="${escapeHtml(e.entry_id)}">
          <div class="top">
            <strong>${e.title || e.event_type}</strong>
            <span class="${badgeClass(e.event_type)}">${e.event_type}</span>
          </div>
          <div class="time">${formatTime(e.timestamp)}${e.camera_name ? ` • ${e.camera_name}` : ''}</div>
        </li>`).join('') || '<li class="empty">No recent events.</li>';

      if ((!state.selected || !events.find(e => e.entry_id === state.selected)) && events.length) {
        selectEvent(events[0].entry_id, false);
      }
    }

    function setStatus(text) { elStatus.textContent = text; }

    async function loadRecent() {
      const resp = await fetch(apiUrl('api/events/recent?limit=50'));
      const data = await resp.json();
      state.events = data.events || [];
      if (requestedEntryId && state.events.find(e => e.entry_id === requestedEntryId)) {
        state.selected = requestedEntryId;
      } else if (!state.selected && state.events.length) {
        state.selected = state.events[0].entry_id;
      }
      render();
      if (state.selected) selectEvent(state.selected, false);
    }

    function selectEvent(id, userInitiated = true) {
      const entry = state.events.find(e => e.entry_id === id);
      if (!entry) return;
      state.selected = id;
      render();
      const clipUrl = entry.clip_url;
      const snapshotUrl = entry.thumbnail_url || entry.metadata?.snapshot_url;
      if (clipUrl) {
        snapshot.hidden = true;
        player.hidden = false;
        player.poster = snapshotUrl || '';
        player.src = clipUrl;
        if (userInitiated) player.play().catch(() => {});
      } else if (snapshotUrl) {
        player.pause();
        player.removeAttribute('src');
        player.load();
        player.removeAttribute('poster');
        snapshot.src = snapshotUrl;
        snapshot.hidden = false;
        player.hidden = true;
      }
      details.innerHTML = `
        <div class="detail-meta">
          <span class="detail-pill ${entry.event_type === 'DOORBELL' ? 'doorbell' : ''}">${escapeHtml(entry.event_type)}</span>
          <span class="detail-pill">${escapeHtml(formatTime(entry.timestamp))}</span>
          <span class="detail-pill">${escapeHtml(entry.camera_name ? entry.camera_name : `Channel ${entry.channel}`)}</span>
          ${entry.clip_status && entry.clip_status !== 'ready' ? `<span class="detail-pill">${escapeHtml(`Clip ${entry.clip_status}`)}</span>` : ''}
        </div>
        ${entry.message && entry.message !== entry.title ? `<div class="detail-note">${escapeHtml(entry.message)}</div>` : ''}
        <div class="row">
          ${entry.live_url ? `<a class="chip" href="${entry.live_url}" target="_blank" rel="noreferrer">Open live</a>` : ''}
        </div>
      `;
    }

    elEvents.addEventListener('click', (ev) => {
      const li = ev.target.closest('.event');
      if (!li) return;
      selectEvent(li.dataset.id, true);
    });

    document.querySelectorAll('[data-filter]').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('[data-filter]').forEach(el => el.classList.remove('active'));
        btn.classList.add('active');
        state.filter = btn.dataset.filter;
        render();
      });
    });

    document.getElementById('refresh').addEventListener('click', loadRecent);

    function connectSocket() {
      const socket = new WebSocket(wsUrl('ws/events'));
      state.socket = socket;
      socket.onopen = () => setStatus('Live');
      socket.onclose = () => { setStatus('Reconnecting…'); setTimeout(connectSocket, 1500); };
      socket.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'event' && msg.event) {
          state.events = [msg.event, ...state.events.filter(e => e.entry_id !== msg.event.entry_id)];
          state.selected = msg.event.entry_id;
          render();
          selectEvent(msg.event.entry_id, false);
        }
      };
    }

    loadRecent().then(() => {
      connectSocket();
    }).catch(err => {
      setStatus('Offline');
      details.innerHTML = `<div class="empty">Failed to load recent events: ${err}</div>`;
    });
  </script>
</body>
</html>"""


@app.get("/app", response_class=HTMLResponse, summary="Open the event dashboard")
@app.get("/app/", response_class=HTMLResponse, include_in_schema=False)
async def app_dashboard():
    return HTMLResponse(_dashboard_html())


@app.websocket("/ws/events")
@app.websocket("/app/ws/events")
async def ws_events(websocket: WebSocket):
    await websocket.accept()
    ui_clients.append(websocket)
    try:
        await websocket.send_json({
            "type": "hello",
            "events": [_timeline_entry_to_recent(entry) for entry in timeline_index.get_entries(limit=20)],
        })
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in ui_clients:
            ui_clients.remove(websocket)


@app.get("/api/debug/info", summary="Debug info (requires debug=true in config)")
async def debug_info():
    if not DEBUG:
        raise HTTPException(status_code=403, detail="Debug endpoint disabled. Set debug: true in add-on config.")
    return {
        "nvr_host":      NVR_HOST,
        "nvr_port":      NVR_PORT,
        "nvr_ssl":       NVR_SSL,
        "nvr_connected": nvr_host is not None,
        "nvr_info": {
            "model":        nvr_host.model         if nvr_host else None,
            "sw_version":   nvr_host.sw_version    if nvr_host else None,
            "nvr_name":     nvr_host.nvr_name       if nvr_host else None,
            "num_channels": nvr_host.num_channels    if nvr_host else None,
            "is_nvr":       nvr_host.is_nvr         if nvr_host else None,
            "mac_address":  nvr_host.mac_address    if nvr_host else None,
        },
        "supported_event_types": list(EVENT_TYPE_MAP.keys()),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT)
