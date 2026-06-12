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

## 2. Start The Service

### Home Assistant add-on

Install the add-on, fill in the options, and start it from the add-on page.

### Local Docker

```bash
docker compose up -d
```

## 3. Check That It Works

```bash
curl http://localhost:5000/api/health
curl http://localhost:5000/api/device/info
curl http://localhost:5000/api/channels
```

## 4. Search Recordings

```bash
curl "http://localhost:5000/api/search?channel=8&start_date=2026-06-11&event_type=PERSON&stream=main"
```

If you want all recordings for a day, omit `event_type`.

```bash
curl "http://localhost:5000/api/search?channel=8&start_date=2026-06-11"
```

## 5. View The Timeline

```bash
curl "http://localhost:5000/api/timeline?hours=48&channel=8"
```

## Common Questions

- Use `channel=0` for the first NVR channel.
- Start with `hours=48` if you are not sure when the event happened.
- `PERSON`, `DOORBELL`, `MOTION`, `ANIMAL`, and `VEHICLE` are the supported event filters.

