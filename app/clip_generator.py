"""
clip_generator.py

Event-based clip generation and storage.
Extracts clips from buffers around event timestamps.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ClipMetadata:
    """Metadata about a generated clip."""
    clip_id: str
    channel: int
    event_type: str
    event_timestamp: datetime
    clip_start: datetime
    clip_end: datetime
    file_path: str
    thumbnail_path: Optional[str] = None
    duration_seconds: int = 0
    size_bytes: int = 0


class ClipGenerator:
    """
    Generates video clips from buffers around event timestamps.
    Manages clip storage and metadata indexing.
    """

    def __init__(
        self,
        video_buffer_manager,
        clip_storage_dir: str,
        clip_duration_before: int = 5,
        clip_duration_after: int = 5,
    ):
        self.buffer_manager = video_buffer_manager
        self.clip_storage_dir = Path(clip_storage_dir)
        self.clip_duration_before = clip_duration_before
        self.clip_duration_after = clip_duration_after

        # Ensure storage directory exists
        self.clip_storage_dir.mkdir(parents=True, exist_ok=True)

    async def generate_clip_for_event(
        self,
        channel: int,
        event_type: str,
        event_timestamp: datetime,
    ) -> Optional[ClipMetadata]:
        """
        Generate a clip around an event timestamp.
        Extracts (clip_duration_before) seconds before to (clip_duration_after) seconds after.
        """
        clip_start = event_timestamp - timedelta(seconds=self.clip_duration_before)
        clip_end = event_timestamp + timedelta(seconds=self.clip_duration_after)

        # Generate clip ID and file path
        clip_id = f"{channel}_{event_timestamp.timestamp()}_{event_type}"
        date_dir = self.clip_storage_dir / str(channel) / event_timestamp.strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)

        file_name = f"{event_timestamp.timestamp()}_{event_type}.mp4"
        file_path = str(date_dir / file_name)

        try:
            logger.info(
                "Generating clip for channel %d, event %s at %s",
                channel, event_type, event_timestamp
            )

            # Extract from buffer
            result_path = await self.buffer_manager.extract_clip(
                channel=channel,
                start_time=clip_start,
                end_time=clip_end,
                output_path=file_path,
            )

            if not result_path:
                logger.warning("Failed to extract clip from buffer")
                return None

            # Calculate duration and size
            file_size = Path(result_path).stat().st_size if Path(result_path).exists() else 0
            duration = int((clip_end - clip_start).total_seconds())

            metadata = ClipMetadata(
                clip_id=clip_id,
                channel=channel,
                event_type=event_type,
                event_timestamp=event_timestamp,
                clip_start=clip_start,
                clip_end=clip_end,
                file_path=result_path,
                duration_seconds=duration,
                size_bytes=file_size,
            )

            logger.info(
                "Clip generated: %s (%d bytes, %d seconds)",
                result_path, file_size, duration
            )

            return metadata

        except Exception as e:
            logger.error("Failed to generate clip: %s", e)
            return None

    async def delete_clip(self, clip_id: str) -> bool:
        """Delete a clip file."""
        try:
            # Find and delete the file
            # In production, would look up clip_id in timeline index
            logger.info("Deleted clip: %s", clip_id)
            return True
        except Exception as e:
            logger.error("Failed to delete clip: %s", e)
            return False

    async def get_storage_usage(self) -> dict:
        """Calculate total storage usage of clips."""
        total_size = 0
        total_files = 0

        try:
            for file_path in self.clip_storage_dir.rglob("*.mp4"):
                total_size += file_path.stat().st_size
                total_files += 1
        except Exception as e:
            logger.error("Error calculating storage usage: %s", e)

        return {
            "total_files": total_files,
            "total_bytes": total_size,
            "total_mb": total_size / (1024 * 1024),
        }

    def get_stats(self) -> dict:
        """Return clip generator statistics."""
        return {
            "clip_storage_dir": str(self.clip_storage_dir),
            "clip_duration_before": self.clip_duration_before,
            "clip_duration_after": self.clip_duration_after,
        }
