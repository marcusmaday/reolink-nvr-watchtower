# Advanced Setup

This repository is organized for two main paths:

- End users should start with [README.md](README.md), [QUICKSTART.md](QUICKSTART.md), and [INSTALL.md](INSTALL.md)
- Developers should work from `app/`, `addon/`, and `integration/`

## Current Repository Layout

```text
.
├── app/            FastAPI backend and NVR search logic
├── addon/          Home Assistant add-on files
├── integration/    Optional Home Assistant custom integration
├── docker-compose.yml
├── Dockerfile
├── config.yaml
└── run.sh
```

## Local Development

### Run the API

```bash
docker compose up -d
curl http://localhost:5000/api/health
```

### Useful Endpoints

```bash
curl http://localhost:5000/api/device/info
curl http://localhost:5000/api/channels
curl "http://localhost:5000/api/search?channel=8&start_date=2026-06-11&event_type=PERSON"
curl "http://localhost:5000/api/timeline?hours=48&channel=8"
```

## Notes For Contributors

- Keep the API and the Home Assistant add-on aligned.
- Prefer changes in `app/` first, then update the add-on and docs.
- Use the top-level README and quick-start docs for user-facing wording.

