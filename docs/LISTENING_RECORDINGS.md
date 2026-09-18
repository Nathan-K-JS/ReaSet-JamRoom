# Leave with a listening recording

Status: delivered in v3.11; simplified to MP3-only sharing in v3.11.1.

## Using it

Keep **JamRoom Importer.bat** open on the room PC. In ReaSet's Record tab,
stop a take, choose instrument mutes, then **Make listening copy**. Confirm
whether to include backing. **Listening copies** shows queued work and completed
copies; open a ready copy to listen, download the MP3, or show its room-Wi-Fi QR.
Saved and exported takes have the same action. Making a copy does not clear the
setlist, discard takes, or replace multitrack export.

Use **Download MP3** to save the recording on your phone.
Safari downloads are in the iPhone/iPad Files app's Downloads folder; Chrome on
Android has a Downloads screen. The page includes saving instructions and a
copy-link fallback that works on local HTTP without requiring the native Share
or Clipboard APIs. Audio never autoplays. Files remain playable away from home;
the local link requires the same Wi-Fi and a running room PC/service.
[Apple download help](https://support.apple.com/en-nz/102440),
[Chrome Android download help](https://support.google.com/chrome/answer/95759?co=GENIE.Platform%3DAndroid&hl=en).

## Implementation and limits

- REAPER freezes each request beside the setlist in `.RPP.recordings/Listening/`.
  Its snapshot captures one take, backing choices, item timing/pitch/gain and
  recording mutes. Current backing item settings and parent mutes are captured
  when that song is still in place; otherwise its recording-time snapshot is used.
- The service discovers roots through REAPER's published recording index. Its
  registry and private worker configuration live in `imports/.listening/`.
  Keep that directory along with the recording storage. It contains the stable
  share-link registry, not just disposable importer cache.
- One independent REAPER worker uses its own settings directory and **Dummy Audio**,
  no web control surface, below-normal process priority, and no hardware sends or
  armed tracks. A Windows job object closes the worker if its parent service dies.
  It does not open tabs in the performance instance. This isolation was proven
  on the test workstation's REAPER 7.75; the room remains a separate installation.
- Shared byte-verifying media copy code secures source files in the listening job.
  Existing discard/export cleanup retains source files, so it cannot invalidate
  pending requests. Never change recording cleanup to erase those files without
  adding coordination with these jobs.
- A flat dry stereo mix avoids double-summing the room's folder buses. Its saved
  template, `imports/.listening/mix-template.json`, starts at unity/centre for all
  14 inputs and is frozen per request. Stereo pairs stay stereo. Room/IEM faders
  and desk processing are not captured. Custom sends, active automation, FX or
  layered/section-source items produce an explicit manual-mix message instead of
  silently losing processing. Audition this starting balance with real room takes;
  it is not an automatic instrument-balancing system.
- Native dry-run analysis rejects near-silence. REAPER renders 48 kHz/24-bit stereo
  WAV, targeting -16 LUFS and a -1 dBTP ceiling, with at most 18 dB of gain increase.
  The service verifies duration, channels, decodability and peaks, then encodes
  256 kbps MP3 from that WAV. Musical pauses are kept. No artificial effects tail
  is added to this dry-file template. WAV is an internal intermediate, never a
  sharing option, and is removed after the MP3 is verified and published.
- Jobs resume after restart. The internal render survives an MP3 failure; Retry
  encodes it without repeating the render. A copy becomes available only when its
  MP3 is ready. Existing MP3 share links survive the upgrade; old WAV endpoints
  are unavailable. Each new copy has its own link. Replace share
  link revokes the old token; Remove listening copy removes its published audio
  and indexed private media copies, leaving original multitracks and audit metadata.
- Share endpoints serve only indexed outputs, with Safari/Chrome byte-range and
  HEAD support, audio MIME types, UTF-8 filenames, and attachment downloads.
  QR codes are generated locally. Opening from localhost uses the detected LAN
  address; opening from a phone uses that address. Reopen after an address change.
  The page has no room-control buttons. Access follows the existing trusted-LAN
  model; this is not a public internet hosting/authentication service.

Automated checks cover HTTP range/HEAD behavior, downloads, Unicode, revocation,
restart recovery, WAV retention on encoding failure, responsive layouts, and
playback/seeking/downloading in Chromium with Android emulation and WebKit with
iPhone emulation. Native checks use synthetic mono/stereo signals to verify
chosen mutes, backing inclusion, no click, tempo/pitch handling, post-export
copies and unchanged performance transport. **Physical Android/iPhone camera
scanning and saving on the actual room Wi-Fi remain an on-site acceptance check.**

Update with **JamRoom Update.bat**, restart REAPER and JamRoom Importer, then
refresh ReaSet with Ctrl+F5. The normal dependency check installs the local QR
library. No song-library rebuild is needed.

Release verification: 192 automated tests; native recording/recovery/export and
import/playback checks; four native listening mixes (with backing, without it,
one instrument muted, and after export), all preserving the original project.
Visual captures: `imports/.visual/listening-v311/`. Test tools:
`python -m unittest discover -s tools -p 'test_*.py' -q`,
`python tools/verify_listening_live.py`, `python tools/verify_recording_live.py`.

On-site check: use an actual iPhone and Android on room Wi-Fi, scan the QR, play
and seek, download the MP3, then turn Wi-Fi off and play the saved recording. Verify
that guest Wi-Fi can reach the PC; try a real four-mic and band take to assess mix
balance. Browser emulation does not verify camera apps or the room's router.

The sections below preserve the approved design and acceptance criteria.

## Musician workflow

1. Stop a take. It is already saved, as today.
2. Listen and choose the existing recording/backing instrument mutes. Press
   **Make listening copy** on this take (also available beside saved takes).
3. A small confirmation card shows the take name, **Include backing** (Song
   recordings only), and **Make copy**. Click and count-in are excluded by default.
   Use the audition mutes as the starting choice; do not stack all kept takes.
4. The card progresses through Queued / Making copy / Ready, then offers an
   audio player, **Download MP3**, and **Share in room**.
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

Output: a stereo 256 kbps MP3, made from a private 48 kHz / 24-bit render.
Aim for -16 LUFS integrated, with a -1 dBTP ceiling. Avoid
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
then atomically publish the MP3 and receipt. An internal render survives
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
