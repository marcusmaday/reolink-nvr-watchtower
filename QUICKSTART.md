# Quick Start

Use this path if you want the service running quickly and do not need the full background on the project.

## 1. Set Up The NVR Connection

In Home Assistant add-on settings or your local `.env`, set:

```bash
API_PORT=5000
API_HOST=0.0.0.0
NVR_HOST=192.168.50.42
NVR_PORT=80
NVR_USERNAME=admin
NVR_PASSWORD=your_password
NVR_SSL=false
BUFFER_ENABLED=true
BUFFER_SIZE_SECONDS=60
CLIP_DURATION_BEFORE=5
CLIP_DURATION_AFTER=5
CLIP_QUALITY=medium
RETENTION_DAYS=7
MAX_STORAGE_MB=5000
EXTERNAL_STORAGE_PATH=
ALLOW_CORS=false
```

If you change the add-on `api_port`, keep the add-on port mapping aligned with that value and use the same port in the relay URL and in any local client URLs.
`CLIP_QUALITY` selects the RTSP stream for generated clips. `high` uses the main stream; all other values use the sub stream.

## 2. Add The Add-On Repository

In Home Assistant:

1. Go to `Settings` -> `Add-ons` -> `Add-on Store`
2. Open the three-dot menu and choose `Repositories`
3. Add:

```text
https://github.com/marcusmaday/reolink-nvr-ha-app
```

## 3. Start The Service

### Home Assistant add-on

Install the add-on, fill in the options, and start it from the add-on page.

### Local Docker

```bash
docker compose up -d
```

## 4. Check That It Works

```bash
curl http://localhost:5000/api/health
curl http://localhost:5000/api/device/info
curl http://localhost:5000/api/channels
```

## 5. Search Recordings

```bash
curl "http://localhost:5000/api/search?channel=8&start_date=2026-06-11&event_type=PERSON&stream=main"
```

If you want all recordings for a day, omit `event_type`.

```bash
curl "http://localhost:5000/api/search?channel=8&start_date=2026-06-11"
```

## 6. View The Timeline

```bash
curl "http://localhost:5000/api/timeline?hours=48&channel=8"
```

## 7. Set Up Notifications

Use the blueprint instead of editing `automations.yaml` by hand:

```text
https://raw.githubusercontent.com/marcusmaday/reolink-nvr-ha-app/main/blueprints/automation/reolink_enhanced_notification.yaml
```

Import it in Home Assistant, then set your sensors, lock, notification services, app base URL, and camera name.

The blueprint also handles the `UNLOCK_DOOR` action from the notification button, so it replaces the separate unlock automation.

Add this one `rest_command` block to `configuration.yaml` so the blueprint can relay the event into the app timeline:

```yaml
rest_command:
  reolink_ingest_event:
    url: "http://HA_GATEWAY_IP:APP_PORT/api/events/ingest"
    method: POST
    content_type: "application/json"
    payload: >-
      {
        "event_type": "{{ event_type }}",
        "channel": {{ channel }},
        "timestamp": "{{ timestamp }}",
        "camera_name": "{{ camera_name }}",
        "snapshot_url": "{{ snapshot_url }}",
        "live_url": "{{ live_url }}",
        "title": "{{ title }}",
        "message": "{{ message }}",
        "source": "home_assistant"
      }
```

`APP_PORT` is the app port configured in the add-on options and defaults to `5000`. If you do not know `HA_GATEWAY_IP`, open the add-on shell and run:

```bash
ip route | awk '/default/ {print $3}'
```

Use that IP with the configured app port. It is an internal Home Assistant network address, not your public remote-access URL.

If you are writing a manual example, keep the real remote URL out of shared examples and use a placeholder:

```yaml
app_base_url: "https://YOUR_HA_REMOTE_URL/app/reolink_enhanced_api"
app_event_url: "{{ app_base_url }}?channel=8&event_type=PERSON"
app_live_url: "{{ app_base_url }}/live?channel=8&event_type=PERSON"
```

The notification should:

- show the snapshot thumbnail
- open the event in the app when tapped
- offer `View Event Clip`
- offer `View Live Stream` for person events
- offer `Unlock Front Door` for doorbell events

## Common Questions

- Use `channel=0` for the first NVR channel.
- Start with `hours=48` if you are not sure when the event happened.
- `PERSON`, `DOORBELL`, `MOTION`, `ANIMAL`, and `VEHICLE` are the supported event filters.
