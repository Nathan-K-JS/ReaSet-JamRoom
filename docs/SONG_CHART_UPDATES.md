# Section charts and existing-song updates

Delivered on `feature/timing-repair`, September 2026. The importer reports v3.0;
the structured chart schema is 2 and its generator is `sections-1`.

## Start using it

1. Run **JamRoom Update.bat** on another installation to fetch and deploy this branch.
2. Save your REAPER project, then restart REAPER and the importer. Refresh ReaSet
   in each browser. Already-running Lua scripts retain their previous code until
   restarted; rerunning Startup alone skips scripts that are already running.
3. Open **Update song charts** in ReaSet, or **Song library → Update lyrics &
   chords…** in the importer. Opening from ReaSet includes its current setlist.
4. Leave the songs you want selected. Uncheck individual songs to exclude them
   from this run. **Keep this version** also excludes a song from future updates.
5. Stop playback and choose **Update selected**. Each song completes separately;
   a failed song does not prevent the others from updating.

Existing songs are not silently rewritten when the application updates. The
library chooser is the deliberate migration step. Audio, routing, regions,
region IDs and setlist membership are unchanged by this operation.

## Automatic first pass

New imports and library updates use the same generator. There is no mandatory
section-confirmation pass.

The generator retains headings, chord progressions, printed word positions and
explicit repeats from the selected Ultimate Guitar chart. Timed lyrics supply
the recording-relative vocal passages. Blank lyric entries terminate vocals;
they are not thrown away and turned into long sung lines. Short breathing gaps
are grouped into passages. Longer uncovered intervals become instrumental
passages, using source headings such as Intro or Solo where their order fits.
Otherwise the label stays generic. These boundaries remain estimates.

An abbreviated chart can supply the same chorus to multiple occurrences in the
timed lyrics. Matching wording can reuse printed chord positions. Similar but
different wording may reuse a progression without pretending to locate each
chord on a new word. Conflicting matches are left unresolved. Missing verse
content cannot be reconstructed reliably just because another verse exists.

Chords do **not** receive evenly spaced timestamps just to fill a lyric line or
a silent gap. A complete progression must have ordered matches in the detected
audio events before its chord timings are emitted. This is supporting evidence,
not musical ground truth. Sheet/Chart mode remains readable when those timings
are unavailable. Audio-only harmony is labeled estimated. Empty harmony is
shown as missing rather than filled with guessed chords.

Chart and lyric views show the passage, progression, matched words and upcoming
section. Previous/Next lets you browse; Resume following returns to playback.
Canvas receives the same section content. Big/Timeline remain available as
optional event views; songs with manual section edits use the section document.
Legacy songs continue to use their existing timeline until upgraded.

## Fix a passage

Choose **Fix this section** in ReaSet. Select the passage, change its start/end
in seconds relative to the song, rename it, choose a source progression, or type
a corrected chord progression and repeat count. You can mark the section start
at the current playback position. Shared boundaries move together; word-row
times in affected passages are scaled to fit. Changing a progression removes
unsupported word anchors rather than retaining the old chord-to-word mapping.

REAPER confirms the save, stores the document in project extstate, and provides
one undo step. Every connected browser receives the same document. Section
edits do not rewrite individual legacy note items; structured views use the
edited document. A stale browser revision or wrong project cannot overwrite a
newer section edit.

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

The automated suite passed **46 tests**, including real Edge browser rendering,
selection and save-confirmation tests, plus production Lua executed against a
deterministic REAPER API fixture. Run:

```powershell
python -m pip install -r tools/requirements-dev.txt
python -m unittest discover -s tools -p "test_*.py" -v
```

Browser tests require Microsoft Edge on Windows and report a skip if absent.
All Lua files and both inline browser scripts also passed syntax checks.

An opt-in live check exercised **12 assertions in REAPER**, including actual
item replacement, retry, restore, preservation of unrelated tracks, document
publication, section editing, changed-boundary rejection and protection of later
edits. The scratch tab was saved and closed; the original project's state-change
count and cursor were unchanged. To repeat while REAPER is stopped:

```powershell
python tools/verify_reaper_live.py
```

These checks establish software behavior, not a measured song-accuracy rate.
An additional dry run against the cached Dreams import produced nine passages,
including its intro and instrumental break, with 30 matched lyric rows. It
changed neither the saved job nor the loaded project; those counts are not an
independent assessment of musical accuracy.
Automatic labels and boundaries remain heuristic. Multiple unmatched
instrumental templates may be divided approximately within a gap. This version
does not perform speech alignment, beat tracking, or reliable reconstruction of
omitted new verses. Section splitting/merging and a full revision-history UI are
future extensions. A labeled song benchmark is still needed to measure how often
an untouched import is musically satisfactory.

See [the project review](PROJECT_REVIEW.md) for the original findings, broader
feature suggestions and remaining work. In particular, the pre-existing
**Delete song** workflow has broader scope than this new updater and still needs
an importer-ownership audit. Use the update/restore workflow for chart repairs.
