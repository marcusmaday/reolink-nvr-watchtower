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
from reolink_aio.enums import VodRequestType
from reolink_aio.typings import VOD_trigger

logger = logging.getLogger(__name__)

# Map our API event type strings to Reolink VOD trigger flags.
EVENT_TYPE_MAP = {
    "DOORBELL": VOD_trigger.DOORBELL,
    "PERSON":   VOD_trigger.PERSON,
    "MOTION":   VOD_trigger.MOTION,
    "ANIMAL":   VOD_trigger.ANIMAL,
    "VEHICLE":  VOD_trigger.VEHICLE,
}

# Reverse map for labeling results and manual fallback filtering.
TRIGGER_TO_EVENT = {
    int(VOD_trigger.DOORBELL): "DOORBELL",
    int(VOD_trigger.PERSON): "PERSON",
    int(VOD_trigger.MOTION): "MOTION",
    int(VOD_trigger.ANIMAL): "ANIMAL",
    int(VOD_trigger.VEHICLE): "VEHICLE",
}

EVENT_TRIGGER_PRIORITY = (
    ("PERSON", VOD_trigger.PERSON),
    ("DOORBELL", VOD_trigger.DOORBELL),
    ("MOTION", VOD_trigger.MOTION),
    ("ANIMAL", VOD_trigger.ANIMAL),
    ("VEHICLE", VOD_trigger.VEHICLE),
)


def _normalize_trigger_value(raw_trigger) -> Optional[int]:
    if raw_trigger is None:
        return None

    if isinstance(raw_trigger, VOD_trigger):
        return int(raw_trigger)

    try:
        return int(raw_trigger)
    except (TypeError, ValueError):
        return None


def _extract_event_type(vod_file) -> tuple[str, str]:
    """
    Return (event_type, trigger_label) for a VOD file.

    Event-triggered files use bc_triggers, which is a VOD_trigger bitmask.
    Continuous recordings fall back to the file type (typically "sub").
    """
    bc_triggers = getattr(vod_file, "bc_triggers", None)
    if bc_triggers is not None:
        try:
            trigger_flags = VOD_trigger(int(bc_triggers))
            for event_name, flag in EVENT_TRIGGER_PRIORITY:
                if trigger_flags & flag:
                    return event_name, event_name.lower()
        except (TypeError, ValueError):
            pass

    raw_trigger = getattr(vod_file, "trigger", None) or getattr(vod_file, "type", None)
    trigger_value = _normalize_trigger_value(raw_trigger)
    if trigger_value is not None:
        event_name = TRIGGER_TO_EVENT.get(trigger_value)
        if event_name:
            return event_name, event_name.lower()

    if raw_trigger is not None:
        trigger_label = str(raw_trigger).lower()
        return str(raw_trigger).upper(), trigger_label

    return "UNKNOWN", "unknown"


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
            # for the given channel and date and returns them directly. The
            # trigger parameter filters by event type.
            request_kwargs = dict(
                start=datetime(year, month, day, 0, 0, 0),
                end=datetime(year, month, day, 23, 59, 59),
                split_time=False,
            )
            if trigger is not None:
                request_kwargs["trigger"] = trigger

            request_result = await host.request_vod_files(channel, **request_kwargs)
            if isinstance(request_result, tuple) and len(request_result) == 2:
                _, vod_files = request_result
            else:
                vod_files = request_result or []

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
                request_result = await host.request_vod_files(
                    channel,
                    start=datetime(year, month, day, 0, 0, 0),
                    end=datetime(year, month, day, 23, 59, 59),
                    split_time=False,
                )
                if isinstance(request_result, tuple) and len(request_result) == 2:
                    _, vod_files = request_result
                else:
                    vod_files = request_result or []
            except ReolinkError as e2:
                logger.warning("Failed to request VOD files for %s: %s", current, e2)
                current += timedelta(days=1)
                continue

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

    # Get the event type from the VOD file.
    detected_event_type, raw_trigger_label = _extract_event_type(vod_file)

    # Manual filter if we couldn't pass trigger to request_vod_files or if the
    # library returned a different-but-equivalent trigger spelling.
    if event_type_filter and detected_event_type != event_type_filter.upper():
        return None

    # Get file name
    file_name = getattr(vod_file, "file_name", None) or getattr(vod_file, "name", "unknown")

    # Generate stream/playback URL using get_vod_source
    stream_url = None
    download_url = None

    try:
        # get_vod_source expects the VOD filename, not the whole object.
        stream_mime, stream_source = await host.get_vod_source(
            channel,
            str(file_name),
            stream,
            request_type=VodRequestType.FLV,
        )
        stream_url = stream_source or None
        if stream_mime:
            logger.debug("Stream VOD source mime=%s for %s", stream_mime, file_name)
    except Exception as e:
        logger.debug("Could not generate stream URL for VOD file: %s", e)

    try:
        # Prefer the direct download URL for browser playback; it usually yields MP4.
        download_mime, download_source = await host.get_vod_source(
            channel,
            str(file_name),
            stream,
            request_type=VodRequestType.DOWNLOAD,
        )
        download_url = download_source or None
        if not stream_url:
            stream_url = download_url
        if download_mime:
            logger.debug("Download VOD source mime=%s for %s", download_mime, file_name)
    except Exception:
        download_url = stream_url  # Fall back to stream URL

    return {
        "timestamp":        start_time.isoformat(),
        "end_timestamp":    end_time.isoformat(),
        "duration_seconds": duration_seconds,
        "event_type":       detected_event_type,
        "trigger":          raw_trigger_label,
        "file_name":        str(file_name),
        "stream_url":       stream_url,
        "download_url":     download_url,
    }


async def get_channels_info(host: Host) -> list[dict]:
    """
    Return info about all available channels on the NVR.
    """
    channels = []
    for i in range(host.num_channels):
        channels.append({
            "channel":  i,
            "name":     host.camera_name(i) or f"Channel {i}",
            "enabled":  True,
            "model":    host.camera_model(i) if hasattr(host, "camera_model") else None,
        })
    return channels
