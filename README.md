# Reolink Enhanced API

Reolink Enhanced API is a Home Assistant app and REST service for browsing Reolink NVR recordings, pulling event clips, and exposing a searchable timeline.

## What It Gives You

- Search recordings by date, channel, and event type
- View a timeline of recent person, motion, vehicle, animal, and doorbell events
- Open a live event dashboard at `/app` that jumps straight to the newest alert
- Generate clip URLs for playback or download
- Run as a Home Assistant app or as a local Docker service

## Repository Layout

```text
.
├── app/            FastAPI app and NVR integration code
├── reolink_enhanced_api/ Home Assistant app metadata and startup script
├── integration/    Optional Home Assistant custom integration
├── Dockerfile      Local development image
├── docker-compose.yml
├── README.md
├── QUICKSTART.md
├── INSTALL.md
└── API.md
```

## Start Here

1. Add the repository in Home Assistant: `Settings` -> `Add-ons` -> `Add-on Store` -> `Repositories`.
2. Install **Reolink Enhanced API**.
3. Configure your NVR connection in the Home Assistant app or in `.env` for local Docker.
4. Start the service.
5. Open the dashboard at `http://localhost:5000/app`.
6. Open the API docs at `http://localhost:5000/docs`.
7. Try a search.

```bash
curl "http://localhost:5000/api/search?channel=8&start_date=2026-06-11&event_type=PERSON&stream=main"
```

## Everyday Use

### Search recordings

Use `/api/search` to find recordings for a channel and date range.

- `event_type=PERSON`
- `event_type=DOORBELL`
- `event_type=MOTION`
- `event_type=ANIMAL`
- `event_type=VEHICLE`

### Check recent activity

Use `/api/timeline` to review recent events in time order.

```bash
curl "http://localhost:5000/api/timeline?hours=48&channel=8&event_type=PERSON"
```

### Verify the system

```bash
curl http://localhost:5000/api/health
curl http://localhost:5000/api/device/info
curl http://localhost:5000/api/channels
```

## Configuration

Common settings:

- `NVR_HOST`
- `NVR_PORT`
- `NVR_USERNAME`
- `NVR_PASSWORD`
- `NVR_SSL`
- `BUFFER_ENABLED`
- `BUFFER_SIZE_SECONDS`
- `CLIP_DURATION_BEFORE`
- `CLIP_DURATION_AFTER`
- `RETENTION_DAYS`
- `MAX_STORAGE_MB`
- `DEBUG`

For Home Assistant app installs, these are supplied through the app options UI.

## Home Assistant Notifications

The intended workflow is to ingest `PERSON` and `DOORBELL` events into the app, then route mobile notifications back into the app UI.

The easiest setup is to import the Home Assistant blueprint instead of editing automation YAML directly:

```text
https://raw.githubusercontent.com/marcusmaday/reolink-nvr-ha-app/main/blueprints/automation/reolink_enhanced_notification.yaml
```

That blueprint lets you choose the sensors, lock, phone notification services, and the remote app URL from the Home Assistant UI.
It also handles the `UNLOCK_DOOR` action from the notification button, so it replaces the separate unlock automation.
The app now registers its own NVR webhook on startup when supported, so new events appear in the app without a Home Assistant relay.

Use placeholders in shared examples instead of a real remote-access URL:

```yaml
app_base_url: "https://YOUR_HA_REMOTE_URL/app/reolink_enhanced_api"
```

Recommended notification behavior:

- snapshot thumbnail in the notification
- tap opens the event in the app
- `PERSON` actions: `View Event Clip`, `View Live Stream`
- `DOORBELL` actions: `View Event Clip`, `Unlock Front Door`

## Troubleshooting

- `NVR not connected` means the app could not reach the camera system.
- Empty search results usually mean the date range or event type does not match recordings on the NVR.
- If `/api/timeline` is empty, run a search first so matching events are indexed.
- If you are testing locally, make sure the container can reach the NVR on the network.

## More Details

- [QUICKSTART.md](QUICKSTART.md) for a fast install path
- [INSTALL.md](INSTALL.md) for app and Docker setup
- [API.md](API.md) for endpoint details
