"""
video_buffer.py

Rolling RTSP buffer for continuous video capture.
Maintains circular buffers per channel for event-based clip extraction.
"""

import asyncio
import logging
from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class BufferFrame:
    """Single frame in the buffer."""
    timestamp: datetime
    data: bytes
    is_keyframe: bool = False


class CircularVideoBuffer:
    """
    Maintains a rolling buffer of video frames for a single channel.
    Automatically discards old frames when buffer reaches max size.
    """

    def __init__(
        self,
        channel: int,
        buffer_size_seconds: int = 60,
        frame_rate: int = 15,
    ):
        self.channel = channel
        self.buffer_size_seconds = buffer_size_seconds
        self.frame_rate = frame_rate
        self.max_frames = buffer_size_seconds * frame_rate

        # Use deque for efficient circular buffer
        self.frames: deque = deque(maxlen=self.max_frames)
        self._lock = asyncio.Lock()
        self.last_frame_time: Optional[datetime] = None

    async def add_frame(self, frame: BufferFrame):
        """Add a frame to the buffer."""
        async with self._lock:
            self.frames.append(frame)
            self.last_frame_time = frame.timestamp

    async def get_frames_since(self, since: datetime) -> list[BufferFrame]:
        """Retrieve all frames since a given timestamp."""
        async with self._lock:
            return [f for f in self.frames if f.timestamp >= since]

    async def get_buffered_duration(self) -> float:
        """Return duration of buffered video in seconds."""
        async with self._lock:
            if len(self.frames) < 2:
                return 0
            first = self.frames[0].timestamp
            last = self.frames[-1].timestamp
            return (last - first).total_seconds()

    async def clear(self):
        """Clear all frames from buffer."""
        async with self._lock:
            self.frames.clear()
            self.last_frame_time = None

    def get_stats(self) -> dict:
        """Return buffer statistics."""
        return {
            "channel": self.channel,
            "frames": len(self.frames),
            "max_frames": self.max_frames,
            "buffer_size_seconds": self.buffer_size_seconds,
            "last_frame_time": self.last_frame_time.isoformat() if self.last_frame_time else None,
        }


class VideoBufferManager:
    """
    Manages circular buffers for all channels.
    Coordinates frame ingestion and extraction.
    """

    def __init__(self, nvr_client, buffer_size_seconds: int = 60):
        self.nvr_client = nvr_client
        self.buffer_size_seconds = buffer_size_seconds
        self.buffers: dict[int, CircularVideoBuffer] = {}
        self._running = False
        self._capture_tasks: dict[int, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Initialize buffers for all channels."""
        if not self.nvr_client.is_connected:
            raise RuntimeError("NVR not connected")

        channels = await self.nvr_client.get_channels()
        async with self._lock:
            for channel_info in channels:
                channel = channel_info["channel"]
                self.buffers[channel] = CircularVideoBuffer(
                    channel=channel,
                    buffer_size_seconds=self.buffer_size_seconds,
                )
            logger.info("Initialized %d video buffers", len(self.buffers))

    async def start(self):
        """Start capturing video for all channels."""
        if self._running:
            logger.warning("Buffer manager already running")
            return

        await self.initialize()
        self._running = True

        async with self._lock:
            for channel, buffer in self.buffers.items():
                # In production, these would be real RTSP capture tasks
                # For now, they're placeholders
                task = asyncio.create_task(self._capture_channel(channel))
                self._capture_tasks[channel] = task

        logger.info("Video buffer manager started")

    async def stop(self):
        """Stop capturing and cleanup."""
        self._running = False

        async with self._lock:
            for task in self._capture_tasks.values():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._capture_tasks.clear()
        logger.info("Video buffer manager stopped")

    async def _capture_channel(self, channel: int):
        """
        Capture video for a channel.
        This is a placeholder; real implementation would stream RTSP.
        """
        rtsp_url = await self.nvr_client.get_rtsp_url(channel, stream="sub")
        if not rtsp_url:
            logger.error("Failed to get RTSP URL for channel %d", channel)
            return

        logger.debug("Starting capture for channel %d from %s", channel, rtsp_url)

        # Placeholder: In production, integrate with ffmpeg/opencv to capture RTSP
        # This would decode the stream and add frames to the buffer
        while self._running:
            try:
                await asyncio.sleep(1)
                # Simulate frame capture
                if channel in self.buffers:
                    # Real implementation would add actual frames here
                    pass
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error capturing channel %d: %s", channel, e)
                await asyncio.sleep(5)

    async def extract_clip(
        self,
        channel: int,
        start_time: datetime,
        end_time: datetime,
        output_path: str,
    ) -> Optional[str]:
        """
        Extract a clip from the buffer.
        In production, this would encode buffered frames into an MP4.
        """
        if channel not in self.buffers:
            logger.error("Channel %d not in buffers", channel)
            return None

        buffer = self.buffers[channel]
        frames = await buffer.get_frames_since(start_time)

        if not frames:
            logger.warning(
                "No frames found in buffer for channel %d between %s and %s",
                channel, start_time, end_time
            )
            return None

        logger.info(
            "Extracting %d frames from buffer for channel %d",
            len(frames), channel
        )

        # Placeholder: Real implementation would use ffmpeg or similar to encode
        # For now, just return the output path as if successful
        return output_path

    def get_stats(self) -> dict:
        """Return statistics for all buffers."""
        return {
            "running": self._running,
            "buffers": {
                ch: buf.get_stats()
                for ch, buf in self.buffers.items()
            },
        }
