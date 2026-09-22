# Recording parts and reliable starts — v3.16

Implemented from [the approved plan](RECORDING_UPGRADES_PLAN.md). See
[Recording setup](RECORDING_SETUP.md) for X32 routing and the musician workflow.

## What changes

- Opening Record prepares REAPER's configured audio device before input checks.
  Connecting, unavailable and reconnect states replace the need to play/stop a
  song first. Silence is not treated as a missing input. Background device-close
  preferences are saved temporarily and restored when leaving recording; the
  driver and channel mappings are not changed.
- Two-bar count-in and capture share one native Record transport. Record starts
  before the first click, so no browser/Lua timer starts capture on the downbeat.
  The native red recording indicator during count-in is intentional.
- Recorded parts have independent names, Hear switches and saved volume sliders.
  Sliders apply and save on release; Reset restores the original recording-track
  level. These controls affect review, overdub accompaniment and MP3 export.
- **Add another part** plays the selected arrangement while recording newly
  selected inputs. Reusing the same microphone creates a separate part track.
  **Redo new parts** retries the newest pass; **Discard new parts** returns to its
  parent arrangement. Earlier performances remain recoverable.
- **Keep & record another** remains an independent alternative take. Choose any
  kept arrangement to build a different version. MP3 export renders the selected
  combination; multitrack export retains separate parts and kept alternatives.

For free jams, the first pass runs until Stop. Added parts can stop at the previous
arrangement's end or continue past it. Click and two-bar count-in are separate
choices. Song overdubs use the session's original start, playback rate and pitch.
Record input selection is independent of which existing parts are audible.

## Implementation and recovery

The count-in uses the planned timeline fallback. A temporary area beyond library
media holds accompaniment copies and generated count-in audio, routed through
the existing PB CLICK destination and level. All preparation finishes before
transport starts. Library songs stay in their original positions.

The journal stores capture origin and lead-in before recording. After Stop,
recorded items are aligned to the original song start and their lead-in is hidden
using source offsets. Raw source files remain intact. Temporary items are removed,
original mutes/options restored, and the cursor returns to the session start.
Recovery uses the same alignment, including interrupted recordings.

Physical inputs and recorded parts have different IDs. Each pass owns its new
parts and references inherited parts; each arrangement has its own saved mix.
Only new destination tracks are armed. X32 hardware monitoring remains the live
monitor path. Empty generated part tracks are removed during session cleanup.

Version-1 recording journals migrate to version 2 with a permanent
`index.v1.json` backup. Existing MP3 requests remain supported. Exported/deleted
sessions receive metadata migration without adding their tracks to the setlist.
MP3 rendering still uses the isolated REAPER worker. Source recordings are only
removed from the setlist after multitrack export is saved and verified; source
audio files remain recoverable.

## Verification

Validated on the development workstation, not the room's X32:

- Native REAPER capture, pause/resume, count-in cancellation, changed playback
  speed, restart recovery, independent takes, discard/restore and verified export.
- Four instrument parts followed by two vocals through the same input: six
  separate performances, previous parts disarmed but audible during overdubbing,
  saved mix after restart, and discard returning to the previous arrangement.
- Forty actual software audio captures at 240 BPM/normal speed and 137 BPM/80%
  speed, with starts at zero and later in the project and deliberate controller
  stalls. Maximum measured count-in/backing boundary error was 0.514 ms; measured
  spread was 0.118 ms. This measures the software capture path, not X32 latency.
- Decoded MP3 checks verified relative part attenuation, a same-input harmony,
  backing selection and click exclusion. The performance transport was unchanged.
- Browser checks cover independent playback/record controls and phone/tablet
  widths; importer append/playback and duplicate/wrong-project guards still pass.

Repeatable checks: `tools/verify_recording_live.py`,
`tools/verify_recording_timing.py`, `tools/verify_listening_live.py`, the Python
unit/browser suite, and `tools/verify_import_playback.py` with `--queue-guards`.
Run native project verifiers sequentially against a stopped, saved test project.

## Room acceptance after updating

1. Run `JamRoom Update.bat`, restart REAPER and the importer, and refresh ReaSet.
2. From a cold start, open Record without playing a song. Confirm the selected
   X32 inputs become available and show levels with REAPER in the background.
3. Record several on-beat starts with count-in, including a changed song speed.
   Check physical input/output latency with the actual X32 buffer configuration.
4. Keep a vocal, add a second vocal through the same mic, adjust their relative
   levels, and compare Listen with an exported MP3.

Physical X32 cold-start behaviour and round-trip latency still require these
room checks. This release provides whole-part overdubbing from the beginning;
punch-ins, comping, EQ, effects and detailed mix automation remain REAPER work.
