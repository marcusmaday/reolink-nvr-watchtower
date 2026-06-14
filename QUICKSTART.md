# Quick Start

Use this path if you want the service running quickly and do not need the full background on the project.

## 1. Set Up The NVR Connection

In Home Assistant add-on settings or your local `.env`, set:

```bash
NVR_HOST=192.168.50.42
NVR_PORT=80
NVR_USERNAME=admin
NVR_PASSWORD=your_password
NVR_SSL=false
```

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
    url: "{{ app_url }}/api/events/ingest"
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

The blueprint supplies `app_url` from the same remote app base URL you already entered for notification links.

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
