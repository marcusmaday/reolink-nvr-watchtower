# Testing & Verification

This project does not use a large unit-test suite for day-to-day validation. The useful checks are the ones that prove the add-on, the relay, and the clip pipeline still work together.

## Local Validation

Run the recorder validation script against the NVR:

```bash
python3 scripts/validate_rolling_buffer.py --channel 8 --seconds 12 --segment-seconds 2
```

Use the values from `.env` if you want to override the defaults:

```bash
NVR_HOST=192.168.50.42
NVR_PORT=80
NVR_USERNAME=admin
NVR_PASSWORD=...
NVR_SSL=false
```

What to look for:

- the script connects to the NVR
- it resolves a usable RTSP URL
- it writes `.ts` segments
- it exits cleanly after the timed capture

## Home Assistant Validation

After changing the app or HA config:

1. Restart Home Assistant Core.
2. Restart the add-on.
3. Trigger a fresh `PERSON` or `DOORBELL` event.
4. Confirm the app logs show `POST /api/events/ingest 200 OK`.
5. Confirm the event appears in the app timeline.
6. Confirm the notification opens the app, not the browser login page.

## Clip Validation

For clip timing and buffering:

- check `/api/debug/info`
- `rolling_buffer.segments` should be greater than `0`
- the app logs should show `Rolling buffer selected ...` for buffered clips
- if you see `Direct RTSP fallback`, the clip used the late fallback path

## Common Failures

- `segments: 0` in `/api/debug/info`
  - the recorder is running but no files are being recognized yet
- `POST /api/events/ingest` never appears
  - the HA relay is not reaching the app
- notification opens the browser login page
  - the link is using a raw web URL instead of the Companion App deep link
- dashboard iframe spins on mobile
  - use the direct app launch button instead of the iframe dashboard
