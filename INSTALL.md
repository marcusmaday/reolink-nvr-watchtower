# Installation

## Home Assistant Add-On

1. Add the repository to Home Assistant.
2. Install **Reolink Enhanced API** from the add-on store.
3. Open the add-on configuration page.
4. Set your NVR host, username, password, and port.
5. Start the add-on.

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

