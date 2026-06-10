# Reolink NVR HA App — API Documentation

Complete API reference for the Reolink NVR Home Assistant App.

**Base URL:** `http://localhost:5000` (or your HA Green IP)

---

## Table of Contents

1. [Health & Status](#health--status)
2. [Device Information](#device-information)
3. [Recording Search](#recording-search-primary-endpoint)
4. [Examples](#examples)
5. [Error Handling](#error-handling)
6. [Response Models](#response-models)

---

## Health & Status

### GET `/api/health`

Health check endpoint. Returns the API and NVR connection status.

**Response:**
```json
{
  "status": "ok",
  "nvr_connected": true,
  "nvr_host": "192.168.1.100"
}
```

**Status codes:**
- `200 OK` — API is running (check `nvr_connected` for NVR status)
- `503 Service Unavailable` — API or NVR is down

**Use case:** Verify the add-on is operational before making search requests.

---

## Device Information

### GET `/api/device/info`

Retrieve NVR device details.

**Response:**
```json
{
  "model": "RLN16-410",
  "firmware_version": "v3.1.0.123",
  "nvr_name": "Front Door NVR",
  "mac_address": "AA:BB:CC:DD:EE:FF",
  "is_nvr": true,
  "num_channels": 8
}
```

**Status codes:**
- `200 OK` — Success
- `503 Service Unavailable` — NVR not connected

---

### GET `/api/channels`

List all available camera channels on the NVR.

**Response:**
```json
[
  {
    "channel": 0,
    "name": "Front Door",
    "enabled": true,
    "model": "RLC-810A"
  },
  {
    "channel": 1,
    "name": "Back Porch",
    "enabled": true,
    "model": "RLC-810A"
  },
  {
    "channel": 7,
    "name": "Driveway",
    "enabled": true,
    "model": null
  }
]
```

**Status codes:**
- `200 OK` — Success
- `503 Service Unavailable` — NVR not connected

---

## Recording Search (Primary Endpoint)

### GET `/api/search`

Search NVR recordings by date range and optional event type.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `channel` | int | ✅ Yes | Camera channel (0-based). Use `/api/channels` to list. |
| `start_date` | string | ✅ Yes | Start date in `YYYY-MM-DD` format |
| `end_date` | string | ⏸ Optional | End date in `YYYY-MM-DD` format. Defaults to `start_date`. |
| `event_type` | string | ⏸ Optional | Filter by event: `DOORBELL`, `PERSON`, `MOTION`, `ANIMAL`, `VEHICLE`. Omit for all. |
| `stream` | string | ⏸ Optional | Stream quality: `sub` (default, faster) or `main` (higher quality) |

**Response (200 OK):**
```json
{
  "channel": 0,
  "start_date": "2025-01-10",
  "end_date": "2025-01-10",
  "event_type": "DOORBELL",
  "total_clips": 3,
  "clips": [
    {
      "timestamp": "2025-01-10T14:32:15+00:00",
      "end_timestamp": "2025-01-10T14:32:40+00:00",
      "duration_seconds": 25,
      "event_type": "DOORBELL",
      "trigger": "visitor",
      "file_name": "2025_01_10_14_32_15.mp4",
      "stream_url": "rtsp://192.168.1.100/playback?token=ABC123...",
      "download_url": "http://192.168.1.100/api/reolink/download?id=XYZ789..."
    },
    {
      "timestamp": "2025-01-10T16:45:22+00:00",
      "end_timestamp": "2025-01-10T16:45:39+00:00",
      "duration_seconds": 17,
      "event_type": "DOORBELL",
      "trigger": "visitor",
      "file_name": "2025_01_10_16_45_22.mp4",
      "stream_url": "rtsp://192.168.1.100/playback?token=ABC456...",
      "download_url": "http://192.168.1.100/api/reolink/download?id=XYZ790..."
    }
  ]
}
```

**Error Responses:**

| Status | Detail | Cause |
|--------|--------|-------|
| `400` | Channel X out of range | Channel number invalid |
| `400` | Invalid date format | Date not in `YYYY-MM-DD` |
| `400` | start_date must be ≤ end_date | Wrong date order |
| `400` | Invalid event_type 'FOO' | Unknown event type |
| `502` | NVR API error | NVR query failed |
| `503` | NVR not connected | Add-on can't reach NVR |

**Event Types:**

- **DOORBELL** — Doorbell button press (visitor detection)
- **PERSON** — Human/person detected
- **MOTION** — General motion detection
- **ANIMAL** — Animal/pet detected
- **VEHICLE** — Vehicle detected
- *(omit for all recordings)*

**Stream Options:**

- **sub** (default) — Lower resolution, faster to load. Use for quick browsing.
- **main** — Full resolution. Use for detailed viewing.

---

## Examples

### Example 1: Get Doorbell Events from Today

```bash
curl "http://localhost:5000/api/search?channel=0&start_date=2025-01-10&event_type=DOORBELL"
```

### Example 2: Search Date Range for Person Detection

```bash
curl "http://localhost:5000/api/search?channel=0&start_date=2025-01-08&end_date=2025-01-10&event_type=PERSON"
```

### Example 3: Get All Recordings for a Day

```bash
curl "http://localhost:5000/api/search?channel=0&start_date=2025-01-10"
```

### Example 4: Get High-Quality Stream

```bash
curl "http://localhost:5000/api/search?channel=0&start_date=2025-01-10&stream=main"
```

### Example 5: In Home Assistant Template

```yaml
- alias: "Send Doorbell Clip Link in Notification"
  trigger:
    - trigger: state
      entity_id: binary_sensor.front_door_visitor_2
      to: "on"
  action:
    - service: notify.mobile_app_pixel_8_pro
      data:
        title: "🔔 Doorbell"
        message: "Someone is at the door!"
        data:
          # Link to today's doorbell events
          clickAction: >
            http://YOUR_HA_IP:5000/api/search?channel=8&start_date={{ now().strftime('%Y-%m-%d') }}&event_type=DOORBELL
```

### Example 6: Python Script to Download Recent Doorbell Videos

```python
import asyncio
import aiohttp
from datetime import datetime

async def download_doorbell_clips():
    base_url = "http://localhost:5000"
    
    # Search for today's doorbell events
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"{base_url}/api/search?channel=0&start_date={today}&event_type=DOORBELL"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            
            for clip in data["clips"]:
                timestamp = clip["timestamp"]
                download_url = clip["download_url"]
                filename = clip["file_name"]
                
                print(f"Downloading {filename} from {timestamp}...")
                
                # Download the clip
                async with session.get(download_url) as clip_resp:
                    with open(f"/tmp/{filename}", "wb") as f:
                        f.write(await clip_resp.read())
                    print(f"✓ Saved {filename}")

asyncio.run(download_doorbell_clips())
```

---

## Error Handling

All endpoints return JSON error responses with a `detail` field:

```json
{
  "detail": "Channel 99 out of range. NVR has 8 channels (0-based)."
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `400` | Bad request (invalid parameters) |
| `403` | Forbidden (e.g., debug endpoint disabled) |
| `502` | Bad Gateway (NVR API error) |
| `503` | Service Unavailable (NVR not connected) |

### Common Issues

**"NVR not connected"** (503)
- Check NVR IP address and port in add-on config
- Verify NVR credentials are correct
- Check network connectivity: `ping 192.168.1.100`
- Review add-on logs

**"Channel X out of range"** (400)
- Use `/api/channels` to see available channels
- Remember channels are **0-based** (first channel is 0, not 1)

**"Invalid date format"** (400)
- Must use `YYYY-MM-DD` (e.g., `2025-01-10`, not `1/10/2025`)

**"NVR API error"** (502)
- NVR API returned an error
- May indicate no recordings exist for the date range
- Check NVR web UI to verify recordings exist
- Check add-on logs for details

---

## Response Models

### Clip Object

```typescript
{
  timestamp:        string,     // ISO 8601 (e.g., "2025-01-10T14:32:15+00:00")
  end_timestamp:    string,     // ISO 8601 end time
  duration_seconds: number,     // Clip length in seconds
  event_type:       string,     // DOORBELL, PERSON, MOTION, ANIMAL, VEHICLE
  trigger:          string,     // Raw Reolink trigger string (e.g., "visitor")
  file_name:        string,     // Original NVR file name
  stream_url:       string|null,   // RTSP/FLV URL for playback
  download_url:     string|null    // HTTP URL for MP4 download
}
```

### SearchResponse Object

```typescript
{
  channel:     number,
  start_date:  string,         // YYYY-MM-DD
  end_date:    string,         // YYYY-MM-DD
  event_type:  string | null,  // Filter that was applied (or null)
  total_clips: number,         // Count of clips returned
  clips:       Clip[]          // Array of clip objects
}
```

### DeviceInfo Object

```typescript
{
  model:            string,
  firmware_version: string,
  nvr_name:         string,
  mac_address:      string,
  is_nvr:           boolean,
  num_channels:     number
}
```

### ChannelInfo Object

```typescript
{
  channel: number,
  name:    string,
  enabled: boolean,
  model:   string | null
}
```

---

## Rate Limiting

Currently, there is **no rate limiting**. The API will process all requests as fast as the NVR can respond.

**Recommendations:**
- Avoid hammering the API with many simultaneous searches
- Consider caching search results on the client side
- For large date ranges, break into multiple 7-day searches

---

## Future Enhancements

Planned endpoints (not yet implemented):

- `GET /api/download/{clip_id}` — Direct MP4 download
- `GET /api/snapshot/{clip_id}` — JPEG snapshot from clip
- `POST /api/events/subscribe` — Real-time event webhook
- `GET /api/search/stats` — Recording statistics by event type

---

## Support

- **Interactive docs:** Visit `http://localhost:5000/docs` (Swagger UI)
- **OpenAPI spec:** `http://localhost:5000/openapi.json`
- **Issues:** https://github.com/marcusmaday/reolink-nvr-ha-app/issues
