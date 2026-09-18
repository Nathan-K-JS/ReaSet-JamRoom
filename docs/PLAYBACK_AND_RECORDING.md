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
2. Configure named mono/stereo inputs using the actual REAPER audio device.
   Inputs 1–16 are the rig default, not a hardcoded limit. Reuse saved instrument
   labels and mappings. Create dedicated tagged recording tracks; never arm the
   original stem tracks. Default to the X32's existing hardware monitoring.
3. Arm the instruments to capture. Record creates a new pass with optional
   two-bar count-in. Implement audible count-in in REAPER, using the current
   effective tempo and time signature, without shifting the library timeline or
   playing the preceding song. Validate native preroll/metronome support first.
4. Pause suspends the recording transport; Resume continues at that position.
   Stop closes the pass and retains all media. Starting another pass from the
   song start retains the previous pass rather than overwriting it.
5. Audition a selected pass with independent original-stem and recorded-instrument
   mute controls. Only the selected pass plays by default. Recording mutes and
   rehearsal backing choices are distinct and restored when leaving audition.
6. Save as recording project exports the chosen session's passes plus ALL original
   stems, including currently muted stems, to a new self-contained project folder.
   Present the result/path and make opening the new project an explicit action.

### Export, recovery and transport integration

- Save session identity, owned track/item GUIDs, pass boundaries, source files and
  export progress in persistent project state. Recover an unfinished session after
  restart; do not infer ownership merely from an item's position or track name.
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

1. Prove the volume persistence/import interactions and recording count-in,
   pause/resume and export alignment in isolated REAPER projects.
2. Implement and verify per-song gain, including native playback and song updates.
3. Implement the session bridge and Recording screen with persistent recovery.
4. Implement audition and verified export/cleanup; inject copy/save failures and
   project switches to prove originals survive and retries cannot duplicate takes.
5. Test two simultaneous tablets, normal playback regressions, restart recovery,
   and actual multichannel audio capture. Publish through the standard update branch.
