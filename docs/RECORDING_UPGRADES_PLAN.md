# Recording reliability, playback balance and overdubs

Status: implementation plan, 22 September 2026. No runtime changes in this update.
This builds on the existing local REAPER controller, X32 input template,
recoverable recording sessions and MP3 sharing service.

## Decisions

1. Prepare the audio device before validating inputs or counting in.
2. Put count-in and recording on REAPER's audio timeline, removing the timed
   handover from preview audio to a separate Record command.
3. Introduce independent recorded parts and a saved mix, then build the sliders
   and overdub workflow on that shared model.
4. Keep ordinary independent takes. Add **Add another part** for overdubbing;
   do not silently turn **Keep & record another** into layering.
5. Support reusing any physical input, including recording several vocal or
   guitar parts through the same input. Every part has its own playback control.
6. Keep **Export recording** as the MP3 action. Export the selected arrangement,
   while multitrack export also preserves kept alternative takes for later editing.

## What the current code establishes

| Area | Current behaviour | Consequence |
| --- | --- | --- |
| Count-in | `RecordingCore:count_in()` plays a separate SWS preview and sets a wall-clock deadline. `tick()` starts native recording after that deadline. `ReaSet_Recording.lua` runs controller ticks at 100 ms intervals. | The last click and first recorded beat do not share a scheduled transition. The timer alone can add roughly one polling interval, with additional delay under load. This is a concrete design flaw, though the room's actual delay has not been measured. |
| Inputs | `arm()` rejects selected inputs against `GetNumAudioInputs()` before arming them. `state()` uses the same count for every unavailable label. There is no device-opening step. `park()` disarms owned tracks. | Closed/not-yet-open audio can look identical to missing hardware. The reported Play/Stop workaround is consistent with this; it does not prove the X32 driver is the only cause. |
| Review | One selected take is audible; recording mutes are keyed by input ID and reset when entering review. | Two different performances through one input cannot have independent persisted controls. |
| MP3 | Requests snapshot one take. The render worker already reads an optional `mix` map, but the request builder does not supply a saved mix. | Sliders need durable state and matching audition/render behaviour, not just visible controls. |
| Multitrack export | Reconstructs tracks from the original backing snapshot and unmutes the latest kept take. | New overdub tracks and a combination of parts need explicit reconstruction and selection. |
| Recovery | Version-1 journals, item chunks and ownership checks protect original audio. | Migration, gains and generated tracks must preserve those protections. |

## 1. Audio readiness and input meters

Opening Record, returning from review/export, or preparing an overdub should
run one readiness procedure while native transport is stopped:

1. Publish **Connecting recording inputs…** immediately; preserve input choices.
2. Check device status. Use REAPER's `Audio_Init()` to open configured devices
   if closed, then recheck input count, channel names and configured ranges over
   a bounded interval. This does not change driver or routing.
3. Establish the owned input-meter/arm state, with REAPER software monitoring off.
4. Publish **Ready** only when selected recording destinations are usable.
   Silence is valid: readiness must never require nonzero meter readings.
5. If initialization fails, show one actionable device message and **Reconnect
   inputs**. Missing template tracks and individual out-of-range mappings get
   distinct messages, rather than declaring every channel unavailable.

Use the same procedure before every capture, including retry and overdub. Watch
device loss while the screen is open; back off retries and preserve the current
take if it happens during recording. Never close/reopen audio during playback,
recording or an active export operation in the performance process. Do not use a
hidden Play/Stop cycle as the remedy.

Investigate REAPER's background-device-close preference on the room PC. If a
temporary setting override is needed to keep the recording screen ready, scope
and journal it with the existing recording option restoration. Do not repeatedly
force global preferences or restart audio on every state poll. Hardware IEM
monitoring stays on the X32. Reported meters going dead after other actions are
part of this readiness lifecycle regression coverage.

## 2. Continuous count-in and recording

The invariant is **no Lua, browser or wall-clock-triggered Record command at the
first musical beat**. Device initialization, directory creation, track creation,
backing preparation and recovery checkpoints finish before the first click.

First implementation task: prove REAPER's native metronome/pre-roll recording
path in a disposable project on the installed version. Prefer native pre-roll
with capture already prepared, including pre-roll audio capture where needed.
REAPER must own the transition; browser count numbers only reflect its position.
Native count-in and pre-roll are documented REAPER features, but their exact
combination and routing must pass these checks before choosing the final settings:

- Two bars at the session's actual tempo, time signature and playback rate.
- Correct behaviour at project time zero, at a later song boundary, and when a
  song begins between project bar lines. Preserve the existing chosen musical
  start; do not move library songs to fit a convenient bar boundary.
- Route the count through the current PB CLICK destination and level, including
  the room outputs when configured. Temporarily restore all metronome settings.
- No preceding setlist song leaks into a pre-roll. Continuous free-jam click
  starts on the same grid without a second overlapping metronome.
- Count-in on/off and continuous click on/off remain independent.
- Capture early attacks where possible; keep raw pre-roll audio recoverable and
  exclude the lead-in from normal playback/export using explicit offsets.

If native pre-roll cannot meet boundary/routing requirements, use a prepared
recording area with timeline click and recording running before musical zero;
do not fall back to another preview/timer handoff. That fallback requires a
separate review of copied backing, timeline offsets and isolation before coding
the wider overdub workflow. Do not shift the entire setlist to create lead-in.

Count-in cancellation should leave no visible empty take, while retaining any
ambiguous interrupted files for recovery. Disable Pause during count-in; Stop
always works. During capture, Pause/Resume must pause/resume the shared playback
and recording timeline together. Genuine CPU underruns remain possible; the fix
removes the avoidable transition delay, not every possible hardware dropout.

## 3. Shared session, part and mix model

Keep the familiar word **take** for an attempt and **part** for a recorded
instrument performance. Internally separate:

| Record | Purpose |
| --- | --- |
| Session | Song/free-jam identity, timeline origin, backing snapshot, tempo/meter/rate/key, export/recovery ownership. |
| Pass | One press of Record, potentially capturing several selected inputs. Owns a set of new parts and its recovery folder. |
| Part | One mono or stereo performance, stable ID, source input ID, destination track GUID/specification, media/items and optional name. |
| Arrangement | The parts chosen to play together. Independent takes are separate arrangements; adding a part creates a new revision of the selected arrangement. |
| Mix | Part gain/mute, backing enable/stem mutes, and selected arrangement, saved per session/arrangement. |

A stereo EAD10 or keys recording remains one part/slider. Selecting four mics
produces four parts in one pass. Reusing Vox 1 creates another unique part; it
does not replace the first merely because the input ID matches.

Create dedicated REAPER destination tracks for new parts before capture; older
parts stay on disarmed playback tracks. The permanent 14-input template remains
the setup/routing source. Never arm both a template and its new destination for
the same capture. New tracks inherit the configured mono/stereo input and playback
return, but not accidental arm state or duplicated hardware sends. Playback and
capture must work simultaneously even when several parts share one source input.

Replace the assumption that input ID uniquely identifies every recording track
with explicit input/part ownership lookup. Playback tracks need stable stored
specifications because they will not exist in an older backing snapshot. Create
missing owned part tracks during recovery/export; do not duplicate them on restart.

Migrate version-1 sessions transactionally, preserving a readable backup. Each
legacy take becomes an independent arrangement with one part per recorded input;
do not mix all old takes together. Default new gains to unity and existing mutes
to their known saved state. Previously transient review mutes cannot be recovered
after shutdown. Preserve existing source paths, export receipts and operation IDs.
Support already queued version-1 MP3 requests as well as new requests.

## 4. Playback sliders

Under **Playback**, show one row per recorded part: name, Mute switch, horizontal
volume slider and readable level/reset. Put these controls in the normal review
screen; keep setup/input mappings in Setup. Long lists scroll inside the reserved
panel space and controls wrap cleanly on phones.

- Default 0 dB / original playback level. Proposed range: silence to +12 dB,
  logarithmic travel, a clear unity position, and **Reset**. Existing sessions
  must not become quieter on upgrade.
- One saved gain per part, not per physical input. It affects review, previously
  recorded accompaniment during overdubs, and the MP3 export snapshot.
- This changes recorded playback only, never X32 preamp/input gain or the live
  musician's hardware monitoring. Part returns still feed the room/IEM mix.
- Use the same relative mix coefficients in audition and export. The existing
  MP3 loudness normalization may change overall loudness; X32 EQ/fader settings
  are not reproduced in an export.
- Apply gain once against a captured baseline. Do not multiply the current value
  repeatedly, bake it into source audio, or apply it both to item and worker track.
- Coalesce rapid slider updates; acknowledge final values, retain focus while
  polling, and persist settled changes. Do not synchronously save the entire RPP
  on every pointer movement. Show save errors and restore pending mix state.
- Publish compact part summaries and separate live meter updates; do not send
  every historical item chunk over the browser link on each meter tick. Keep
  large sessions usable without imposing a small fixed number of overdubs.
- Make expected gain/mute edits compatible with item-chunk recovery/cleanup
  verification without weakening detection of unrelated native REAPER edits.

First release has level and mute only. Pan, EQ, effects, editing and automation
are outside this upgrade; the existing stereo inputs retain their stereo image.

## 5. Solo overdub workflow

The current quick jam remains: choose inputs/click/count-in, Record, Stop, Listen,
then keep, discard, export or finish. Review adds **Add another part**:

1. Select the take/arrangement to build on and press **Add another part**.
2. Expand an inline **Record next part** area, keeping the playback mix above it.
   Choose inputs here, including inputs already used. Start with no newly armed
   inputs so a prior full-band selection is not accidentally recorded again.
3. The summary says, for example, **Recording: Guitar 1 · Playing: Bass, Keys +
   backing**. Existing parts/backing can be muted or balanced. Distinguish
   **Record these inputs** checkboxes from **Hear these parts** switches.
4. Press **Record part**. Apply the session timing, initialize/arm only the new
   destinations, count in, then record against the selected older parts/backing.
   All passes begin at the arrangement's musical start in this first release.
5. Stop autosaves the new pass and previews the combined arrangement. New parts
   are highlighted so a musician knows what the next discard/retry will affect.
6. **Keep & add another part** opens input selection again. **Redo new part**
   retains the previous accompaniment and reuses just the current capture inputs.
   **Discard new part** restores the prior arrangement without starting recording.
   With several selected inputs, these actions affect the entire newly captured
   pass; label this **new parts** in the plural when appropriate.
7. Repeat, then **Export recording** exports the complete chosen arrangement.

An example using one microphone: record guitar through Guitar 1; add lead vocal
through Vox 1; add harmony through Vox 1 again. The resulting rows are Guitar 1,
Vox 1, Vox 1 (2), with optional rename to Guitar, Lead vocal, Harmony. Both vocal
parts play independently, use separate sliders and survive export.

**Keep & record another** continues to create an independent take without
playing the previous take. A compact **More** menu can hold that alternative in
overdub mode. Never merge alternatives implicitly or make users choose a special
solo mode before their first recording. Allow returning to an earlier saved
arrangement and building from there without destroying later work.

### Timing, length and editing limits

- Lock session timing and backing identity while overdubbing. If global song
  tempo/key has changed, offer returning to the session settings or starting a
  separate session; do not stretch/pitch the recorded parts silently.
- Song-backed overdubs finish at the song end. First free-jam pass ends manually;
  subsequent overdubs default to stopping at the arrangement end. A free-jam-only
  **Stop at end** toggle may be turned off before recording to extend the jam.
  Shorter parts leave silence after their end; extending does not stretch them.
- Free jam without a click is supported; later parts follow the audible first
  performance. Adding a click does not infer or quantize a rubato recording.
- Start-from-cursor, punch-in, looping/comping and automatic best-take assembly
  are deferred. Whole-part retry covers the initial workflow; native REAPER
  remains available after multitrack export for detailed editing.
- Capture only selected hardware inputs. Prior playback is not re-recorded
  digitally; the X32 input patch stays as documented. Software monitoring stays
  off, so the player hears their live instrument through the X32.

## 6. Recovery, export and state transitions

Journal an overdub intent before native Record: parent arrangement revision,
new pass/part IDs, selected inputs, track specifications, media path, musical
origin, pre-roll offset, and accompaniment mix snapshot. Duplicate browser
commands must not create duplicate parts. Reject stale project/session revisions.

On restart, recover the new pass without replacing the last complete arrangement.
An interrupted part is marked **Recovered — check recording**; uncertain media
is retained. Closing the browser does not stop native capture. Done and normal
setlist playback park all recording parts silent. Existing housekeeping/export
reminders still cover the complete session, including unfinished overdubs.

Discard removes new parts from the selected arrangement recoverably. Older
arrangement references keep their source media alive. Session deletion remains
separate from discarding a new pass. Stop, native Stop, count-in cancel, a lost
device, controller restart and project switch must each restore temporary
metronome/mute/arm settings and leave the journal consistent.

MP3 requests use a versioned immutable manifest of the selected parts, gains,
mutes, timing and backing. Later slider edits cannot change an export in progress.
Extend worker reconstruction beyond its one-take/input-ID assumption. Keep the
isolated Dummy Audio worker, resumable service, MP3-only downloads and existing
Android/iPhone sharing flow. Generated click/count-in are omitted; any acoustic
click captured by a microphone remains part of the recorded audio.

Multitrack export reconstructs all required part tracks, source media and backing
with the selected arrangement audible and other kept alternatives parked/muted.
Save enough session/mix metadata to understand the arrangement when reopening.
Verify files, item timing, part count and selected mix before clearing source
items from the setlist. Disk-full, missing-media or render failures retain the
session. Basic gains must remain editable in the exported project.

## Implementation order and acceptance

| Step | Deliverable | Required evidence |
| --- | --- | --- |
| 1 | Shared device readiness and meter lifecycle | Cold start, browser-only control, foreground/background, return after song/review/export; no Play/Stop workaround; unplugged hardware gets an actionable error. |
| 2 | Native timing proof, then count-in replacement | Loopback measurement of repeated starts at time zero/later regions, slow/fast tempo, rate changes, multiple buffers and CPU load. No missing first attack or variable timer-sized gap. Verify at least 20 starts per representative condition and report actual timing spread. |
| 3 | Versioned part/arrangement/mix model and track ownership | Existing sessions reopen and sound the same; interrupted migration recovers; repeated initialization does not duplicate tracks. |
| 4 | Saved review sliders and export mix | A known part attenuation produces the expected relative change in audition and rendered audio; same-input parts remain independent; mute, reset and restart persistence work. |
| 5 | Add-part capture and review | Guitar, bass, lead and harmony sequentially; repeated Vox 1; four-mic first pass; stereo inputs; song/free-jam and all click combinations; retry/discard affects only the new pass. |
| 6 | Recovery and full exports | Crash during prepare/count-in/capture/finalize, repeated commands, queued export then shutdown, missing files and failed copies. Combined MP3 and reopened RPP retain the intended parts/timing/balance. |
| 7 | Room acceptance and release | X32 cold-start and physical loopback/monitoring checks; phone portrait/landscape/tablet controls, large part lists, live slider feedback; ordinary song playback and original test library unchanged. |

Design the part/mix schema before implementing sliders so they do not need to be
rewritten for overdubs. The independent readiness/count-in fixes can ship first
once their own checks pass. Use the existing Lua, Python and Playwright test
infrastructure plus disposable native REAPER projects. Native output-capture
tests on this workstation do not substitute for real X32 input-latency checks.
Compare successive overdubs for accumulated alignment error; correct driver
latency/calibration at the source rather than guessing a fixed timer offset.
The digital scheduling target is an exact sample boundary. For physical-loopback
acceptance, measure the residual after REAPER's reported latency compensation:
target no more than 1 ms variation across repeated starts at each tested device
configuration, with no increasing offset over successive overdubs. Measure and
calibrate a consistent fixed hardware offset separately. A larger or variable
residual blocks the timing release until explained; do not declare success based
on the animated countdown.

Primary code touched during implementation: `ReaSet_RecordingCore.lua`,
`ReaSet_Recording.lua`, `ReaSet_FreeJam.lua`, `ReaSet.html`,
`ReaSet_RecordingExport.lua`, `ReaSet_Listening.lua`,
`jamroom_listening_worker.lua`, associated recovery tests and recording setup docs.
Use small Lua helpers for readiness/timing and session mix rather than duplicating
state changes across commands. No framework, cloud service or new audio engine.

## References

- [REAPER API reference](https://www.cockos.com/reaper/sdk/reascript/reascripthelp.html#Audio_Init):
  `Audio_Init`, `Audio_IsRunning`, input enumeration and input/output latency APIs.
- [REAPER User Guide](https://www.reaper.fm/userguide.php): native recording,
  metronome, count-in and pre-roll; implementation must verify installed-version
  behaviour and X32 output routing rather than assume all options compose.
- [Existing recording setup](RECORDING_SETUP.md) and
  [MP3 export implementation](LISTENING_RECORDINGS.md).
