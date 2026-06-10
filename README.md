# Reolink NVR Home Assistant App

A Home Assistant add-on that provides a REST API wrapper around the Reolink NVR API for advanced recording search, filtering, and clip management.

## Purpose

The built-in Home Assistant Reolink integration's media browser has limitations:
- Cannot reliably filter recordings by event type (Person, Doorbell, Motion, etc.)
- Event-level links in notifications always resolve to day-level views
- Limited programmatic access to clip metadata

This add-on solves these problems by:
- Providing direct API access to Reolink NVR recording metadata
- Filtering clips by date, time, channel, and event type
- Generating direct URLs to specific event clips
- Enabling custom dashboard cards and automations

## Architecture

```
Home Assistant
    ↓
Reolink NVR HA App (FastAPI + reolink_aio)
    ↓
Reolink NVR HTTP API
    ↓
NVR Hardware
```

## Features

- ✅ Search recordings by date and time range
- ✅ Filter by event type (DOORBELL, PERSON, MOTION, ANIMAL)
- ✅ List available clips with metadata
- ✅ Generate direct stream/download URLs
- ✅ Multi-channel support
- ✅ Main and sub-stream support
- ✅ Real-time event webhooks (planned)

## Installation

### Prerequisites
- Home Assistant Green (or any HA installation)
- Reolink NVR with HTTP API access
- NVR credentials (username/password)
- NVR IP address

### Steps

1. Add the repository to Home Assistant Apps:
   - Settings → Apps → Install App → ⋮ → Repositories → Create Repository
   - (In Home Assistant 2026+, "Add-ons" was renamed to "Apps")
   - URL: `https://github.com/marcusmaday/reolink-nvr-ha-app`

2. Install the Reolink NVR HA App add-on

3. Configure with your NVR details (see Configuration below)

4. Start the add-on

5. Check logs to verify it's running on `http://localhost:5000`

## Configuration

The add-on is configured via Home Assistant's add-on options panel.

**Example configuration:**
```yaml
nvr_host: 192.168.1.100
nvr_port: 80
nvr_username: admin
nvr_password: your_password
nvr_ssl: false
debug: false
api_port: 5000
```

## API Endpoints

### Search Recordings

**GET** `/api/search`

Query parameters:
- `channel` (required): Camera channel number
- `start_date` (required): ISO 8601 date (YYYY-MM-DD)
- `end_date` (optional): ISO 8601 date (YYYY-MM-DD), defaults to start_date
- `event_type` (optional): `DOORBELL`, `PERSON`, `MOTION`, `ANIMAL`, or empty for all

**Example:**
```bash
curl "http://localhost:5000/api/search?channel=8&start_date=2025-01-10&event_type=DOORBELL"
```

**Response:**
```json
{
  "channel": 8,
  "start_date": "2025-01-10",
  "end_date": "2025-01-10",
  "event_type": "DOORBELL",
  "clips": [
    {
      "timestamp": "2025-01-10T14:32:15Z",
      "duration_seconds": 25,
      "event_type": "DOORBELL",
      "stream_url": "rtsp://...",
      "download_url": "/api/download/...",
      "thumbnail_url": "/api/snapshot/..."
    }
  ]
}
```

### Download Clip

**GET** `/api/download/<clip_id>`

Downloads a specific clip as MP4.

### Get Snapshot

**GET** `/api/snapshot/<clip_id>`

Gets a JPEG snapshot from a clip.

### Device Info

**GET** `/api/device/info`

Returns NVR device information, model, firmware version, etc.

### Channel Info

**GET** `/api/channels`

Lists all available channels with their configuration.

## Usage in Home Assistant

### Automation with Notifications

Reference the API in your doorbell automation:

```yaml
alias: "Doorbell: Notifications and Unlock"
triggers:
  - trigger: state
    entity_id: binary_sensor.front_door_visitor_2
    to: "on"
    id: pressed
actions:
  - action: notify.mobile_app_pixel_8_pro
    data:
      title: "🔔 Doorbell"
      message: "Someone is at the door!"
      data:
        clickAction: >
          https://your-nabu-casa-url.ui.nabu.casa/api/reolink-nvr-ha-app/search?channel=8&start_date={{now().strftime('%Y-%m-%d')}}&event_type=DOORBELL
```

### Custom Dashboard Card

Create a Lovelace card that fetches and displays recent doorbell events:

```yaml
type: custom:html-card
html: |
  <div id="doorbell-clips"></div>
  <script>
    async function loadClips() {
      const today = new Date().toISOString().split('T')[0];
      const res = await fetch(
        `/api/reolink-nvr-ha-app/search?channel=8&start_date=${today}&event_type=DOORBELL`
      );
      const data = await res.json();
      const html = data.clips.map(clip => `
        <div style="border: 1px solid #ccc; padding: 10px; margin: 10px 0;">
          <p><strong>${clip.timestamp}</strong> - ${clip.duration_seconds}s</p>
          <video controls width="100%" style="max-height: 300px;">
            <source src="${clip.stream_url}" type="video/mp4">
          </video>
        </div>
      `).join('');
      document.getElementById('doorbell-clips').innerHTML = html || '<p>No clips found</p>';
    }
    loadClips();
  </script>
```

## Troubleshooting

### Add-on won't start
- Check app logs in Home Assistant (Settings → Apps → Reolink NVR HA App → Logs)
- Verify NVR credentials
- Ensure NVR is reachable from HA Green

### API returns 401 Unauthorized
- Verify NVR username/password in add-on config
- Check if NVR user account has API access

### Clips not found
- Verify channel number matches your setup
- Ensure recordings exist for the selected date range
- Check event type matches actual events

### Connection timeout
- Verify NVR IP address and port
- Check network connectivity between HA Green and NVR
- Try disabling SSL if using HTTP

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for development setup and architecture details.

## Contributing

Contributions welcome! Please:
1. Fork the repo
2. Create a feature branch
3. Submit a pull request with description

## License

MIT License - see [LICENSE](LICENSE) file

## Support

For issues, questions, or suggestions:
- GitHub Issues: https://github.com/marcusmaday/reolink-nvr-ha-app/issues
- Home Assistant Community: (link to forum post)

## Disclaimer

This add-on is not officially affiliated with Reolink. Use at your own risk.
