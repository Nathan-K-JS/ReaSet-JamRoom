# Leave with a listening recording

Status: proposed implementation plan. Requested after the v3.10 UX review;
the listening-copy feature is not implemented by that release.

## Musician workflow

1. Stop a take. It is already saved, as today.
2. Listen and choose the existing recording/backing instrument mutes. Press
   **Make listening copy** on this take (also available beside saved takes).
3. A small confirmation card shows the take name, **Include backing** (Song
   recordings only), and **Make copy**. Click and count-in are excluded by default.
   Use the audition mutes as the starting choice; do not stack all kept takes.
4. The card progresses through Queued / Making copy / Ready, then offers an
   audio player, **Download MP3**, **Download WAV**, and **Share in room**.
5. Share shows a QR code and copyable local link. Friends on the room Wi-Fi open
   a simple listening/download page. Once downloaded, the file plays elsewhere.

Keep recording, discarding/retrying, and multitrack export as separate actions.
Making a listening copy must not clear the setlist or delete its source takes.
It must work before or after multitrack export. Do not force people to understand
REAPER project exports just to get a file they can listen to.

Favourites help pick takes, but never silently select which take gets rendered.
Each card names the precise take. Making another copy after changing the mix
creates a new version, so an existing shared link continues to mean the same file.

## What the listener hears

This is a useful rehearsal mix, not automatic studio mastering or an IEM capture.
Recorded inputs route directly to X32 hardware outputs in the current project
(`B_MAINSEND=0` in `ReaSet_RecordingCore.lua`). An ordinary master render would
omit them. The recording files also do not necessarily contain desk EQ, effects
or IEM balance; processing is included only if present in the captured audio or
deliberately reproduced in the listening mix.

Build a dedicated stereo mix from exactly one selected take and, optionally,
the original backing stems. Preserve stereo pairs, timing, take offsets, song
playback speed/pitch, item gain and the confirmed song-level trim. Respect chosen
mutes. Exclude the click, count-in, other takes and unrelated songs. Detect unsupported
external-hardware FX/routing instead of producing a silently incomplete mix.

Start with a saved listening-mix template for the 14 default recording inputs.
It supplies sensible fixed gains/pans without changing room or IEM levels. Review
that template with actual room recordings; loudness normalization alone cannot
balance four microphones against drums. If adjustment is needed, first expose
**Voices/instruments versus backing** balance, with preview and rerender. Avoid
adding a full mixer, effects editor or timeline to the web UI.

Proposed output defaults: stereo 48 kHz / 24-bit WAV plus a 256 kbps MP3 made
from that same WAV. Aim for -16 LUFS integrated, with a -1 dBTP ceiling. Avoid
aggressive gain on near-silent recordings; report no usable audio instead. These
are listening-copy defaults to validate by listening, independent of the existing
-23 LUFS song-library matching. Retain musical pauses; trim only known capture
boundaries and provide a short effects tail, not automatic silence removal.

## REAPER and local-service responsibilities

- Extract the existing recording export's snapshot/copy/verification operations
  into a reusable builder. A listening snapshot is non-destructive and independent
  of the export receipt/cleanup operation. The live setlist is never the render target.
- Freeze take identity, media, mute choices and mix settings in a persistent job.
  Verify media ownership, readability and source revision before accepting it.
  Source deletion/export cannot invalidate a queued job: first secure a verified
  snapshot, or hold cleanup until that snapshot is durable.
- In the render project, explicitly build one stereo route for each included
  signal, disable hardware sends and recording/monitoring, and exclude duplicate
  parent/send paths. Keep audio processing only where its route is supported and
  understood. Do not blindly sum every copied bus and its children.
- Use REAPER's native offline renderer. Prefer a separate REAPER worker instance
  with its own config and no audio-device access, so a render does not stall the
  room controller. **This isolation must be proven first on the installed REAPER
  version.** If it cannot be guaranteed, queue for an idle room with an explicit
  visible wait state; never start a blocking render during performance.
- REAPER's official API exposes master rendering, explicit bounds, channels,
  sample rate, loudness normalization and true-peak limiting. This supports the
  proposed render configuration; it does not prove our worker/process isolation.
  [REAPER ReaScript API](https://www.reaper.fm/sdk/reascript/reascripthelp.html#GetSetProjectInfo)
- Use the existing local Python service for persistent job scheduling, progress,
  file verification, MP3 encoding and listening/download pages. Audio mixing and
  rendering remain REAPER's job. Integrate service startup/health into the existing
  launcher/setup so the UI explains availability without sending musicians to a terminal.
- Serve the share page on that service's own origin to avoid requiring the REAPER
  web interface to proxy audio or opening broad cross-origin access. The controller
  opens a session-specific page; a local queue/REAPER bridge supplies confirmed
  state. Use the existing local ranged-audio serving as a starting point.

No new cloud account, cloud upload or database is needed. Ordinary rehearsal and
recording must continue working if the optional listening/download service is off.

## Persistence, sharing and failure handling

Journal jobs and results under the project's recording storage with stable IDs.
States: queued, preparing, rendering, encoding, verifying, ready, interrupted,
failed. Poll confirmed state; a timeout is not a signal to render again. One render
worker at a time, with idempotent requests and resumable jobs after restart.

Write to temporary paths, validate duration/channels/decodability and peak/loudness,
then atomically publish the final files and receipt. A completed WAV can survive
an MP3 encoder failure; retry just encoding. Low disk, missing media, interrupted
render or verification failures leave the source recordings intact and explain
the next action. An empty take never becomes a render job.

Serve only indexed ready files using unguessable share tokens, not arbitrary
filesystem paths. A read-only share page cannot control playback or recording.
Generate QR images locally; no external QR service. Use the PC's reachable LAN
address, handle range requests/download filenames, and show “same room Wi-Fi;
room PC must be on”. Rebuild QR URLs if the PC's address changes. A downloaded
file needs no server; the local link is not an internet hosting service.

Copies remain until explicitly removed. Removing a copy does not remove the
multitracks; removing a share link revokes that link. List ready copies alongside
saved recordings, with friendly song/take/date names and file sizes. Reopening the
app restores queued work and ready downloads without another export ritual.

## Build order and acceptance checks

1. **Prove rendering:** render known mono/stereo recordings and optional backing in
   an isolated project; verify non-silent expected signals, no click, no doubled
   buses, correct speed/pitch, no X32 output and unchanged live-project state.
   Establish and test the worker isolation before promising background operation.
2. **Durable backend:** snapshot builder, operation journal, native render driver,
   verification/encoding, restart recovery and cleanup coordination. Test both
   unexported takes and archived recording projects.
3. **Small UI:** Make listening copy, mix summary, progress, preview and downloads.
   Persist audition choices at submission. Test four-mic a cappella, stereo band
   jam, song backing, multiple kept takes, muted instruments and quiet inputs.
4. **Share:** local QR page, ranged playback, safe download endpoints and revocation.
   Verify Android/iPhone playback and saving on the actual room Wi-Fi, including
   guest/client-isolation failures and changed PC addresses.
5. **Recovery and release:** force-close at each stage, fill disk, remove a source,
   retry encoding, submit twice, start room playback while a job is queued, export
   the source while preparing, and reopen after shutdown. Confirm no lost takes,
   no changes to room routing, and no optimistic “Ready” state.

A later enhancement could offer “Make copies of favourites” for the whole evening.
Start with one explicitly chosen take to establish mix quality and reliability.
