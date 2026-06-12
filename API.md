# API Reference

The service exposes a small REST API for checking the NVR connection, searching recordings, and browsing the event timeline.

Base URL:

```text
http://localhost:5000
```

## Health And Device Info

### `GET /api/health`

Checks whether the app can reach the NVR.

### `GET /api/device/info`

Returns the connected NVR model, firmware, MAC address, and channel count.

### `GET /api/channels`

Lists the available channels and names.

## Search Recordings

### `GET /api/search`

Search recordings by channel, date range, and optional event type.

Parameters:

- `channel` required, zero-based channel number
- `start_date` required, format `YYYY-MM-DD`
- `end_date` optional, defaults to `start_date`
- `event_type` optional, one of `DOORBELL`, `PERSON`, `MOTION`, `ANIMAL`, `VEHICLE`
- `stream` optional, `sub` or `main`

Example:

```bash
curl "http://localhost:5000/api/search?channel=8&start_date=2026-06-11&end_date=2026-06-12&event_type=PERSON&stream=main"
```

If you want every recording on a day, leave out `event_type`.

```bash
curl "http://localhost:5000/api/search?channel=8&start_date=2026-06-11"
```

## Timeline

### `GET /api/timeline`

Returns recently indexed events from the local timeline store.

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

## Debug

### `GET /api/debug/info`

Returns configuration details for troubleshooting. This is only enabled when debug mode is on.

## Response Shape

Search responses include:

- `channel`
- `start_date`
- `end_date`
- `event_type`
- `total_clips`
- `clips`

Each clip includes:

- `timestamp`
- `end_timestamp`
- `duration_seconds`
- `event_type`
- `trigger`
- `file_name`
- `stream_url`
- `download_url`

## Practical Notes

- `PERSON` searches can return only a few events on a given day, so use a wider date range if needed.
- The timeline is populated from search results, so search first if the timeline is empty.
- `channel=0` means the first camera channel.

