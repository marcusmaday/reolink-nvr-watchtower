# API Reference

Watchtower exposes a small HTTP API for the event dashboard, clip playback, live view, and timeline lookup.

Base URL examples:

```text
http://localhost:5000
```

When the app is opened through Home Assistant ingress, the same routes are also available under:

```text
/app/15e0e6e5_watchtower
```

## Core Status

### `GET /api/health`

Returns whether the app is connected to the NVR.

### `GET /api/device/info`

Returns the connected NVR model, firmware, MAC address, and channel count.

### `GET /api/channels`

Returns the list of available channels and their names.

### `GET /api/debug/info`

Returns runtime configuration and rolling-buffer status. This endpoint is only available when debug mode is enabled.

## Recordings And Timeline

### `GET /api/search`

Search recordings on the NVR.

Parameters:

- `channel` required, zero-based channel number
- `start_date` required, format `YYYY-MM-DD`
- `end_date` optional, defaults to `start_date`
- `event_type` optional, one of `DOORBELL`, `PERSON`, `MOTION`, `ANIMAL`, `VEHICLE`
- `stream` optional, `sub` or `main`

Examples:

```bash
curl "http://localhost:5000/api/search?channel=8&start_date=2026-06-11&end_date=2026-06-12&event_type=PERSON&stream=main"
```

```bash
curl "http://localhost:5000/api/search?channel=8&start_date=2026-06-11"
```

### `GET /api/timeline`

Returns events from the local timeline store.

Parameters:

- `hours` optional, how far back to look
- `channel` optional, filter to one channel
- `event_type` optional, filter to one event type
- `limit` optional, maximum number of entries

Example:

```bash
curl "http://localhost:5000/api/timeline?hours=48&channel=8&event_type=PERSON"
```

### `GET /api/timeline/{entry_id}`

Returns one timeline entry by ID.

### `GET /api/events/recent`

Returns the event list used by the app dashboard.

Parameters:

- `limit` optional, maximum number of entries
- `channel` optional, filter to one channel
- `event_type` optional, filter to one event type

## Event Ingest And Playback

### `POST /api/events/ingest`

Creates a timeline entry from Home Assistant or another source.

This is the relay endpoint used by the Home Assistant notification flow.

### `GET /api/events/{entry_id}/clip`

Returns the playable clip for a timeline event.

### `GET /api/events/{entry_id}/live`

Returns the live-view target for a timeline event.

### `POST /api/webhook/reolink`

Accepts a Reolink ONVIF webhook payload.

## Live Views

### `GET /api/live/{channel}/mjpeg`

Returns a browser-friendly MJPEG stream for the requested channel.

### `GET /app`

Opens the event dashboard.

### `GET /app/live`

Opens the live camera page.

### `GET /app/ws/events`

WebSocket feed for live dashboard updates.

## Response Notes

Search responses include:

- `channel`
- `start_date`
- `end_date`
- `event_type`
- `total_clips`
- `clips`

Timeline entries and recent events include the clip URL, live URL, thumbnail URL, clip status, and camera metadata needed by the dashboard.

## Practical Notes

- `PERSON` and `DOORBELL` are the main event types for the mobile notification flow.
- `channel=0` means the first camera channel.
- If you are testing through Home Assistant ingress, use the app route under `/app/...` instead of a raw LAN URL.
