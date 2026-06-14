# Installation

## Home Assistant Add-On

1. In Home Assistant, go to `Settings` -> `Add-ons` -> `Add-on Store`.
2. Open the three-dot menu and choose `Repositories`.
3. Add this repository:

```text
https://github.com/marcusmaday/reolink-nvr-ha-app
```

4. Install **Reolink Enhanced API** from the add-on store.
5. Open the add-on configuration page.
6. Set your NVR host, username, password, and port.
7. Start the add-on.

Recommended starting values:

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
clip_duration_before: 5
clip_duration_after: 5
clip_quality: medium
retention_days: 7
max_storage_mb: 5000
external_storage_path: ""
allow_cors: false
debug: false
```

The `api_port` option controls the app's listening port in the add-on. If you change it, keep the add-on port mapping aligned and use the same port in the relay URL.
`clip_quality` controls which RTSP stream is used for generated clips. `high` uses the main stream; the other values use the sub stream.

## Local Docker

If you want to run the service outside Home Assistant:

```bash
docker compose up -d
```

The API will be available at `http://localhost:5000`.

## After Installation

1. Confirm `/api/health` returns `status: ok`.
2. Confirm `/api/device/info` shows your NVR.
3. Run a search for a known date range.
4. Open `/docs` for the interactive API browser.

## Home Assistant Notifications

The app is designed to work with existing Home Assistant automations. The easiest setup is to import the blueprint instead of hand-editing an automation file.

Import this blueprint in Home Assistant:

```text
https://raw.githubusercontent.com/marcusmaday/reolink-nvr-ha-app/main/blueprints/automation/reolink_enhanced_notification.yaml
```

Then create the automation from the blueprint and choose:

1. Your doorbell sensor
2. Your person sensor
3. Your camera snapshot entity
4. Your front door lock
5. Your two `notify` services
6. Your remote app base URL

Use placeholders for your remote Home Assistant URL. Do not hard-code a private Nabu Casa URL in shared docs.

This blueprint also handles the `UNLOCK_DOOR` notification action, so you do not need a separate unlock automation when you use it.

To keep the app timeline in sync, add this one `rest_command` block to Home Assistant `configuration.yaml` once:

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

Use that IP with the configured app port. This is an internal Home Assistant network address used by the add-on, not your public remote-access URL.
