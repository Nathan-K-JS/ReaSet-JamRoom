# Playback and recording

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

## Recording and playback volume release

The **Tracks** screen now has a song-specific playback-volume slider, initially
**65%**. It adjusts all recognized backing stems together while preserving their
relative levels. The click and newly recorded instruments retain their own levels.
The setting lives in the REAPER project, works during native playback, and is
reapplied once to newly imported/replaced backing items. Item gain is before track
FX; this is a backing trim, not a final output limiter or automatic loudness match.

The **Record** tab provides the approved X32 template, remembered input selection,
meters, optional two-bar count-in, Record, Pause/Resume and Stop. Stop saves the
whole pass automatically. Listen reviews one pass at a time; Backing/Recording
and expandable instrument mutes control audition. Keep & record another retains
the pass; Discard & re-record parks that pass recoverably. Done returns to the
normal song screen. Song changes, loop/seek automation and library mutations
are guarded while recording or reviewing. Native Stop also finalizes the take.

Startup reconciliation runs in REAPER without needing a browser. It restores
indexed takes missing from an older project save, discovers recoverable audio
from an interrupted capture, and parks the recordings silent with inputs
disarmed. Pending sessions produce **Review recordings / Later**. The saved list
supports favourites, optional names, individual/batch export, recoverable delete,
and restoring a discarded pass. Ambiguous interrupted media is retained and
marked for review in REAPER; it is never guessed into a successful export.

**Export & clear from setlist** creates a separate REAPER project containing all
kept passes plus the original backing stems, including muted stems and the click.
It preserves the recorded speed/pitch, shifts the song to zero, copies and
byte-verifies media, then reopens the new project and checks alignment, pitch,
rate and media references. Only after that succeeds does it remove the session's
owned recording items from the setlist and save. Failed export keeps the source
takes. The result path and **Open in REAPER** button remain in Saved recordings.

### Start using it

1. Run **JamRoom Update.bat**, restart REAPER, and refresh ReaSet on each browser.
   The registered startup action must be the installation's
   `Requirements/ReaSet_Startup.lua`; it now launches the recording/volume bridge.
   If Record reports the controller unavailable, run that file from the REAPER
   action list. A previously copied standalone startup file may need updating.
2. Follow [Recording setup](RECORDING_SETUP.md) once to verify X32 inputs and
   REAPER output returns. The controller automatically creates and saves the
   recording template once the saved Jam Room project is stopped. Open Record
   and select instruments. Setup can still create missing tracks manually.
3. Cue a song, Record, and Stop. The take is already saved; export can wait.
   Use Done to move on, or Listen / Keep another / Discard & re-record.

### Storage and first-release limits

- Recording storage is automatically beside the saved setlist:
  `<setlist.RPP>.recordings/`. It contains the session journal and its previous
  version, backing snapshots, per-pass audio folders, and `Exports/`. Back up this
  folder along with the setlist and imported audio. The first release uses this
  fixed location rather than adding another folder-selection workflow.
- Delete and discard clear/park project items recoverably; they do not erase raw
  audio from disk. No automatic expiry or disk-purge button is included. Exported
  folders contain their own media and can be copied as complete folders.
- This records one selected song, with an automatic stop at its boundary. For
  free-form jams, punch-ins, comping and detailed mixing, use native REAPER.
- Count-in uses an SWS audio preview routed to the first PB CLICK hardware send
  (or output 1 if that bus is absent), at the song's detected tempo and current
  speed/signature. It does not play the preceding song. The transition into
  recording is controller-timed, not a sample-accurate native preroll; count-in
  can be disabled. Generated click audio itself is unchanged.
- Export handles ordinary file-backed audio. Nested/section sources or missing
  media stop export with the original recordings retained. Detailed manual edits
  to managed recording items also stop automatic cleanup rather than losing edits.
- Closing a tablet does not stop recording. If the controller is disconnected,
  use native REAPER Stop. On a power loss, recovery depends on audio that REAPER
  actually flushed to disk; unfinished/corrupt media may need native recovery.

### Verification

Automated browser checks cover command confirmation, duplicate/pending Stop,
chunk delivery during changing state, offline controls, song-scoped gain, and
phone/tablet drawer geometry. Lua checks cover tempo isolation, recording locks,
loop cleanup in the owning project, and refusing song deletion with saved takes.

The opt-in `tools/verify_recording_live.py` runs native recording in a disposable
REAPER tab: count-in, two inputs, pause/resume, repeated keep/retry, 80% song speed,
restart/older-project/interrupted-media recovery, review mutes, delete/restore,
failed export, verified export, duplicate/stale tablet commands and project scope.
It confirms the original loaded project and cursor remain unchanged. On this
workstation it uses native track-output capture when hardware inputs are absent;
this does **not** validate physical X32 recording or the IEM/room mix.

Import/playback regression checks also passed using a disposable copy of the
populated library. Real X32 input identification, latency and audition levels
remain an initial jam-room setup check. Forced power-off/disk-full recovery has
not been tested; failure injection and interrupted-session reconstruction have.

## Approved recording direction and final usability review

Nathan approved the recording plan, with the direction to keep ReaSet a simple,
functional web controller for the existing REAPER setup. This final pass refines
that approved direction; no further general design approval is needed. Recording
and per-song volume are implemented as described above; the design notes remain as context.

The recording proposal below incorporates the requested default input/track
template and explicit post-stop retry/keep actions. Nathan's supplied live input
list is now recorded in [RECORDING_SETUP.md](RECORDING_SETUP.md): 14 recording
tracks covering inputs 1–16, with stereo EAD10 (9/10) and Keys (11/12).
Physical local/stagebox sourcing and the current USB patch remain unverified.

### Product boundary: one recording screen, REAPER does the work

REAPER owns audio capture, recording transport, media, takes and project saving.
ReaSet provides named input selection, transport, whole-take review and project
handoff. Use native REAPER capabilities wherever they support this workflow;
the bridge supplies session ownership, confirmed state and safe export orchestration.
Do not build an audio engine, waveform editor, timeline, plugin rack, comp editor,
or separate browser mixer. Detailed editing, overdubbing and mixing belong in the
exported REAPER project. Keep one workflow for casual and serious use, without
"simple/pro" modes or separate feature trees.

### Two use cases and the friction to remove

| Situation / likely annoyance | Design response |
| --- | --- |
| Friends want to record before the moment passes. | After initial setup: cue song, open Recording, press Record. Remember selected instruments and count-in choice; show them immediately without a wizard. First use requires selecting inputs once. |
| The first attempt falls apart. | Stop → Discard & re-record returns to the same start with the same inputs and count-in. No naming or confirmation dialog; the discard remains recoverable. |
| It was fun, and everyone wants to play the next song. | Stop keeps the take automatically. Done returns to rehearsal; export is optional and can wait. Returning to a song finds its saved takes. |
| Someone thinks a take was lost because the tablet slept. | Recording continues in REAPER. Reconnection reads actual transport/session state, and restores the review screen after a native Stop. Never claim the tablet stopped REAPER while disconnected. |
| A serious take is spoiled by an unnoticed wrong input. | Named inputs with compact signal/clip indicators and a clear armed count. Show unavailable selected inputs before Record; silence alone is not an error. Input routing is configured once in Setup. |
| Comparing attempts requires clicking many instrument controls. | A take selector changes the whole synchronized pass. A small favourite star and optional take name help identify the best performance. Listen resumes the review choices; no per-instrument take assembly in the browser. |
| The recording and backing double each other during playback. | Review offers independent Backing and Recording on/off controls, with instrument mutes in an expandable detail area. Start from the backing mix used during the take; old recording passes remain silent. |
| Export interrupts the rehearsal or loses work. | Save project uses an automatic song/date/session folder and includes all kept takes plus original stems. Show progress and a reusable result path; open it only when requested. Copy/verify precedes setlist cleanup. |

**Scope:** the first release records the selected song. This makes its backing,
tempo and export boundaries unambiguous. Free-jam recording was added in v3.8
([workflow](FREE_JAM_RECORDING.md)); a one-tap stereo sharing mix remains a later
addition. A saved session is enough to keep a casual
recording; a self-contained REAPER project is the handoff for serious work.

### Visible controls by state

| State | Main controls | Secondary details |
| --- | --- | --- |
| Ready | Song, selected instruments, compact meters, Record, Count-in Off / 2 bars | Takes; Setup; Additional inputs |
| Recording / paused | Confirmed recording status, elapsed time, Pause / Resume, Stop | Input activity and clipping; no setup or take changes |
| Review | Listen / Stop, Keep & record another, Discard & re-record, Done | Take selector; expandable backing/recording instrument mutes |
| Saved takes | Select take, Listen, Record another, Save project | Favourite, optional name, Restore discarded take |

Count-in defaults to two bars and remembers an Off choice. Pause resumes the
same pass; Stop completes it. Use the same transport controls consistently:
the existing Stop button must stop recording too, and normal Play during review
must use audition behavior rather than invoke setlist chaining. A compact global
recording indicator and Stop remain available if the user visits another tab;
navigation alone does not end recording. Guard song/seek changes while recording
with a direct explanation, not an apparently broken button.

Setup holds input/output mapping; the release uses automatic recording storage beside the setlist. The normal screen
shows instrument names and useful state, not channel numbers, file paths or
bridge diagnostics. Show the saved path after export. Surface actionable errors
in place (for example, "Keys input unavailable" or "Project could not be saved").

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
   remembered selections and any existing unfinished session. Save the setlist in its intended location; sessions and takes are named automatically.
2. On first use, automatically create the recording tracks in a saved, stopped
   Jam Room project (with a manual setup fallback), using the jam-room input
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
6. Done keeps the take and returns to rehearsal; changing songs does not require
   export or a discard decision. The song's takes remain available on returning.
   **Save project** exports the chosen session's kept passes plus ALL original
   stems, including currently muted stems, to a new self-contained project folder.
   Present the result/path and make opening the new project an explicit action.

### Default instrument and track template

- Use the confirmed track table in [RECORDING_SETUP.md](RECORDING_SETUP.md):
  Vox 1–4, Bass, Guitar 1–2, Utility Mic, stereo Drums EAD10, stereo Keys and
  Spare 1–4. Create all 14 tracks disarmed; Utility Mic and spares appear under
  Additional inputs. Each stereo pair uses one track and one arm control.
- Build the shipped default from that jam-room input list, including
  physical socket/stagebox, X32 channel, USB input, mono/stereo pairing and
  instrument name. Do not infer live inputs from the backing-return slot map.
- Create one named recording track for each mono source or confirmed stereo
  pair, beneath a Recording folder. Use the supplied EAD10 stereo pair directly;
  no drum-mic grouping UI is needed for this rig.
- Track names follow `REC <instrument/mic>`; users see just the friendly name.
  Stable internal tags identify ownership independently of later renaming.
  Store the edited rig template in project state so all tablets see the same map.
- Setup is repeatable: reuse matching owned tracks, create missing ones, and
  preserve existing takes, names and user-edited routing. Report conflicts or
  unavailable inputs rather than silently assigning a different input.
- Keep the input assignments fixed between songs. Starting a take snapshots the
  armed inputs, names and format so later setup edits cannot reinterpret old takes.
- Remember the selected instruments between visits and songs. Distinguish that
  saved selection from confirmed REAPER arm state: setup/restart must not silently
  arm inputs. Reapply the selection when entering Ready, then confirm native arm
  state before Record. Restore managed arm/monitoring state when leaving recording
  mode after Stop. Never change unrelated user tracks silently.
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

[ Done ]
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
| Done | Keep the pass and return to rehearsal. Takes remain accessible from Recording, without requiring export. |

Use a prominent filled Keep button and a separate, clearly labelled outlined
Discard button, both with generous touch targets. Keep their positions fixed.
Do not auto-start a new take on Stop, show a routine confirmation dialog, or
require naming each take. Assign monotonically increasing take numbers, even
after discarding. Optional names and a small favourite star live in the take
list, rather than adding another decision to the post-stop card. Omit a separate
notes editor from the first release.

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

The following is implementation responsibility, not another set of controls or
steps the musician must manage.

### Walking away: saved sessions and startup housekeeping

**No export button is required to preserve a take.** Stopping a recording saves
it automatically. Done only changes the screen; closing the browser or leaving
the room does not discard anything. Export creates the separate working project
and permits cleanup of the rehearsal project. It is not the initial save.

Save recordings in a dedicated folder per session under the configured recording
root, separately from imported stem media. Before capture, persist the session's
identity, song, armed-input map and intended media location. After each completed
take, persist its item/take metadata, audio references and project state. Keep a
small session record on disk as well as project metadata so recovery does not
depend entirely on the last manual save of the setlist RPP. Write session records
atomically and retain the previous valid record.

On REAPER bridge startup or opening a rehearsal project, reconcile that project's
session records with its owned recording items and media. This must work without
a browser connected. Include incomplete capture, failed exports and completed
exports whose setlist cleanup was interrupted. A browser connecting later displays
the existing result; refreshing a tablet does not start another cleanup operation.
Do not depend on a browser close event or a shutdown dialog being answered.

When unfinished sessions exist, show one dismissible startup notice:

```text
Recordings to tidy up
3 song sessions · 8 takes awaiting export

[ Review recordings ]                         [ Later ]
```

Review opens a short list grouped by song and recording date, with take counts,
saved/recovery status and these actions:

| Action | Result |
| --- | --- |
| Listen | Open the existing take-review controls for that session. |
| Export & clear from setlist | Save and verify a self-contained recording project, then remove only that session's owned recording items from the rehearsal project and save it. |
| Delete session | Confirm the named session/take count, then remove its owned recording items and put its session data/media in recoverable Deleted recordings. Never touch imported stems. |
| Later | Keep the session safely stored and silent; continue rehearsal immediately. |

Allow selecting several sessions for Export or Delete in this same list. Export
creates one project per session and reports results individually: a failed session
stays pending even if others succeeded. Do not begin project-changing export or
cleanup during playback/recording. A small **Saved recordings (N)** entry remains
on the Recording screen after Later. Acknowledge the notice for the current
project-open session across tablets; do not nag on each refresh or song change.
Remind again on the next project startup while unresolved sessions remain.

**A clean rehearsal project means recordings cannot affect normal song playback.**
Completed takes are parked silent and managed recording tracks disarmed on leaving
recording mode. On startup, reconcile and silence owned pending recordings before
normal ReaSet playback is enabled. Keep this state in the saved project too; the
browser must not be responsible for preventing old takes from playing. Retain the
reusable empty recording-track template after cleanup. Never delete by track name,
song range or file age; ownership identifies exactly what can be removed.

Later intentionally leaves recoverable pending items in the project. Do not
silently relocate or delete them merely to achieve an empty setlist. Successful
export or explicit Delete clears them. Deleted recordings remain accessible from
a secondary recovery action; permanent deletion is a separate explicit operation,
with no automatic age-based purge. This keeps the common path to two decisions:
export the recordings worth keeping, or delete those no longer wanted.

For an interrupted recording, inspect the session's known media and recover what
REAPER can read, labelling the result **Recovered — check take**. Do not claim
that an unfinished or damaged file is complete. Missing media or ambiguous
ownership must be shown for review, never "fixed" by deleting the session. A
verified export receipt lets startup finish interrupted setlist cleanup without
creating another export or deleting anything whose identity/content has changed.

### Implementation safeguards

- Save session identity, owned track/item GUIDs, pass boundaries, source files and
  export progress in persistent project state. Recover an unfinished session after
  restart; do not infer ownership merely from an item's position or track name.
- Persist kept/discarded status and favourite state with each pass. A retry is
  one idempotent bridge command: apply the decision to its identified latest
  pass, then start at most one new take. Duplicate taps or another tablet must
  not discard an older pass or start multiple recordings.
- Keep musical stem volume, key processing and rehearsal bus mutes from changing
  recording tracks. Recorded audition may share hardware destinations with stems,
  so its independent mute controls must operate before any shared bus that would
  silence both. Save/restore audition overrides when returning to rehearsal; do
  not overwrite the user's normal backing choices. Verify the actual routing
  rather than adding another full mixer UI to compensate for it.
- Use one tempo/key/playrate setting per recording session once its first pass
  starts. Show it in the song summary; changing it deliberately starts a new
  session with the old takes retained. This avoids silently retiming recorded
  performances or exporting incompatible passes on one backing timeline.
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
- Opening exported work must not let the background bridges reset its playrate,
  pitch or mutes. Distinguish rehearsal projects from exported recording projects.
  Retained raw files and recovery data are managed behind the scenes; storage
  cleanup is an explicit maintenance action, not a recurring post-take prompt.
- Detect native REAPER stop/project changes and disconnections; never show an
  optimistic recording light. Ordinary performance and recording remain local and
  do not depend on the optional importer server being available.

The REAPER API provides input enumeration, track/input/arm controls and project
save/state functions. Count-in/pause and media-copy behavior have been exercised in
scratch projects as described in the release verification above:
[official ReaScript API](https://www.reaper.fm/sdk/reascript/reascripthelp.html).

### Implementation checkpoints

1. Verify physical source/USB routing against the supplied live input list and
   the initial X32 setup guide. Prove volume persistence/import interactions and recording count-in,
   pause/resume and export alignment in isolated REAPER projects.
2. Implement and verify per-song gain, including native playback and song updates.
3. Implement the session bridge and Recording screen with persistent recovery.
4. Implement audition and verified export/cleanup; inject copy/save failures and
   project switches to prove originals survive and retries cannot duplicate takes.
5. Test two simultaneous tablets, normal playback regressions, restart recovery,
   discard/restore, repeated retries, changed arm selections and actual multichannel
   audio capture. Publish through the standard update branch.

### Usability acceptance checks

- With the rig configured, a musician can start from a cued song without entering
  a filename, reopening Setup or reselecting every input.
- Stop never discards a take. Both retry actions require one deliberate tap and
  reuse the input/count-in selection; duplicate taps cannot start a second pass.
- Done allows the next song immediately after the current take is safely saved.
  Coming back later finds it without browsing REAPER files or exporting first.
- Review can switch whole takes and independently mute backing/recorded parts;
  it never stacks older passes or leaks its mute choices into rehearsal.
- A tablet reload, native REAPER Stop or second tablet cannot invent recording
  state, lose the latest take, or operate on the wrong song/session.
- Record → Stop → close without Done/export → reopen finds the saved session,
  prompts once and leaves its takes silent during normal rehearsal playback.
- Force-close during capture, export or cleanup is tested separately: recoverable
  files remain discoverable, incomplete takes are labelled honestly, and cleanup
  cannot delete unverified or unrelated material.
- Later allows rehearsal; Delete is recoverable; successful export removes only
  the exported session's items. Repeated startups do not duplicate exports/items.
- The exported project opens with all kept passes aligned to the original stems,
  sensible named tracks and exactly one selected pass audible. Native REAPER can
  then handle editing and mixing without requiring the ReaSet browser.

## Agreed upgrades

**Delivered in ReaSet v3.8:** [Free-jam recording with optional click and count-in](FREE_JAM_RECORDING.md),
using the existing input selection, take management, recovery and export workflow.

**Next:** Suggested song-level matching: measure backing loudness and suggest a
per-song playback trim for approval, preserving stem balance and click level.
