"""
storage_manager.py

Manages clip storage, retention policies, and cleanup.
"""

import logging
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class StorageManager:
    """
    Manages video clip storage, enforces retention policies,
    and handles external storage mounting.
    """

    def __init__(
        self,
        clips_directory: str,
        timeline_index,
        retention_days: int = 7,
        max_storage_mb: int = 5000,
        external_storage_path: Optional[str] = None,
    ):
        self.clips_dir = Path(clips_directory)
        self.external_storage = Path(external_storage_path) if external_storage_path else None
        self.timeline_index = timeline_index
        self.retention_days = retention_days
        self.max_storage_mb = max_storage_mb
        self.max_storage_bytes = max_storage_mb * 1024 * 1024

        self._running = False
        self._maintenance_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start storage maintenance background task."""
        if self._running:
            logger.warning("Storage manager already running")
            return

        self._running = True
        self._maintenance_task = asyncio.create_task(self._maintenance_loop())
        logger.info("Storage manager started")

    async def stop(self):
        """Stop storage maintenance."""
        self._running = False
        if self._maintenance_task:
            await self._maintenance_task
        logger.info("Storage manager stopped")

    async def _maintenance_loop(self):
        """Periodic maintenance: enforce retention and storage limits."""
        while self._running:
            try:
                # Run maintenance every hour
                await asyncio.sleep(3600)

                logger.debug("Running storage maintenance")
                await self._enforce_retention()
                await self._enforce_storage_limit()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in storage maintenance: %s", e)

    async def _enforce_retention(self):
        """Delete clips older than retention_days."""
        cutoff_time = datetime.now() - timedelta(days=self.retention_days)
        deleted_count = 0

        try:
            for mp4_file in self.clips_dir.rglob("*.mp4"):
                file_mtime = datetime.fromtimestamp(mp4_file.stat().st_mtime)
                if file_mtime < cutoff_time:
                    logger.debug("Deleting old clip: %s", mp4_file)
                    mp4_file.unlink()
                    deleted_count += 1

            if deleted_count > 0:
                logger.info("Deleted %d old clips (retention: %d days)", deleted_count, self.retention_days)

            # Prune timeline entries
            pruned = self.timeline_index.prune_old_entries(self.retention_days)
            if pruned > 0:
                logger.info("Pruned %d old timeline entries", pruned)

        except Exception as e:
            logger.error("Error enforcing retention: %s", e)

    async def _enforce_storage_limit(self):
        """Delete oldest clips if storage exceeds limit."""
        total_size = self._get_storage_usage()

        if total_size <= self.max_storage_bytes:
            logger.debug(
                "Storage usage OK: %.1f MB / %d MB",
                total_size / (1024 * 1024),
                self.max_storage_mb,
            )
            return

        logger.warning(
            "Storage usage exceeded: %.1f MB / %d MB, deleting old clips",
            total_size / (1024 * 1024),
            self.max_storage_mb,
        )

        # Get list of all clips with modification times
        clips = []
        for mp4_file in self.clips_dir.rglob("*.mp4"):
            mtime = mp4_file.stat().st_mtime
            size = mp4_file.stat().st_size
            clips.append((mp4_file, mtime, size))

        # Sort by modification time (oldest first)
        clips.sort(key=lambda x: x[1])

        # Delete oldest clips until we're under limit
        deleted_size = 0
        for clip_file, _, size in clips:
            if total_size - deleted_size <= self.max_storage_bytes * 0.9:  # Keep at 90% of limit
                break

            logger.info("Deleting clip to free space: %s", clip_file)
            clip_file.unlink()
            deleted_size += size

        logger.info("Freed %.1f MB of storage", deleted_size / (1024 * 1024))

    def _get_storage_usage(self) -> int:
        """Calculate total storage usage in bytes."""
        total = 0
        try:
            for mp4_file in self.clips_dir.rglob("*.mp4"):
                total += mp4_file.stat().st_size
        except Exception as e:
            logger.error("Error calculating storage: %s", e)
        return total

    async def get_storage_info(self) -> dict:
        """Get current storage usage information."""
        total_bytes = self._get_storage_usage()
        total_files = sum(1 for _ in self.clips_dir.rglob("*.mp4"))

        return {
            "total_bytes": total_bytes,
            "total_mb": total_bytes / (1024 * 1024),
            "total_files": total_files,
            "max_mb": self.max_storage_mb,
            "retention_days": self.retention_days,
            "usage_percent": (total_bytes / self.max_storage_bytes * 100) if self.max_storage_bytes else 0,
        }

    def get_stats(self) -> dict:
        """Return storage manager statistics."""
        return {
            "running": self._running,
            "clips_directory": str(self.clips_dir),
            "external_storage": str(self.external_storage) if self.external_storage else None,
            "retention_days": self.retention_days,
            "max_storage_mb": self.max_storage_mb,
        }
