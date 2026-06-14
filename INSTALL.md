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
nvr_host: 192.168.50.42
nvr_port: 80
nvr_username: admin
nvr_password: your_password
nvr_ssl: false
buffer_enabled: true
buffer_size_seconds: 60
clip_duration_before: 5
clip_duration_after: 5
retention_days: 7
max_storage_mb: 5000
debug: false
```

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

The app also registers its own NVR webhook on startup when the NVR supports it, so the timeline stays in sync without a Home Assistant relay.
If your LAN uses an unusual network layout, set the add-on's `webhook_base_url` option so the NVR can reach the app directly.
