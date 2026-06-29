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
        buffer_retention_seconds: int = 300,
        absolute_buffer_max_age_seconds: int = 300,
    ):
        self.clips_dir = Path(clips_directory)
        self.external_storage = Path(external_storage_path) if external_storage_path else None
        self.timeline_index = timeline_index
        self.retention_days = retention_days
        self.max_storage_mb = max_storage_mb
        self.max_storage_bytes = max_storage_mb * 1024 * 1024
        self.buffer_retention_seconds = max(buffer_retention_seconds, 60)
        self.absolute_buffer_max_age_seconds = max(absolute_buffer_max_age_seconds, 60)

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
            self._maintenance_task.cancel()
            try:
                await self._maintenance_task
            except asyncio.CancelledError:
                pass
        logger.info("Storage manager stopped")

    async def _maintenance_loop(self):
        """Periodic maintenance: enforce retention and storage limits."""
        while self._running:
            try:
                logger.debug("Running storage maintenance")
                await self._enforce_buffer_retention()
                await self._enforce_retention()
                await self._enforce_storage_limit()

                # Run maintenance every hour
                await asyncio.sleep(3600)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in storage maintenance: %s", e)

    async def _enforce_buffer_retention(self):
        """Delete stale rolling-buffer transport stream segments."""
        rolling_root = self.clips_dir / "rolling_buffer"
        if not rolling_root.exists():
            return

        cutoff_seconds = min(self.buffer_retention_seconds, self.absolute_buffer_max_age_seconds)
        cutoff_time = datetime.now() - timedelta(seconds=cutoff_seconds)
        deleted_count = 0
        deleted_bytes = 0

        try:
            for ts_file in rolling_root.rglob("*.ts"):
                try:
                    file_mtime = datetime.fromtimestamp(ts_file.stat().st_mtime)
                    if file_mtime >= cutoff_time:
                        continue
                    file_size = ts_file.stat().st_size
                    ts_file.unlink()
                    deleted_count += 1
                    deleted_bytes += file_size
                except FileNotFoundError:
                    continue

            if deleted_count > 0:
                logger.info(
                    "Deleted %d stale rolling-buffer segments (%.1f MB)",
                    deleted_count,
                    deleted_bytes / (1024 * 1024),
                )
        except Exception as e:
            logger.error("Error enforcing rolling buffer retention: %s", e)

    async def _enforce_retention(self):
        """Delete clips older than retention_days."""
        cutoff_time = datetime.now() - timedelta(days=self.retention_days)
        deleted_count = 0

        try:
            for media_file in self._iter_managed_files(include_ts=False):
                file_mtime = datetime.fromtimestamp(media_file.stat().st_mtime)
                if file_mtime < cutoff_time:
                    logger.debug("Deleting old clip: %s", media_file)
                    media_file.unlink()
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
        for media_file in self._iter_managed_files(include_ts=True):
            mtime = media_file.stat().st_mtime
            size = media_file.stat().st_size
            clips.append((media_file, mtime, size))

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
            for media_file in self._iter_managed_files(include_ts=True):
                total += media_file.stat().st_size
        except Exception as e:
            logger.error("Error calculating storage: %s", e)
        return total

    async def get_storage_info(self) -> dict:
        """Get current storage usage information."""
        total_bytes = self._get_storage_usage()
        total_files = sum(1 for _ in self._iter_managed_files(include_ts=True))

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
            "buffer_retention_seconds": self.buffer_retention_seconds,
            "absolute_buffer_max_age_seconds": self.absolute_buffer_max_age_seconds,
        }

    def _iter_managed_files(self, include_ts: bool) -> list[Path]:
        patterns = ["*.mp4"]
        if include_ts:
            patterns.append("*.ts")

        files: list[Path] = []
        for pattern in patterns:
            files.extend(self.clips_dir.rglob(pattern))
        return files
