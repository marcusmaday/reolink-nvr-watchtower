# Reolink Enhanced Integration - Implementation Guide

This document describes the implementation of the Reolink Enhanced API system as defined in the design document.

## Architecture Overview

```
┌─────────────────────────────────────────┐
│        Home Assistant OS                │
├─────────────────────────────────────────┤
│  Custom Integration: reolink_enhanced   │
│  ├─ Camera Entities                     │
│  ├─ Binary Sensors (motion, person, ...) │
│  ├─ Event Entities                      │
│  └─ Timeline UI (Lovelace card)         │
└─────────────────┬───────────────────────┘
                  │ HTTP/WebSocket
┌─────────────────▼───────────────────────┐
│    Reolink Enhanced API App             │
├─────────────────────────────────────────┤
│  FastAPI Server (Port 5000)             │
│  ├─ REST Endpoints                      │
│  └─ WebSocket Events                    │
└─────────────────┬───────────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
┌──────────────┐    ┌────────────────────┐
│  NVR Client  │    │ Internal Systems   │
├──────────────┤    ├────────────────────┤
│ • Connect    │    │ • Event Stream     │
│ • Channels   │    │ • Video Buffer     │
│ • Search VOD │    │ • Clip Generator   │
│ • RTSP URLs  │    │ • Timeline Index   │
└──────┬───────┘    │ • Storage Manager  │
       │            └────────────────────┘
       │
       ▼
    Reolink NVR
    ├─ API (limited)
    ├─ RTSP Streams
    └─ VOD Database
```

## Components Implemented

### 1. App Core Modules

#### `nvr_client.py` - NVR Communication
- Low-level Reolink API wrapper using `reolink_aio`
- Connection management and authentication
- Device info retrieval
- RTSP URL generation
- Health checks

```python
nvr_client = NVRClient(host="192.168.1.100", ...)
await nvr_client.connect()
channels = await nvr_client.get_channels()
```

#### `event_stream.py` - Real-Time Events
- Persistent event listener
- Subscriber pattern for event broadcasting
- Event type definitions (motion, person, vehicle, doorbell, animal)
- Reconnection logic with exponential backoff

```python
event_stream = EventStream(nvr_client)
await event_stream.start()

def on_event(event: Event):
    print(f"Event on channel {event.channel}: {event.event_type}")

unsubscribe = event_stream.subscribe(on_event)
```

#### `video_buffer.py` - Rolling RTSP Buffer
- Circular buffer management per channel
- Continuous video capture (configurable duration: 10-300 seconds)
- Frame extraction for clip generation

```python
buffer_manager = VideoBufferManager(nvr_client, buffer_size_seconds=60)
await buffer_manager.start()
await buffer_manager.extract_clip(channel=0, start_time=..., end_time=..., output_path="clip.mp4")
```

#### `clip_generator.py` - Event-Based Clips
- Generates clips around event timestamps
- Configurable pre/post-event duration (1-30 seconds each)
- Organized storage structure: `/clips/{channel}/{YYYY-MM-DD}/{timestamp}_{event_type}.mp4`

```python
generator = ClipGenerator(buffer_manager, "/ data/clips")
metadata = await generator.generate_clip_for_event(
    channel=0,
    event_type="person",
    event_timestamp=datetime.now()
)
```

#### `timeline_index.py` - Event Timeline
- JSON-based searchable event index
- Query by channel, event type, time range
- Automatic pruning of old entries
- CSV export capability

```python
timeline = TimelineIndex("/data/timeline.json")
entries = timeline.get_entries(channel=0, event_type="person", hours=24)
```

#### `config.py` - Configuration Management
- Environment variable parsing
- Structured config objects
- Supports Home Assistant add-on configuration
- Validates and logs settings

```python
config = get_config()
print(f"NVR: {config.nvr.host}:{config.nvr.port}")
print(f"Retention: {config.storage.retention_days} days")
```

#### `storage_manager.py` - Clip Storage & Retention
- Enforces retention policies (delete clips older than N days)
- Enforces storage limits (delete oldest clips if exceeding max_mb)
- Supports external storage mounting
- Background maintenance task

```python
storage = StorageManager(
    clips_directory="/data/clips",
    retention_days=7,
    max_storage_mb=5000
)
await storage.start()
info = await storage.get_storage_info()
```

### 2. REST API Endpoints

#### Health & Device
- `GET /api/health` - System health check
- `GET /api/device/info` - NVR device information
- `GET /api/channels` - List camera channels
- `GET /api/stats` - System statistics

#### Search & Recordings
- `GET /api/search?channel=0&start_date=2024-06-01&event_type=person` - Search recordings

Parameters:
- `channel` (required): Camera channel (0-based)
- `start_date` (required): Start date YYYY-MM-DD
- `end_date` (optional): End date, defaults to start_date
- `event_type` (optional): DOORBELL, PERSON, MOTION, ANIMAL, VEHICLE
- `stream` (optional): "sub" or "main"

#### Timeline
- `GET /api/timeline?channel=0&hours=24&limit=100` - Get event timeline
- `GET /api/timeline/{entry_id}` - Get timeline entry details

#### Clips
- `GET /api/clips/{clip_id}` - Download clip file

### 3. WebSocket API

#### Real-Time Events
```
ws://localhost:5000/ws/events
```

Connect to receive real-time events:
```json
{
  "type": "event",
  "timestamp": "2024-06-10T14:23:45.123456",
  "channel": 0,
  "event_type": "person",
  "event_id": "evt_12345",
  "metadata": {...}
}
```

### 4. Home Assistant Custom Integration

#### Configuration Flow
- Input: API host and port
- Validates connection to API
- Confirms NVR connectivity

#### Entities Created

**Camera Entities**
- One per channel
- Snapshot capability
- RTSP stream support

**Binary Sensors**
- Motion detection per channel
- Person detection per channel
- Vehicle detection per channel
- Animal detection per channel

**Event Entities** (optional)
- Records events for automation

#### Services
- `reolink_enhanced.send_clip_notification` - Send clip with notification
- `reolink_enhanced.refresh_snapshot` - Force snapshot refresh
- `reolink_enhanced.get_recent_events` - Get recent events

### 5. Docker & Home Assistant Add-on

**Dockerfile**: Multi-stage build with Alpine base
- Python 3, pip, ffmpeg installed
- Healthcheck configured
- Data volumes mounted at `/data/reolink`

**Add-on Manifest** (`addon/manifest.json`)
- Exposes port 5000
- Configuration schema for all settings
- Requires Home Assistant 2024.1.0+

**Add-on Run Script** (`addon/run.sh`)
- Reads options from `/data/options.json`
- Sets environment variables
- Starts FastAPI server

## Configuration

### Environment Variables

```bash
# NVR Connection
NVR_HOST=192.168.1.100
NVR_PORT=80
NVR_USERNAME=admin
NVR_PASSWORD=password
NVR_SSL=false

# Video Buffer
BUFFER_ENABLED=true
BUFFER_SIZE_SECONDS=60
CLIP_DURATION_BEFORE=5
CLIP_DURATION_AFTER=5
CLIP_QUALITY=medium

# Storage
RETENTION_DAYS=7
MAX_STORAGE_MB=5000
EXTERNAL_STORAGE_PATH=/media/nas/reolink  # Optional

# API
API_HOST=0.0.0.0
API_PORT=5000
DEBUG=false
```

### Home Assistant Add-on Config

The add-on presents a configuration UI in Home Assistant:
- NVR Host/Port/Username/Password
- Buffer settings
- Retention policy
- Storage limits
- Debug mode

## Direct-to-Video Notifications

Flow:
1. Event detected on NVR
2. Add-on receives event via event stream
3. Clip extracted from buffer (N seconds before to N seconds after)
4. Clip saved to storage
5. Integration receives event notification
6. Integration sends Home Assistant notification with:
   - Thumbnail (from NVR)
   - Video clip URL
   - Event metadata (time, type, channel)

Example automation:
```yaml
automation:
  - alias: "Person Detected - Send Notification"
    trigger:
      platform: state
      entity_id: binary_sensor.camera_0_person
      to: "on"
    action:
      service: reolink_enhanced.send_clip_notification
      data:
        channel: 0
        title: "Person Detected!"
        message: "Motion detected on Front Camera"
```

## Storage Management

### Retention Policy
- Delete clips older than `RETENTION_DAYS` days
- Enforced hourly by `StorageManager`

### Storage Limit
- If total clip size > `MAX_STORAGE_MB`, delete oldest clips until at 90% of limit
- Prevents filling Home Assistant Green's limited storage

### Clip Storage Structure
```
/data/reolink/
├── clips/
│   ├── 0/                    # Channel 0
│   │   ├── 2024-06-01/
│   │   │   ├── 1718000000_person.mp4
│   │   │   ├── 1718005000_motion.mp4
│   │   │   └── ...
│   │   └── 2024-06-02/
│   │       └── ...
│   └── 1/                    # Channel 1
│       └── ...
└── timeline.json             # Timeline index
```

## Development & Testing

### Local Testing with Docker Compose

```bash
docker-compose up -d
curl http://localhost:5000/api/health
```

Environment can be customized by editing `docker-compose.yml`.

### Running Without Docker

```bash
cd reolink-nvr-ha-app/app
pip install -r requirements.txt
export NVR_HOST=192.168.1.100
export NVR_PORT=80
export NVR_USERNAME=admin
export NVR_PASSWORD=password
python main.py
```

## Future Enhancements

1. **RTSP Capture**: Integrate ffmpeg for actual RTSP stream capture into buffers
2. **Thumbnail Generation**: Auto-generate thumbnails for timeline
3. **Advanced Filtering**: ML-based event filtering (reduce false positives)
4. **Custom Lovelace Card**: Timeline UI visualization
5. **Database Backend**: Replace JSON index with SQLite for large deployments
6. **Cloud Backup**: Optional clip upload to cloud storage
7. **Recording Playback**: Stream long recordings from NVR (fallback mode)

## Troubleshooting

### NVR Not Connecting
- Check NVR IP/port/credentials
- Verify NVR is on same network
- Check firewall rules
- Enable debug mode for detailed logs

### High Storage Usage
- Reduce `BUFFER_SIZE_SECONDS`
- Lower `RETENTION_DAYS`
- Enable `CLIP_QUALITY=low` for re-encoding
- Increase `MAX_STORAGE_MB` if possible

### Missing Events
- Increase buffer size
- Check NVR event channel configuration
- Verify event types are enabled on NVR

### WebSocket Connection Issues
- Check firewall rules for port 5000
- Verify Home Assistant can reach add-on IP:port
- Enable debug logs for details

## License

MIT License - See LICENSE file
