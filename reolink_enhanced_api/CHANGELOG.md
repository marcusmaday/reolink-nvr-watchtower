# Changelog

# Changelog

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
