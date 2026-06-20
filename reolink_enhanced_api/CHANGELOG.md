# Changelog

## 0.4.31

- Route live links through the app root with `?view=live` so phones stay inside Watchtower without hitting ingress auth edge cases.
- Keep the app's live page header branded as Watchtower only.

## 0.4.30

- Keep live view inside Watchtower by linking event details and notifications to the app's `/app/live` route.
- Remove the standalone live label from the live page header.

## 0.4.29

- Point the live notification action at the Home Assistant camera dashboard instead of the app live route.
- Remove the standalone "Live" label from the live page header.

## 0.4.28

- Add a lightweight rolling-buffer watchdog that restarts the recorder task if it stops.
- Keep the rolling recorder logs readable by suppressing ffmpeg progress spam.

## 0.4.27

- Respect the configured clip window exactly instead of forcing a 10-second pre-roll floor.
- Silence ffmpeg stats spam from the rolling recorder.
- Align the add-on defaults with the current 1 second before / 15 second after setup.

## 0.4.26

- Rebrand the product to `Watchtower` and rename the repo and add-on slug for the larger HA migration.

## 0.4.25

- Bust cached snapshot previews and force the player to reload the newest event cleanly.

## 0.4.24

- Disable browser caching for the dashboard recent-events fetch so the newest event loads reliably.

## 0.4.23

- Sort the dashboard events client-side so the newest event always loads first.

## 0.4.22

- Force the dashboard to open the newest event on load.
- Remove the dead entry-id deep-link path from the web UI.

## 0.4.21

- Rename the visible app branding to `Front Door Watch`.
- Update the add-on panel title to match the app.

## 0.4.20

- Fix rolling-buffer segment discovery so buffered clips are recognized correctly.

## 0.4.19

- Stream ffmpeg output from the rolling recorder into the logs for easier diagnosis.

## 0.4.18

- Add rolling-buffer stats to the debug endpoint.
- Improve clip-builder diagnostics when no buffered segments are available.

## 0.4.17

- Retry buffered clip generation before falling back to direct RTSP.

## 0.4.16

- Re-encode the rolling RTSP recorder into short segments so the buffer produces usable files.

## 0.4.15

- Add more detailed rolling-buffer logging around clip selection and timing.

## 0.4.14

- Fix timestamp normalization in the rolling-buffer clip builder.
- Improve recorder diagnostics.

## 0.4.13

- Stamp relay events from the trigger time.
- Increase the buffered pre-roll window to keep clips aligned with the event.

## 0.4.12

- Improve the mobile layout so the player keeps more vertical room.

## 0.4.11

- Make the event list independently scrollable from the player.
- Compact the event metadata under the player.

## 0.4.10

- Restore the timeline index filename so existing event history loads again.

## 0.4.9

- Refresh the release version for the HA add-on update path.
