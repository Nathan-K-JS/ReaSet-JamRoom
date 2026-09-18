# Importer activity — v3.12

The importer now has one persistent status bar and an Activity view. The bar
stays visible when scrolling the library. View activity opens full details;
Back to songs restores the previous scroll position and keeps review fields.

## Everyday behavior

- Scans, searches and maintenance requests announce work immediately. Library
  scans disable dependent controls. Selection and mode changes use the loaded
  list instead of scanning again.
- Starting a library update opens Activity. A first new import opens Activity
  after the queue accepts it; adding another while reviewing keeps the review.
- Updates show the current song/stage, processed count, successes, failures and
  skips. Pause waits for the current song. Resume/retry uses the existing batch.
- Song results and technical logs expand on demand. Show only problems filters
  failed songs. Finished checks live in collapsed Recent results.
- Queued imports have separate named activity entries. Open song returns to the
  existing review/recovery controls. Draft autosave remains beside the review.
- Background completions do not move focus or clear review fields. Receipts and
  failures remain available until dismissed or superseded by another attempt.
- Lost communication retains last-confirmed activity and announces reconnection.
  Polling retries reads only. It never reissues an import, paid split or Apply.
- Reopening reconstructs imports and library work from the existing server
  journals. Transient search/scan notices are session-only. Closing Activity does
  not stop work; stopping the importer still uses existing recovery rules.

## Implementation

`tools/importer-activity.js` is a vanilla JS module served by the existing importer.
It centralizes request feedback, named import states and batch progress. It
shares concurrent identical requests and gives each caller its own Response.
Read-only searches/scans have a timeout; mutations are never blindly replayed.

`GET /api/updates/status` reads the current project's batch journal without
enumerating songs or calculating folder sizes. The chooser continues to use
`GET /api/updates` for explicit scans. Progress polling does not rebuild song
rows. Batch stage messages/logs are bounded and saved through the existing
per-job logging context. Existing project identity, playback, recording and
operation receipt guards remain in force.

The Activity bar occupies normal layout space and sticks to the viewport top.
Scroll padding follows its actual height. Detailed activity uses a separate
view, not an expanding overlay. Significant status changes have a polite live
region; elapsed timers and full logs are not repeatedly announced.

## Validation

Browser fixtures exercise delayed scans, long libraries, local-only selection,
stable checkbox focus, duplicate submissions, stale-scan failure, partial batch
failure, disconnect/reconnect, returning to the previous scroll position,
review-field preservation and reopening journaled work. Chromium covers desktop
and phone-sized layouts; WebKit covers an iPhone-sized and short viewport.
These are browser emulations, not physical phone/keyboard acceptance tests.

Backend tests prove status polling avoids song/source scans and stage messages
survive failures. The native REAPER append/playback check includes duplicate
Apply and wrong-project guards on disposable copies of the saved library.

Install with JamRoom Update.bat, restart the importer and refresh with Ctrl+F5.
