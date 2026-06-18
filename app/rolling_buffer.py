"""
rolling_buffer.py

Continuous RTSP segment recorder used to build pre-roll event clips.
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SEGMENT_NAME_RE = re.compile(r"^(?P<stamp>\d{8}T\d{6})_(?P<index>\d+)?\.ts$")


@dataclass
class SegmentFile:
    path: Path
    start_time: datetime


class RollingSegmentBuffer:
    def __init__(
        self,
        nvr_client,
        channel: int,
        storage_dir: str,
        segment_seconds: int = 2,
        retention_seconds: int = 90,
        ffmpeg_bin: str = "ffmpeg",
        stream: str = "sub",
    ):
        self.nvr_client = nvr_client
        self.channel = channel
        self.storage_dir = Path(storage_dir)
        self.segment_seconds = max(1, segment_seconds)
        self.retention_seconds = max(retention_seconds, self.segment_seconds * 2)
        self.ffmpeg_bin = ffmpeg_bin
        self.stream = stream

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._rtsp_url: Optional[str] = None

    async def start(self):
        if self._running:
            return
        self._rtsp_url = await self._resolve_rtsp_url()
        if not self._rtsp_url:
            raise RuntimeError(f"No RTSP source available for channel {self.channel}")
        self._running = True
        self._task = asyncio.create_task(self._record_loop())
        logger.info("Rolling buffer started for channel %d", self.channel)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Rolling buffer stopped for channel %d", self.channel)

    async def _record_loop(self):
        assert self._rtsp_url
        while self._running:
            cmd = [
                self.ffmpeg_bin,
                "-hide_banner",
                "-loglevel",
                "info",
                "-rtsp_transport",
                "tcp",
                "-fflags",
                "+genpts",
                "-i",
                self._rtsp_url,
                "-an",
                "-map",
                "0:v:0",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-tune",
                "zerolatency",
                "-pix_fmt",
                "yuv420p",
                "-g",
                str(max(self.segment_seconds * 2, 10)),
                "-keyint_min",
                str(max(self.segment_seconds * 2, 10)),
                "-sc_threshold",
                "0",
                "-f",
                "segment",
                "-segment_time",
                str(self.segment_seconds),
                "-reset_timestamps",
                "1",
                "-segment_format",
                "mpegts",
                "-strftime",
                "1",
                str(self.storage_dir / "%Y%m%dT%H%M%S.ts"),
            ]
            logger.info("Starting rolling recorder for channel %d", self.channel)
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                stderr_task = asyncio.create_task(self._drain_stderr(proc.stderr))
                await proc.wait()
                stderr_task.cancel()
                try:
                    await stderr_task
                except asyncio.CancelledError:
                    pass
                if self._running:
                    logger.warning("Rolling recorder exited for channel %d with return code %s", self.channel, proc.returncode)
                    await asyncio.sleep(2)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("Rolling recorder error for channel %d: %s", self.channel, e)
                await asyncio.sleep(2)

    async def _drain_stderr(self, stream) -> None:
        if stream is None:
            return
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode("utf-8", "ignore").rstrip()
            if text:
                logger.info("Rolling recorder ffmpeg[%d]: %s", self.channel, text)

    async def _resolve_rtsp_url(self) -> Optional[str]:
        if hasattr(self.nvr_client, "get_rtsp_url"):
            return await self.nvr_client.get_rtsp_url(self.channel, stream=self.stream)
        if hasattr(self.nvr_client, "get_rtsp_stream_source"):
            return await self.nvr_client.get_rtsp_stream_source(self.channel, stream=self.stream)
        if hasattr(self.nvr_client, "rtsp"):
            return self.nvr_client.rtsp(self.channel, self.stream)
        return None

    def _load_segments(self) -> list[SegmentFile]:
        segments: list[SegmentFile] = []
        for file_path in sorted(self.storage_dir.glob("*.ts")):
            match = SEGMENT_NAME_RE.match(file_path.name)
            if not match:
                continue
            try:
                start_time = datetime.strptime(match.group("stamp"), "%Y%m%dT%H%M%S")
            except ValueError:
                continue
            segments.append(SegmentFile(path=file_path, start_time=start_time))
        return segments

    def _prune_old_segments(self) -> None:
        cutoff = datetime.now() - timedelta(seconds=self.retention_seconds)
        for file_path in self.storage_dir.glob("*.ts"):
            try:
                match = SEGMENT_NAME_RE.match(file_path.name)
                if match:
                    start_time = datetime.strptime(match.group("stamp"), "%Y%m%dT%H%M%S")
                    if start_time < cutoff:
                        file_path.unlink(missing_ok=True)
                        continue
                if datetime.fromtimestamp(file_path.stat().st_mtime) < cutoff:
                    file_path.unlink(missing_ok=True)
            except Exception:
                continue

    @staticmethod
    def _normalize_window_time(value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value.astimezone().replace(tzinfo=None)
        return value

    async def build_clip(self, start_time: datetime, end_time: datetime, output_path: str) -> Optional[str]:
        if end_time <= start_time:
            return None

        start_time = self._normalize_window_time(start_time)
        end_time = self._normalize_window_time(end_time)

        self._prune_old_segments()
        segments = self._load_segments()
        if not segments:
            logger.debug(
                "Rolling buffer has no segments for channel %d while building window %s -> %s",
                self.channel,
                start_time.isoformat(),
                end_time.isoformat(),
            )
            return None

        selected = []
        for segment in segments:
            segment_end = segment.start_time + timedelta(seconds=self.segment_seconds)
            if segment.start_time <= end_time and segment_end >= start_time:
                selected.append(segment.path)

        if not selected:
            logger.debug(
                "Rolling buffer found %d segments but none overlapped window %s -> %s for channel %d; first=%s last=%s",
                len(segments),
                start_time.isoformat(),
                end_time.isoformat(),
                self.channel,
                segments[0].start_time.isoformat() if segments else "none",
                segments[-1].start_time.isoformat() if segments else "none",
            )
            return None

        logger.debug(
            "Rolling buffer selected %d/%d segments for channel %d window %s -> %s",
            len(selected),
            len(segments),
            self.channel,
            start_time.isoformat(),
            end_time.isoformat(),
        )

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        concat_list = out_path.with_suffix(".concat.txt")

        try:
            concat_list.write_text(
                "".join(f"file '{path.as_posix()}'\n" for path in selected),
                encoding="utf-8",
            )

            cmd = [
                self.ffmpeg_bin,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(out_path),
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError((stderr or b"").decode("utf-8", "ignore").strip() or f"ffmpeg exited with {proc.returncode}")

            if not out_path.exists() or out_path.stat().st_size == 0:
                raise RuntimeError("ffmpeg completed without producing output")

            return str(out_path)
        finally:
            concat_list.unlink(missing_ok=True)

    def get_stats(self) -> dict:
        segments = self._load_segments()
        return {
            "running": self._running,
            "channel": self.channel,
            "storage_dir": str(self.storage_dir),
            "segment_seconds": self.segment_seconds,
            "retention_seconds": self.retention_seconds,
            "segments": len(segments),
            "oldest_segment": segments[0].start_time.isoformat() if segments else None,
            "newest_segment": segments[-1].start_time.isoformat() if segments else None,
        }
