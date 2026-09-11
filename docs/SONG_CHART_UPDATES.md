# Section charts and existing-song updates

Delivered on `feature/timing-repair`, September 2026. The importer reports v3.1;
the structured chart schema is 2 and its generator is `source-pages-2`.

## Start using it

1. Run **JamRoom Update.bat** on another installation to fetch and deploy this branch.
2. Save your REAPER project, then restart REAPER. The updater restarts any running
   importer automatically; open **JamRoom Importer.bat** if it was closed. Refresh ReaSet
   in each browser. Already-running Lua scripts retain their previous code until
   restarted; rerunning Startup alone skips scripts that are already running.
3. Open **Menu > Song library & chart updates** in ReaSet, or **Song library → Update lyrics &
   chords…** in the importer. Opening from ReaSet includes its current setlist.
4. Leave the songs you want selected. Uncheck individual songs to exclude them
   from this run. **Keep this version** also excludes a song from future updates.
5. Stop playback and choose **Update selected**. Each song completes separately;
   a failed song does not prevent the others from updating.

Existing songs are not silently rewritten when the application updates. The
library chooser is the deliberate migration step. Audio, routing, regions,
region IDs and setlist membership are unchanged by this operation.

## Importer recovery during application updates

**JamRoom Update.bat** checks port 8765 after a successful pull, including when
Git says it is already current. It stops a verified Python importer and its local
workers, then starts the installed code and checks its runtime identity over HTTP.
This works without a responsive importer page. An unrelated port owner is left
alone and reported as a recovery failure.

Updating interrupts unfinished imports, including downloads or preparation.
Cached files are retained; retry the unfinished song and inspect REAPER before
applying it again. Restarting Python cannot undo work already applied in REAPER
or cancel work already submitted to a remote provider. Batch chart progress remains
available through the existing resume workflow.

For recovery without fetching an update, run from the installation folder:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/restart_importer.ps1
```

Startup logs are under `imports/.runtime/`. When upgrading from an older updater
that does not contain recovery, run Update a second time: its first run continues
using its old temporary copy, even after downloading the new batch file.

## Source chart and page timing

The selected Ultimate Guitar chart controls the section order, lyric wording,
line breaks and chord columns. Timed lyrics estimate page cues only. They cannot
replace chart words, redistribute chords across a lyric line, or invent a new
section order. Instrumental patterns and printed repeats stay compact. Missing
source content is not reconstructed from an unrelated verse.

**+ Lyrics** places chords above their original word positions. Long sections
split into readable pages that fit the available display, without performance
scrollbars. Previous/Next browses pages; Resume following returns to playback.
**Chart** shows the chord patterns without words. Big/Timeline use the separate
audio-detected events, whose timing and harmony may be inaccurate.

Automatic cues are labeled **Cue estimated**. Source chord columns describe
musical relationships to words; they are not proof of recording synchronization.
Abbreviated or incorrect source charts still need review. This release does not
claim to solve forced alignment or verify the recording by listening.

## Correct structure or timing

Choose **Edit sections** to see the full chart in a scrollable editing dialog.
Rename sections, split before a source line, or join the preceding section.
Adjust starts in song-relative seconds and save. Every original line must remain
exactly once and in order; words and chord anchors are retained. This is a section
editor, not a general lyric or chord transcription editor.

Choose **Timing** on the performance chart. While playing or seeking, use
**This page starts now** or **Next page starts now**. Section boundaries move
together. Continuation-page cues are attached to their source line and column.
Moving a cue never stretches words or changes which lyric a chord belongs over.
Changing screen size can create different continuation pages, so check timing on
the performance device after resizing; section starts remain shared.

REAPER confirms saves, stores the document in project extstate, and provides one
undo step. Connected browsers receive the new document. Stale revisions and edits
for another project are rejected. Save the REAPER project to keep these changes.
Legacy timing checkpoints must be replaced through the update chooser before
using the new section editor, to avoid applying two timing correction systems.

## Quality acceptance

A successful import or high text-match count is not a musical quality pass.
Check the selected source chart against every displayed section: exact words,
chord-to-word columns, section order, instrumental repeats and final coda.
Inspect every page at performance screen sizes for clipped lines, chord overlap,
and inaccessible controls. Then play the actual recording and check page turns;
use cue taps to correct them. Automated checks cover preservation, layout and
confirmed persistence, not audible synchronization or the source chart's accuracy.
See [visual testing](VISUAL_IMPORT_TESTING.md) for the real REAPER scratch test.

## Updates, protection and restore

- **Current** requires both a matching generator and a matching installed REAPER
  revision. Updating an already-current song is skipped unless rebuilding was
  explicitly requested through the replacement option.
- Updates reuse saved lyrics, selected chart templates and chord evidence. Old
  jobs with only a chart URL may need to fetch that chart once. No audio download,
  paid stem separation or automatic recording replacement is part of a batch.
- Saved timing checkpoints and manual section edits are protected by default.
  **Replace old timing fixes too** permits discarding them during regeneration.
  Use **Keep this version** for songs whose current results should remain intact.
- **Pause** stops before the next song. Playback or a project change also pauses
  the batch. **Resume** retries incomplete/failed work and skips completed songs.
  Restarting the importer retains that progress.
- **Restore selected** restores each selected song's latest saved previous
  version. **Restore last batch** applies that operation to songs completed in
  the most recently displayed batch. Restore refuses later project edits rather
  than overwriting them. The UI exposes the latest batch, not a history browser.

Snapshots and manifests live under `imports/.updates/<project-id>/` (or your
configured jobs directory). They include actual REAPER text-item chunks,
documents, revisions, timing repairs and saved jobs. Keep that folder when
backing up your library. A candidate is generated before mutation. The
transaction checks stopped transport, project/region identity, utility-track
ownership constraints and boundaries, writes its before snapshot, then applies
the change. Failures during mutation attempt to restore that snapshot. Matching
operation IDs make retries idempotent. Save the project normally after updates.

## Validation and limits

Run automated content, browser, transaction and timing regression checks:

```powershell
python -m pip install -r tools/requirements-dev.txt
python -m unittest discover -s tools -p "test_*.py"
python tools/verify_reaper_live.py
python tools/verify_song_visual.py "imports/The Darkness - I Believe in a Thing Called Love" --edit-check
python tools/verify_import_playback.py "imports/Lenny Kravitz - Fly Away"
```

The last three commands use real REAPER scratch projects and require stopped
playback. The visual check imports cached stems, photographs the actual browser,
splits a section and taps a cue through REAPER's web interface, then confirms
that source rows did not change and the original project was preserved.
The append check requires a saved, populated library. It imports cached stems
twice into a disposable template of that library and checks native and browser
Play without restarting REAPER. This catches transport failures that an empty
scratch project can miss. It also checks playback after an aborted import.

Full section saves use small UTF-8 hex chunks: REAPER truncates large individual
web commands, so a direct Lua-only save test cannot validate the browser path.

The older event checkpoint drawer and importer lyric-offset/replacement controls
have been removed. Existing corrections remain readable for compatibility;
regeneration explicitly replaces them when the user selects that option.
Source-chart selection remains available under **Chart tools**.

**Update whole library** includes eligible songs throughout the current REAPER
project, even outside the selected setlist. Current songs, protected versions and
songs without cached sources are excluded. Audio is reused; the same generator
and transactional backup/restore path are used as for selected-song updates.

No check here establishes audible sync or the source chart's correctness. A
labeled musical benchmark is still needed before claiming untouched imports
are ready for rehearsal.
