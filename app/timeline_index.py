"""
timeline_index.py

Event timeline indexing and querying.
Maintains searchable metadata about events and clips.
"""

import logging
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class TimelineEntry:
    """Single entry in the timeline."""
    entry_id: str
    timestamp: datetime
    channel: int
    event_type: str
    clip_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    metadata: dict = None

    def to_dict(self) -> dict:
        """Convert to dictionary, ISO-formatting datetime."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


class TimelineIndex:
    """
    Maintains a searchable index of events and clips.
    Stores metadata in JSON for easy querying.
    """

    def __init__(self, index_file: str):
        self.index_file = Path(index_file)
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        self.entries: List[TimelineEntry] = []
        self._lock_enabled = False

        # Load existing index on init
        self._load_index()

    def _load_index(self):
        """Load index from disk."""
        index_path = self.index_file
        if not index_path.exists() and index_path.name == "timeline.json":
            legacy_path = index_path.with_name("reolink_timeline.json")
            if legacy_path.exists():
                logger.info("Legacy timeline index found at %s; loading it instead", legacy_path)
                index_path = legacy_path

        if index_path.exists():
            try:
                with open(index_path, "r") as f:
                    data = json.load(f)
                    for item in data:
                        entry = TimelineEntry(
                            entry_id=item["entry_id"],
                            timestamp=datetime.fromisoformat(item["timestamp"]),
                            channel=item["channel"],
                            event_type=item["event_type"],
                            clip_path=item.get("clip_path"),
                            thumbnail_path=item.get("thumbnail_path"),
                            metadata=item.get("metadata", {}),
                        )
                        self.entries.append(entry)
                logger.info("Loaded %d timeline entries from index", len(self.entries))
            except Exception as e:
                logger.error("Failed to load index: %s", e)

    def _save_index(self):
        """Save index to disk."""
        try:
            with open(self.index_file, "w") as f:
                data = [entry.to_dict() for entry in self.entries]
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Failed to save index: %s", e)

    def add_entry(self, entry: TimelineEntry) -> str:
        """Add a new timeline entry and return the entry ID."""
        # Generate unique entry ID if not provided
        if not entry.entry_id:
            entry.entry_id = f"{entry.channel}_{entry.timestamp.timestamp()}_{entry.event_type}"

        self.entries.append(entry)
        self._save_index()

        logger.debug("Added timeline entry: %s", entry.entry_id)
        return entry.entry_id

    def upsert_entry(self, entry: TimelineEntry) -> str:
        """Insert or replace an entry by ID."""
        if not entry.entry_id:
            entry.entry_id = f"{entry.channel}_{entry.timestamp.timestamp()}_{entry.event_type}"

        for idx, existing in enumerate(self.entries):
            if existing.entry_id == entry.entry_id:
                self.entries[idx] = entry
                self._save_index()
                logger.debug("Updated timeline entry: %s", entry.entry_id)
                return entry.entry_id

        return self.add_entry(entry)

    def get_entry(self, entry_id: str) -> Optional[TimelineEntry]:
        """Return a single entry by ID."""
        for entry in self.entries:
            if entry.entry_id == entry_id:
                return entry
        return None

    def get_entries(
        self,
        channel: Optional[int] = None,
        event_type: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[TimelineEntry]:
        """
        Query timeline entries with optional filters.
        """
        results = self.entries
        since = self._normalize_dt(since)
        until = self._normalize_dt(until)

        if channel is not None:
            results = [e for e in results if e.channel == channel]

        if event_type is not None:
            results = [e for e in results if e.event_type.lower() == event_type.lower()]

        if since is not None:
            results = [
                e for e in results
                if (normalized := self._normalize_dt(e.timestamp)) is not None and normalized >= since
            ]

        if until is not None:
            results = [
                e for e in results
                if (normalized := self._normalize_dt(e.timestamp)) is not None and normalized <= until
            ]

        # Sort by timestamp descending (newest first)
        results.sort(
            key=lambda e: self._normalize_dt(e.timestamp) or datetime.min,
            reverse=True,
        )

        return results[:limit]

    def get_entries_for_channel(
        self,
        channel: int,
        hours: int = 24,
        limit: int = 100,
    ) -> List[TimelineEntry]:
        """Get recent entries for a specific channel."""
        since = datetime.now() - timedelta(hours=hours)
        return self.get_entries(channel=channel, since=since, limit=limit)

    def delete_entry(self, entry_id: str) -> bool:
        """Delete a timeline entry by ID."""
        original_count = len(self.entries)
        self.entries = [e for e in self.entries if e.entry_id != entry_id]

        if len(self.entries) < original_count:
            self._save_index()
            logger.debug("Deleted timeline entry: %s", entry_id)
            return True

        return False

    def prune_old_entries(self, max_age_days: int) -> int:
        """
        Delete entries older than max_age_days.
        Returns number of entries deleted.
        """
        cutoff = self._normalize_dt(datetime.now() - timedelta(days=max_age_days))
        original_count = len(self.entries)
        self.entries = [
            e for e in self.entries
            if (normalized := self._normalize_dt(e.timestamp)) is not None and normalized > cutoff
        ]

        deleted_count = original_count - len(self.entries)
        if deleted_count > 0:
            self._save_index()
            logger.info("Pruned %d old timeline entries", deleted_count)

        return deleted_count

    def get_stats(self) -> dict:
        """Return timeline statistics."""
        by_event_type = {}
        by_channel = {}

        for entry in self.entries:
            by_event_type[entry.event_type] = by_event_type.get(entry.event_type, 0) + 1
            by_channel[entry.channel] = by_channel.get(entry.channel, 0) + 1

        return {
            "total_entries": len(self.entries),
            "by_event_type": by_event_type,
            "by_channel": by_channel,
            "index_file": str(self.index_file),
        }

    @staticmethod
    def _normalize_dt(value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def export_csv(self, csv_file: str):
        """Export timeline to CSV for analysis."""
        try:
            import csv
            with open(csv_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "channel", "event_type", "clip_path"
                ])
                for entry in sorted(self.entries, key=lambda e: e.timestamp):
                    writer.writerow([
                        entry.timestamp.isoformat(),
                        entry.channel,
                        entry.event_type,
                        entry.clip_path or "",
                    ])
            logger.info("Exported timeline to %s", csv_file)
        except Exception as e:
            logger.error("Failed to export CSV: %s", e)
