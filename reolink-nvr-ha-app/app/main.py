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

import logging
import asyncio
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Import our custom modules
from config import get_config, AppConfig
from nvr_client import NVRClient
from event_stream import EventStream, Event, EventType
from video_buffer import VideoBufferManager
from clip_generator import ClipGenerator, ClipMetadata
from timeline_index import TimelineIndex, TimelineEntry
from storage_manager import StorageManager
from reolink_search import search_recordings, get_channels_info, EVENT_TYPE_MAP

# ─── Config (from env / HA add-on options) ────────────────────────────────────
NVR_HOST     = os.getenv("NVR_HOST",     "192.168.1.100")
NVR_PORT     = int(os.getenv("NVR_PORT", "80"))
NVR_USERNAME = os.getenv("NVR_USERNAME", "admin")
NVR_PASSWORD = os.getenv("NVR_PASSWORD", "password")
NVR_SSL      = os.getenv("NVR_SSL",  "false").lower() == "true"
DEBUG        = os.getenv("DEBUG",    "false").lower() == "true"
API_PORT     = int(os.getenv("API_PORT", "5000"))

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Global NVR host instance
nvr_host: Optional[Host] = None


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


# ─── Lifespan (startup / shutdown) ───────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global nvr_host

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
        logger.info("Connected to NVR: %s (%s channels)", nvr_host.nvr_name, nvr_host.num_channel)
    except ReolinkError as e:
        logger.error("Failed to connect to NVR: %s", e)
        nvr_host = None
    except Exception as e:
        logger.error("Unexpected error during startup: %s", e)
        nvr_host = None

    yield  # ← app runs here

    logger.info("Shutting down Reolink NVR HA App...")
    if nvr_host:
        try:
            await nvr_host.logout()
        except Exception as e:
            logger.error("Error during logout: %s", e)


# ─── App init ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Reolink NVR HA App",
    description="REST API wrapper for Reolink NVR recording search and filtering",
    version="0.1.0",
    lifespan=lifespan,
)


# ─── Helper ───────────────────────────────────────────────────────────────────

def _require_nvr():
    if not nvr_host:
        raise HTTPException(status_code=503, detail="NVR not connected. Check add-on logs.")


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/", summary="API root")
async def root():
    return {
        "name":    "Reolink NVR HA App",
        "version": "0.1.0",
        "status":  "running",
        "docs":    "/docs",
        "health":  "/api/health",
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
            num_channels=nvr_host.num_channel,
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
    if channel < 0 or channel >= nvr_host.num_channel:
        raise HTTPException(
            status_code=400,
            detail=f"Channel {channel} out of range. NVR has {nvr_host.num_channel} channels (0-based).",
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

    return SearchResponse(
        channel=channel,
        start_date=start_date,
        end_date=end_date or start_date,
        event_type=event_type,
        clips=clips,
        total_clips=len(clips),
    )


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
            "num_channels": nvr_host.num_channel    if nvr_host else None,
            "is_nvr":       nvr_host.is_nvr         if nvr_host else None,
            "mac_address":  nvr_host.mac_address    if nvr_host else None,
        },
        "supported_event_types": list(EVENT_TYPE_MAP.keys()),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)
