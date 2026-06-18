# Quick Start

Use this if you want the shortest path to a working setup.

## 1. Add The Repository

In Home Assistant:

1. Go to `Settings` -> `Add-ons` -> `Add-on Store`
2. Open the three-dot menu and choose `Repositories`
3. Add:

```text
https://github.com/marcusmaday/reolink-nvr-ha-app
```

## 2. Install The Add-On

Install **Reolink Enhanced API**, then open its configuration and set:

```yaml
api_port: 5000
api_host: 0.0.0.0
nvr_host: 192.168.50.42
nvr_port: 80
nvr_username: admin
nvr_password: your_password
nvr_ssl: false
buffer_enabled: true
buffer_size_seconds: 60
clip_duration_before: 10
clip_duration_after: 5
clip_quality: medium
retention_days: 7
max_storage_mb: 5000
external_storage_path: ""
allow_cors: false
debug: false
```

Restart the add-on after saving.

## 3. Import The Blueprint

Import this blueprint into Home Assistant:

```text
https://raw.githubusercontent.com/marcusmaday/reolink-nvr-ha-app/main/blueprints/automation/reolink_enhanced_notification.yaml
```

Create the automation from the blueprint and choose:

- doorbell sensor
- person sensor
- snapshot camera
- front door lock
- two `notify` services
- app base URL

Use a placeholder for your remote-access URL in any shared examples.

## 4. Add The Relay Command

Add this to `configuration.yaml`:

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

Find `HA_GATEWAY_IP` with:

```bash
ip route | awk '/default/ {print $3}'
```

`APP_PORT` defaults to `5000`.

Restart Home Assistant Core after adding the command.

## 5. Check It

Open the app from the Home Assistant dashboard button and trigger a test doorbell or person event.

What you should see:

- a notification with a snapshot thumbnail
- a tap action that opens the app
- an event clip in the app timeline
- live view for person notifications
- unlock for doorbell notifications

## 6. If Something Is Off

- No events in the app: check the `rest_command` and restart Home Assistant Core.
- Clips start too late: make sure you are on the latest add-on version and use the current buffer defaults.
- Mobile opens a login page: use the notification links from the blueprint, not a raw browser URL.
