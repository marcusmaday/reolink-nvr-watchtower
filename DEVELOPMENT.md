# Developer Instructions

This document is for contributors and for local validation of the app and add-on.

## Repository Layout

```text
app/                  FastAPI application and core runtime logic
blueprints/           Home Assistant automation blueprint
integration/          Optional Home Assistant integration code
reolink_enhanced_api/ Home Assistant add-on metadata, build config, and startup script
scripts/              Validation utilities
```

## Local Runtime

The app can be run as a standalone service for development, but the Home Assistant add-on is the primary supported path.

Typical local environment variables come from `.env` or the add-on options:

- `NVR_HOST`
- `NVR_PORT`
- `NVR_USERNAME`
- `NVR_PASSWORD`
- `NVR_SSL`
- `API_HOST`
- `API_PORT`
- `BUFFER_ENABLED`
- `BUFFER_SIZE_SECONDS`
- `CLIP_DURATION_BEFORE`
- `CLIP_DURATION_AFTER`
- `CLIP_QUALITY`
- `RETENTION_DAYS`
- `MAX_STORAGE_MB`
- `EXTERNAL_STORAGE_PATH`
- `ALLOW_CORS`
- `DEBUG`

## Useful Commands

Run the app locally with your environment already set:

```bash
cd app
python -m uvicorn main:app --reload --host 0.0.0.0 --port 5000
```

Check syntax quickly:

```bash
python3 -B -c "import ast, pathlib; [ast.parse(pathlib.Path(f).read_text()) for f in ['app/main.py','app/config.py','app/rolling_buffer.py','app/timeline_index.py']]"
```

Validate the rolling-buffer recorder path against a real NVR:

```bash
python3 scripts/validate_rolling_buffer.py --channel 8 --seconds 12 --segment-seconds 2
```

## Add-On Notes

- `reolink_enhanced_api/config.yaml` is the add-on manifest and version gate.
- `reolink_enhanced_api/run.sh` is the add-on entrypoint.
- The add-on image must be published before Home Assistant can update to a new version.
- Keep the add-on version in `config.yaml` aligned with the image tag published by CI.

## Fast Refresh in Home Assistant

When you are iterating on the add-on and the package version has already been published, the quickest way to pull the new build into Home Assistant is:

```bash
ha store reload
ha store apps update 15e0e6e5_reolink_enhanced_api
```

The `15e0e6e5` prefix is Home Assistant Supervisor's internal app id for this add-on. It appears in the add-on URL and in HA's internal device registry; it is not a repository setting and you normally do not edit it by hand.

## Editing Guidance

- Prefer small, direct changes in `app/` first.
- Update the add-on manifest and startup script when app options change.
- Keep user-facing setup details in `README.md`, `INSTALL.md`, and `QUICKSTART.md`.
- Keep implementation history and debugging notes out of the user docs.
