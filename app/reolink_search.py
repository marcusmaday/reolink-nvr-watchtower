"""
reolink_search.py

Core recording search logic using reolink_aio.
Handles querying NVR for VOD files, filtering by event type,
and generating stream/download URLs.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from reolink_aio.api import Host
from reolink_aio.exceptions import ReolinkError

logger = logging.getLogger(__name__)

# Map our API event type strings to reolink_aio trigger strings
# These correspond to the 'trigger' parameter in request_vod_files()
EVENT_TYPE_MAP = {
    "DOORBELL": "visitor",
    "PERSON":   "people",
    "MOTION":   "md",
    "ANIMAL":   "animal",
    "VEHICLE":  "vehicle",
}

# Reverse map for labeling results
TRIGGER_TO_EVENT = {v: k for k, v in EVENT_TYPE_MAP.items()}


async def search_recordings(
    host: Host,
    channel: int,
    start_dt: datetime,
    end_dt: datetime,
    event_type: Optional[str] = None,
    stream: str = "sub",
) -> list[dict]:
    """
    Search for recordings on the NVR for a given channel and date range.

    Args:
        host:       Connected reolink_aio Host instance
        channel:    Camera channel number (0-based)
        start_dt:   Start of search window (datetime, any timezone or naive)
        end_dt:     End of search window (datetime, any timezone or naive)
        event_type: Optional filter — "DOORBELL", "PERSON", "MOTION", "ANIMAL", "VEHICLE"
        stream:     "sub" (default, faster) or "main" (higher quality)

    Returns:
        List of dicts, each representing one clip:
        {
            "timestamp":        str (ISO 8601),
            "end_timestamp":    str (ISO 8601),
            "duration_seconds": int,
            "event_type":       str,
            "trigger":          str,   # raw reolink trigger string
            "file_name":        str,
            "stream_url":       str | None,
            "download_url":     str | None,
        }
    """

    # Translate event_type → reolink trigger string (or None for all)
    trigger = None
    if event_type:
        trigger = EVENT_TYPE_MAP.get(event_type.upper())
        if trigger is None:
            raise ValueError(
                f"Unknown event_type '{event_type}'. "
                f"Valid options: {list(EVENT_TYPE_MAP.keys())}"
            )

    clips = []

    # reolink_aio works day-by-day; iterate each day in the range
    current = start_dt.date()
    end_date = end_dt.date()

    while current <= end_date:
        year  = current.year
        month = current.month
        day   = current.day

        logger.debug(
            "Requesting VOD files for channel=%s, date=%s/%s/%s, trigger=%s",
            channel, year, month, day, trigger
        )

        try:
            # request_vod_files populates an internal list of VOD_file objects
            # for the given channel and date. The trigger parameter filters
            # by event type (added in reolink_aio 0.13.3+).
            if trigger:
                await host.request_vod_files(
                    channel,
                    start=datetime(year, month, day, 0, 0, 0),
                    end=datetime(year, month, day, 23, 59, 59),
                    split_time=False,
                    trigger=trigger,
                )
            else:
                await host.request_vod_files(
                    channel,
                    start=datetime(year, month, day, 0, 0, 0),
                    end=datetime(year, month, day, 23, 59, 59),
                    split_time=False,
                )

        except ReolinkError as e:
            logger.warning("Failed to request VOD files for %s: %s", current, e)
            current += timedelta(days=1)
            continue
        except TypeError as e:
            # Older reolink_aio version may not support 'trigger' kwarg
            logger.warning(
                "request_vod_files does not support 'trigger' parameter, "
                "fetching all and filtering manually: %s", e
            )
            try:
                await host.request_vod_files(
                    channel,
                    start=datetime(year, month, day, 0, 0, 0),
                    end=datetime(year, month, day, 23, 59, 59),
                    split_time=False,
                )
            except ReolinkError as e2:
                logger.warning("Failed to request VOD files for %s: %s", current, e2)
                current += timedelta(days=1)
                continue

        # Access the VOD file list from the host
        vod_files = host.vod_files(channel)

        if not vod_files:
            logger.debug("No VOD files found for channel=%s on %s", channel, current)
            current += timedelta(days=1)
            continue

        logger.debug("Found %s VOD files for channel=%s on %s", len(vod_files), channel, current)

        for vod_file in vod_files:
            try:
                clip = await _process_vod_file(
                    host=host,
                    channel=channel,
                    vod_file=vod_file,
                    stream=stream,
                    event_type_filter=event_type,
                    trigger_filter=trigger,
                )
                if clip:
                    clips.append(clip)
            except Exception as e:
                logger.warning("Error processing VOD file: %s", e)
                continue

        current += timedelta(days=1)

    # Sort by timestamp ascending
    clips.sort(key=lambda x: x["timestamp"])
    return clips


async def _process_vod_file(
    host: Host,
    channel: int,
    vod_file,
    stream: str,
    event_type_filter: Optional[str],
    trigger_filter: Optional[str],
) -> Optional[dict]:
    """
    Convert a reolink_aio VOD_file object into our response dict.

    Returns None if the file should be filtered out.
    """

    # Extract timestamps from the VOD_file object
    # Attributes: start_time, end_time (datetime objects)
    start_time: datetime = vod_file.start_time
    end_time: datetime   = vod_file.end_time

    # Calculate duration
    duration_seconds = int((end_time - start_time).total_seconds())
    if duration_seconds <= 0:
        return None

    # Get the trigger/event type from the VOD file
    # VOD_file may have a 'trigger' or 'type' attribute
    raw_trigger = getattr(vod_file, "trigger", None) or getattr(vod_file, "type", "unknown")

    # Manual filter if we couldn't pass trigger to request_vod_files
    if trigger_filter and raw_trigger and raw_trigger != trigger_filter:
        return None

    # Map raw trigger to our event type string
    detected_event_type = TRIGGER_TO_EVENT.get(str(raw_trigger).lower(), raw_trigger.upper() if raw_trigger else "UNKNOWN")

    # Get file name
    file_name = getattr(vod_file, "file_name", None) or getattr(vod_file, "name", "unknown")

    # Generate stream/playback URL using get_vod_source
    stream_url = None
    download_url = None

    try:
        # get_vod_source returns an (url, mime_type) tuple or similar
        # It generates an authenticated URL to play the clip
        vod_source = await host.get_vod_source(channel, vod_file, stream)
        if vod_source:
            # vod_source may be a string URL or a tuple (url, mime_type)
            if isinstance(vod_source, tuple):
                stream_url = vod_source[0]
            else:
                stream_url = str(vod_source)
    except Exception as e:
        logger.debug("Could not generate stream URL for VOD file: %s", e)

    # Try to get NvrDownload URL if available (added in reolink_aio 0.13.3)
    try:
        download_url = await host.get_vod_source(channel, vod_file, stream, stream_type="download")
        if isinstance(download_url, tuple):
            download_url = download_url[0]
    except Exception:
        download_url = stream_url  # Fall back to stream URL

    return {
        "timestamp":        start_time.isoformat(),
        "end_timestamp":    end_time.isoformat(),
        "duration_seconds": duration_seconds,
        "event_type":       detected_event_type,
        "trigger":          str(raw_trigger) if raw_trigger else "unknown",
        "file_name":        str(file_name),
        "stream_url":       stream_url,
        "download_url":     download_url,
    }


async def get_channels_info(host: Host) -> list[dict]:
    """
    Return info about all available channels on the NVR.
    """
    channels = []
    for i in range(host.num_channel):
        channels.append({
            "channel":  i,
            "name":     host.camera_name(i) or f"Channel {i}",
            "enabled":  True,
            "model":    host.camera_model(i) if hasattr(host, "camera_model") else None,
        })
    return channels
