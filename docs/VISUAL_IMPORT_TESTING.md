# Testing an import in the actual ReaSet interface

Run from the repository while REAPER is stopped:

```powershell
python tools/verify_song_visual.py
```

The default song is the cached `Fleetwood Mac - Dreams`. To select another cached song:

```powershell
python tools/verify_song_visual.py "imports/The Presets - My People"
```

This uses Python Playwright and the installed Microsoft Edge in headless mode,
connected to REAPER's real web server at `http://127.0.0.1:8080/ReaSet.html`.
It does not mock the REAPER transport, inject song data into the browser, or
substitute a static HTML preview.

The check generates an import job from a copy of the cached song metadata,
references its existing audio, and runs an unchanged copy of the production
import-apply Lua script in a new scratch project tab. It starts the real
chords/lyrics bridge temporarily if no heartbeat is present. The scratch master
is muted. The browser clicks CHORDS and + Lyrics, seeks REAPER to 0, 30, 75 and
140 seconds, and captures desktop and tablet screenshots. Playback is not started.

Each run writes an evidence folder under `imports/.visual/` containing:

- `applied.txt`: REAPER's import receipt.
- `result.json`: live song identity, item counts, browser errors and visible text.
- `chords-lyrics-*.png`: actual browser screenshots to inspect with an image viewer.
- `scratch.RPP`: the imported test project, saved before closing its tab.
- `cleanup.json`: confirmation that the original project's change count and cursor were preserved.

The original cached song metadata is not written. Chart generation uses the current
production generator, so generated chord-item counts can differ from older cached
detection counts. Existing chart URLs may be consulted by that generator. This
check does not exercise a fresh recording download, paid stem separation, or the
importer's review/apply buttons. Those are separate checks; passing this one does
not establish provider authentication, musical correctness or audible sync.

The REAPER wrapper has a three-minute cleanup deadline in addition to Python's
normal cleanup signal. Inspect `error.json` and `cleanup.json` if a run fails.
Do not switch project tabs or edit REAPER during the check. The served ReaSet page
must be the version you intend to test; this script does not deploy files.

## Verified on 2026-09-11

Evidence: `imports/.visual/song-tmpsb537/`.
The installed page matched the repository. The real import produced 8 stems,
35 lyric items and 9 generated chord items. The browser confirmed a live bridge,
the correct song and `sheet` (+ Lyrics) mode, with no JavaScript errors. Cleanup
confirmed the original project was unchanged.

Visual inspection found chord letters touching the ends of some lyric lines and
chart content underneath fixed controls. These are observations for subsequent
UI work, not a claim that the presentation passed a visual quality check.

## Source chart revision, 2026-09-11

The three saved test songs were rebuilt through the library chooser using
`source-pages-2`: Dreams, All The Small Things, and I Believe in a Thing Called
Love. Live evidence is in `imports/.visual/source-pages/live-library/`.
Every page was checked at 1440x1000, 768x1024, 390x844 and 1024x768. No page
clipped vertically or horizontally, and the rendered chord total matched every
source anchor at every size. Representative verses, choruses and endings were
also inspected as actual images and compared with the cached original charts.

`imports/.visual/song-zn_3yidt/` records an actual scratch import plus a section
split and cue tap through the browser. REAPER confirmed both saves, the source
rows stayed identical, and cleanup confirmed the original project was unchanged.
Use `--edit-check` after the cached-song path to repeat this test.

The first browser save test exposed truncation of large web commands, despite
passing direct Lua tests. Saves now send small chunks; the repeat browser test
passed. This distinction is why mocked transport tests alone are insufficient.

These are readable source charts with editable page cues. They are not an
assertion of accurate automatic audible synchronization. Review playback and
correct estimated cues with Timing on the performance screen.

The live session also exposed duplicate background publishers left by repeated
command-line launches. A clean REAPER restart removed the older instances.
The bridge now gives ownership to its newest instance; older loops exit without
clearing the new publisher's state. The live REAPER check verifies this handoff.

Final repeat: `imports/.visual/song-97zn4z_w/` passed the browser split/cue checks
and cleanup. Cleanup compares complete track chunks, regions, chart documents,
legacy corrections and ReaSet project settings, plus the cursor. It records the
raw project change counter separately because legacy publishers update their
current-text fields during normal operation. Both checks passed in this run.
