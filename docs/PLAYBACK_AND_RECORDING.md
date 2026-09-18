# Playback fixes and proposed recording workflow

## Delivered fixes

The tempo/key drawer now reserves its measured height in the song list and
sets the lower boundary of the Tracks, Lyrics and Chords panels. Its expanded
height is capped against the available viewport, including phone landscape.
Transport height and safe-area padding are measured rather than assumed.

The Tracks click row now includes click item and child-track mute state.
Previously, a generated click could be muted at item level while its PB bus
reported AUDIBLE. Tapping the disabled click enables the current song's click
items, child tracks and PB bus. Other songs' item mutes remain unchanged.
The command is rejected after a project/structure change and the display waits
for confirmed REAPER state. No output-routing restriction is added.

Click quality flags still install muted until explicitly enabled. Enabling an
existing click does not require reimporting the song. This fixes the hidden
item-mute path; the remote jam-room project's actual routing/solo state has
not been inspected. The local test project did not reproduce the reported silence.

Validation: browser geometry at desktop, phone portrait and landscape; browser
click command/confirmation; Lua enable and stale-command tests; live REAPER
scratch-project checks with the original library left unchanged.

## Proposal awaiting design approval

The repository's CLAUDE.md requires explicit approval before implementing a
non-trivial design. The following covers the volume and recording features;
neither is implemented in this checkpoint.

The recording proposal below incorporates the requested default input/track
template and explicit post-stop retry/keep actions. The instrument-by-instrument
live input list is still needed: existing design documents specify live channels
1–16 and the playback return map, but do not assign instruments to live inputs.

### Per-song playback volume

- Put a large accessible Playback volume slider above the backing controls in
  Tracks, with percentage, mute endpoint and a reset-to-65% action.
- Default songs to 65%; range 0–100%. This leaves upward adjustment room without
  treating 100% as a boost above the existing stem mix. It is manual song trim,
  not automatic loudness normalization.
- Multiply all musical stem levels by the same gain, preserving their relative
  mix and existing individual mute choices. Keep click and live inputs separate.
- Persist the setting in the REAPER project, keyed to stable song identity, so
  every tablet agrees and restarting restores it. Browser storage is insufficient.
- Prefer persistent per-song audio-item gain with a separately stored baseline,
  avoiding compounded adjustments and allowing native REAPER playback to work
  without browser timing. Apply only recognized backing audio in that song.
  Confirm the effect on existing FX/automation before adopting this implementation:
  item gain occurs before track FX. Do not change a song's recording takes.
- Import/update/restore must carry the setting forward and apply it once to new
  stems. Published values must reflect actual applied REAPER gain.

### Recording screen and session lifecycle

1. Cue a song and open Recording. Show the song, tempo/key, input availability,
   recording destination and any existing unfinished session.
2. On first use, offer **Set up recording tracks** using the jam-room input
   template and [initial X32 setup guide](RECORDING_SETUP.md). Create and name
   the dedicated recording tracks automatically, with their mono/stereo inputs
   already assigned. Reuse these tracks on subsequent visits. Show instrument
   names, arm buttons and input meters; put wiring changes in a separate Setup
   view. Never arm the original stems. Default to X32 hardware monitoring.
3. Arm the instruments to capture. Record creates a new pass with optional
   two-bar count-in. Implement audible count-in in REAPER, using the current
   effective tempo and time signature, without shifting the library timeline or
   playing the preceding song. Validate native preroll/metronome support first.
4. Pause suspends the recording transport; Resume continues at that position.
   Stop closes the pass, retains all media and opens the take-review screen
   below. Starting another pass from the song start retains the previous pass
   unless the musician explicitly chooses Discard & re-record.
5. Audition a selected pass with independent original-stem and recorded-instrument
   mute controls. Only the selected pass plays by default. Recording mutes and
   rehearsal backing choices are distinct and restored when leaving audition.
6. Save as recording project exports the chosen session's passes plus ALL original
   stems, including currently muted stems, to a new self-contained project folder.
   Present the result/path and make opening the new project an explicit action.

### Default instrument and track template

- Build the shipped default from the actual jam-room input list, including
  physical socket/stagebox, X32 channel, USB input, mono/stereo pairing and
  instrument name. Do not infer live inputs from the backing-return slot map.
- Create one named recording track for each mono source or confirmed stereo
  pair, beneath a Recording folder. A multi-mic instrument has separate tracks
  for each mic, with an optional group arm control (for example, Drums).
- Track names follow `REC <instrument/mic>`; users see just the friendly name.
  Stable internal tags identify ownership independently of later renaming.
  Store the edited rig template in project state so all tablets see the same map.
- Setup is repeatable: reuse matching owned tracks, create missing ones, and
  preserve existing takes, names and user-edited routing. Report conflicts or
  unavailable inputs rather than silently assigning a different input.
- Keep the input assignments fixed between songs. Starting a take snapshots the
  armed inputs, names and format so later setup edits cannot reinterpret old takes.
- Verify each input with a meter before the first take. Keep REAPER software input
  monitoring off by default when the X32 provides the live monitor mix. Route
  recorded playback to the intended existing instrument return buses through an
  explicit template mapping; do not infer it from the USB input number.

### Stop → review → next take

**Terminology:** a *track* is an instrument/mic lane. A *take* is one complete
recording pass across all armed tracks. Keep/discard applies to the entire pass,
including segments created by Pause/Resume. Instruments stay synchronized.

After REAPER confirms Stop, show a review card in the Recording screen:

```text
Take 03 · 3:42 · 6 instruments                     Saved in session

[ ▶ Listen ]

[ Keep & record another ]       [ Discard & re-record ]

[ Finish recording ]            [ ☆ Mark favourite ]
```

This is an inline screen, not a modal covering the controls. Show “Finishing
take…” until REAPER has closed and registered its recording items. Do not offer
retry before the take is captured in the session manifest. Show “Saved in session”
only after persisting both the project and session record successfully; report
save failures while retaining the captured media and allowing a save retry.

| Action | Result |
| --- | --- |
| Listen | Play this pass from its start with current backing/recording audition choices. Stop listening returns to the same review card. |
| Keep & record another | Retain this pass, return to the song's recording start, run the selected count-in and start the next take using the same armed inputs. |
| Discard & re-record | Mark only this latest pass discarded, remove it from normal audition/export selection, return to the same start and begin again with the same count-in and armed inputs. |
| Finish recording | Keep the pass and return to the session's take list, where it can be auditioned or exported later. |
| Mark favourite | Add an optional star to help choose between retained takes; it does not discard or mute other material by itself. |

Use a prominent filled Keep button and a separate, clearly labelled outlined
Discard button, both with generous touch targets. Keep their positions fixed.
Do not auto-start a new take on Stop, show a routine confirmation dialog, or
require naming each take. Assign monotonically increasing take numbers, even
after discarding; optional notes and names are available in the take list.

Discard is reversible within the session: retain its files and item metadata,
with **Restore discarded take** available after stopping. Do not use REAPER's
general Undo command, which could undo unrelated work. If the next take cannot
start, show the reason and leave the discarded pass recoverable. Preserve the
decision before beginning the next recording. Kept passes remain the default;
navigating away from review never discards anything.

The take list shows number, duration, recorded instruments, favourite and selected
audition state. Audition one whole pass at a time by default; older takes remain
silent during another recording. If armed inputs change, the next pass shows its
actual instrument set; it does not silently borrow missing instruments from an
earlier pass. Detailed comping between instruments/passes can be done in the
exported REAPER project. Export includes all kept passes and original stems;
discarded passes are excluded unless restored first.

**Professional workflow references:** Logic Pro's
[advanced recording commands](https://support.apple.com/en-nz/guide/logicpro/lgcpb19d5875/10.7/mac/11.0)
include a command that deletes the current recording, returns to its start and
records again. Ableton's [take lanes and audition workflow](https://www.ableton.com/en/manual/comping/)
retain passes and allow one lane per track to be auditioned at a time. These
inform the retry and comparison model above; ReaSet's two-button layout,
whole-band take selection and recoverable discard are our design choices.

### Export, recovery and transport integration

- Save session identity, owned track/item GUIDs, pass boundaries, source files and
  export progress in persistent project state. Recover an unfinished session after
  restart; do not infer ownership merely from an item's position or track name.
- Persist kept/discarded status and favourite state with each pass. A retry is
  one idempotent bridge command: apply the decision to its identified latest
  pass, then start at most one new take. Duplicate taps or another tablet must
  not discard an older pass or start multiple recordings.
- Copy media first. Build the destination project in a separate project instance,
  retaining track routing/FX, take offsets/rates, and the tempo/key/playrate needed
  for the recorded audio to line up with the backing. Rebase the song to zero.
  Give the exported project its own identity and omit setlist automation/session
  commands. Exported multichannel routing should remain usable on the rig.
- Saving an RPP alone does not copy its media. Explicitly verify destination media
  and the reopened project: source references, item/take counts and alignment.
  Only then remove precisely the exported recording items from the setlist and
  save it. Keep a recovery snapshot and receipt; export failure leaves the session
  available for retry. Preserve disk originals until an explicit cleanup action.
- Prevent double record/export requests from multiple tablets. Commands carry
  project/session identity and unique request IDs; the Lua bridge is authoritative.
- While recording, suppress normal song chaining, skip/loop jumps, automatic cues
  and seek commands. Stop at the session/song boundary rather than recording into
  another song; do not impose rehearsal auto-stop behavior on count-in or audition.
- Detect native REAPER stop/project changes and disconnections; never show an
  optimistic recording light. Ordinary performance and recording remain local and
  do not depend on the optional importer server being available.

The REAPER API provides input enumeration, track/input/arm controls and project
save/state functions. Exact count-in/pause and media-copy behavior still require
scratch-project proof before the feature is considered supported:
[official ReaScript API](https://www.reaper.fm/sdk/reascript/reascripthelp.html).

### Implementation checkpoints after approval

1. Obtain the actual live input list and finalize the default tracks and initial
   X32 setup guide. Prove the volume persistence/import interactions and recording count-in,
   pause/resume and export alignment in isolated REAPER projects.
2. Implement and verify per-song gain, including native playback and song updates.
3. Implement the session bridge and Recording screen with persistent recovery.
4. Implement audition and verified export/cleanup; inject copy/save failures and
   project switches to prove originals survive and retries cannot duplicate takes.
5. Test two simultaneous tablets, normal playback regressions, restart recovery,
   discard/restore, repeated retries, changed arm selections and actual multichannel
   audio capture. Publish through the standard update branch.
