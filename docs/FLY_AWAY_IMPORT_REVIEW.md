# Fresh import: Fly Away — Lenny Kravitz

Tested on the development workstation, 2026-09-11. Release: importer v3.3,
chart generator `source-pages-4`, source parser 3.

## Recording, chart and stems

Used [the 3:42 recording on Lenny Kravitz's YouTube channel](https://www.youtube.com/watch?v=cELBtOexOOo).
The fresh M4A download took 6.75 seconds; the 3.6 MB Fadr upload took 5.9 seconds.
One main split took 12 seconds, followed by melodic and vocal sub-splits taking
33 and 39 seconds respectively. No repeat paid processing was used for fixes.

Selected [UG chart 51423](https://tabs.ultimate-guitar.com/tab/lenny-kravitz/fly-away-chords-51423),
rated 4.80 from 455 votes at review. It had a complete sectioned arrangement.
The next candidate grouped almost the entire song under Intro and was a worse
starting point. Kept the source pitch, without transposition.

Imported six groups: drums, bass, electric guitar, lead vocals, backing vocals,
and Extras combining non-empty piano/wind/strings outputs. These separator labels
do not establish the actual instruments present. Kept the residual audio rather
than silently discarding it; skipped the essentially empty acoustic and other
melodic outputs. The piano-labelled output had measurable content but had been
automatically set to Skip because earlier songs skipped piano. Overrode that
decision for this import, then fixed the shared suggestion rule.

The song is region 7 in the test project, starting at 1125 seconds. It has six
audio groups, 58 lyric items, 145 measured chord items, and 137 authored chart
chord symbols. The measured items and authored symbols serve different views;
their counts are not expected to be equal.

## Failures found and shared changes

1. **Greedy matching shifted repeated passages.** The previous longest-block
   matcher misplaced the outro and left its first seven source rows without cues.
   Replaced it with global word sequence alignment that accounts for substitutions
   and missing words. Deterministic tie-breaking prefers exact matches and earlier
   occurrences. Regression tests include repeated phrases with wording differences
   that caused the old matcher to jump to another repetition.
2. **Partial phrases supplied misleading cues.** A common tail of a line could
   match an earlier ad-lib. A line now needs at least 80% matched words before its
   lyric-derived cue is used. This is an evidence filter, not a musical quality
   score. Six source lines remain without strong timing matches and are explicitly
   reported for review, including overlapping/ad-lib wording in the outro.
3. **Heading annotations became lyrics.** `[Bridge] - no chords` was displayed
   as a sung line inside Chorus. Bracketed headings now accept trailing instructions,
   retained separately from lyrics. Tests cover dash, colon and parenthetical notes.
4. **Leading instrumental bars were timed from the later vocal.** When the source
   begins a section with instrumental rows and the preceding timed vocal ends at
   an explicit blank LRC marker, that gap supplies an earlier cue estimate. Here,
   the bridge starts at 122.27 seconds rather than waiting for vocals at 131.52.
5. **Past routing preferences discarded new audio.** Cross-song skip history now
   supplies a review note, not an automatic Skip selection. Explicit choices saved
   for this particular song still win; essentially empty outputs still suggest Skip.
6. **A correlation result overstated confidence.** Removed the log claim that
   lyric timing “matches the sung vocals.” It now describes an estimated global
   offset and explicitly distinguishes that from verification of individual cues.

All chart changes run through shared generation, including the whole-library
update path. There are no artist/title checks in generation. Parser and generator
versions make existing cached charts eligible for explicit regeneration.

## Review and limits

The initial and revised charts were viewed in actual REAPER. The bridge now has
its own page instead of appearing as a lyric. The verse and chorus are readable;
the long outro needs three pages and its overlapping words still need judgment.
Desktop and portrait tablet use 10 pages; phone and landscape tablet use 15.
All 137 source chord symbols appear exactly once at each of four tested sizes,
without clipping or performance scrollbars. This is a layout check, not proof
that the song is musically correct.

Updated only Fly Away through the normal library chooser, with a successful
one-song batch and backup. Rebuilt five cached-song candidates without modifying
the other saved songs, and checked all their pages at the same four sizes.
All 98 automated tests passed.

An additional real-playback check passed the first verse, bridge and outro
transitions in a muted scratch project. Section editing and a cue tap also saved
through the live bridge, and the original project was unchanged. The reusable
visual test now supports `--playback-check`; its evidence is in
`imports/.visual/song-df6qid79/`. Before this check, the long-running REAPER session
reported playback near zero despite a successful seek, including through native
ReaScript. Saving and restarting the session cleared that state. Its underlying
cause was not established; this was not treated as a chart-generation error.

### Follow-up: playback after import (v3.3.1)

The import failure was subsequently reproduced in a disposable copy of the full
library, using cached Fly Away stems and the production apply action over HTTP.
Native Play worked before import, then played near zero despite a cursor in the
appended song. `UpdateTimeline()` alone did not recover it;
`TrackList_AdjustWindows(false)` did, without saving or restarting REAPER.
The importer now performs that refresh before its success receipt, and on its
explicit no-duration abort path. The existing arrange redraw alone was insufficient.

The new `tools/verify_import_playback.py` checks native Play before import, existing
and appended songs after two successive imports (new buses, then reused buses),
an aborted import, and the actual ReaSet Play button. It uses the last saved
populated library as a disposable template and verifies the original is unchanged.
The historical script fails this check: a requested position of 1661 seconds
instead played at 0.997 seconds. The patched script passes. Empty-project import
tests had missed this failure, so populated-library playback is now a separate
release check. This changes the shared import method, with no song-specific repair.

Local evidence is under `imports/.visual/fly-away/`: recording/allocation captures,
baseline and final live screenshots, source candidates, library update receipt,
test log, and five-song layout checks. The evidence contains source chart text
and is not committed as a public test fixture.

This review does not certify separation quality or every chord/cue by ear.
Preserving a source chart cannot repair incorrect or overlapping source wording.
The remaining unmatched lines require source/timing review; matching every word
or fitting every page must never be presented as rehearsal approval.

## Next process priority

Keep separate acceptance checks for source fidelity, section structure, occurrence
matching, playback cues and display. A transport-following check only proves that
the interface follows its saved cues, not that those cues are musically right.
For speed, detailed Fadr sub-splits are the larger remaining wait in this test;
changing the upload format again would not address those measured 72 seconds.
Investigate overlapping the two independent sub-splits while preserving task
reuse and cost accounting, rather than assuming a smaller file speeds the models.

The jam-room PC receives these changes through **JamRoom Update.bat**, then its own
explicit library updates. This workstation's imported song is not that PC's library.
