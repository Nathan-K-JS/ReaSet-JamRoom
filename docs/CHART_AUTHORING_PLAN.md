# Chart authoring and timing review

Status: proposed after user clarification, 22 September 2026. No application
changes are included in this plan. Baseline: v3.17.

## Agreed scope

One chart editor serves songs already in the REAPER library and songs being
reviewed for import. It supports writing missing instrumental chords, correcting
lyrics, editing chord placement and restructuring sections.

The user confirmed:

- Corrected words appear consistently in both Lyrics and Chords.
- Both chart dividers and section start markers on an audio timeline are draggable.
- Timing correction stays at section/page level. Individual lyric-line or chord
  timestamps are not part of this upgrade.

The ordinary performance chart retains its current paging, transposition, capo,
early page turn and next-page preview. Editing is a deliberate separate workspace.

## Existing behavior and changes required

| Existing capability | Consequence for this work |
| --- | --- |
| Documents preserve lyric text and chord character offsets; modern Lyrics and Chords already render the same document. | Extend that document rather than create a separate edited-lyrics source. |
| Edit sections only sends row identities; Lua requires all original rows exactly once and in order. | Add a validated content-authoring operation. The current layout command cannot add or change music. |
| UG parsing recognizes tagged chords, not ordinary typed chord lines. | Add plain-text chord recognition, explicit line-type overrides and round-trip tests. |
| Imported timing comes from matching chart words to timed lyrics, with interpolation for unlocated sections. | Preserve the origin of each suggested cue. An automatic match is not a listening confirmation. |
| Import review currently returns chart metadata and a source link. Apply regenerates the document from cached source templates. | Publish an editable candidate, persist its draft, and make accepted authored content authoritative during Apply. |
| Library edits live in REAPER, while source templates live in cached jobs. | Start library editing from the current project document; never silently replace it with the cached source. |
| Updates preserve manual chart revisions by default; direct chart/lyric replacement has separate regeneration paths. | Bring source-replacement paths under the same preview, confirmation and revision checks. |

Relevant files: `ReaSet.html`, `Requirements/ReaSet_ChartEdit.lua`,
`Requirements/ReaSet_ChordsLyrics.lua`, `tools/jamroom_chart.py`,
`tools/jamroom_import.py`, `tools/jamroom_import_queue.py`,
`tools/jamroom_importer_server.py`, `tools/jamroom_updates.py` and
`tools/jamroom_song_transaction.lua`.

## The workspace

Entry points:

- In ReaSet, **Edit chart** replaces **Edit sections** in Lyrics and Chords.
- In importer Chords review, **Review / edit chart** opens the chosen chart.
- A song without a usable chart can **Create chart** using its existing audio
  duration. Missing cached sources do not prevent writing one manually.

The header identifies the song, source, editing key and save state. **Change
source chart** opens the existing UG search/URL workflow through a preview step.
Desktop shows editable chart text beside the performance preview; the selected
section is linked between them. A timeline and playback controls occupy reserved
space. On phone, **Edit / Preview / Timing** switch one main pane rather than stack
all three screens. Save/return and playback Stop remain reachable.

See the [proposed editor layout](ui-layout/chart-editor.svg). It is a static design
board, not a screenshot of implemented software.

The editor preserves its selection, scroll, undo history and unfinished input
while background status changes. Selecting a section does not start playback.
Clicking the timeline seeks; dragging a marked boundary moves that boundary.
Those targets must be visually and behaviorally distinct.

Library editing uses native REAPER playback. Import review uses local browser
audio. Audio stops when leaving import review or switching its source/song;
opening another stem preview also stops the chart player. There is one audible
browser preview at a time.

In the library, draft editing and timing review may run during playback; installing
replaced chart content waits for Stop, with an explanation beside Save. Recording
and recording-review locks remain respected. Do not stop room playback merely
because someone opens or edits a chart on another tablet.

## Writing chords and lyrics

Use plain, monospaced text with normal spaces and line breaks:

```text
[Verse]
C              Am7
We find a way together
F        G/B
Home before the light

[Instrumental]
| Am7 | F | C | G | x2
```

These are illustrative original words, not a song transcription. Recognized
chord tokens change colour while typing; lyrics remain ordinary text. The live
preview uses the same chord-above-word layout as performance playback.

- A chord line attaches to the lyric line below it by character column. Consecutive
  chord lines remain separate instrumental rows, not lyrics to the previous line.
- Preserve spaces, blank separators, bars, repeat marks and standalone chord
  passages. Pasted tabs expand consistently to documented fixed tab stops.
- Recognize common major/minor, seventh/extended, suspended, altered and slash
  chords, sharps/flats and `N.C.`. Unrecognized material stays visible and editable.
- Provide a small **Auto / Chords / Lyrics** line override. Ordinary words such
  as a lyric beginning with “A” must not become chords. A forced Chords line can
  flag an unrecognized symbol without deleting or silently converting it.
- Colour has a text legend and line-type indicator; it is not the only signal.
  Recognition means notation was parsed, not that its harmony matches the song.
- Typing and pasting must preserve caret position, native text undo, selection,
  keyboard composition and mobile input. Syntax highlighting must not rebuild
  the active text input on each keystroke. Use a normal text-input foundation
  with a synchronized highlight layer, subject to the early input prototype.
- Normal Enter, paste and delete handle musical text; a section header/handle
  handles boundaries. Do not require UG markup or special chord brackets.

Editing uses the original recording's sounding key, clearly labelled. UG capo
normalization has already happened on import. Playback key and display capo remain
independent; the preview can show the current performance settings with an explicit
label. Opening/saving the editor must never apply either transposition twice.

## Restructuring sections

Each section has a stable identity, editable name and a divider with a dedicated
drag handle. Repeated choruses remain separate occurrences even when their words
and names are identical.

- Drag a divider to a gap between chart rows/pairs to change which music belongs
  to the sections on either side. Never split a chord line away from its paired
  lyric line as an accidental side effect.
- **Start section here** inserts a divider. **Merge with previous** removes one
  and retains every line. The first section can merge with the following one.
- Deleting words/chords is an explicit text edit. Removing a section divider does
  not delete its music. Undo restores both structural and text edits.
- Dragging a text divider does not silently change its audio time. Show that its
  assignment needs review, and offer **Suggest timing** where evidence is available.
- Dragging a timeline marker changes the start time without moving text.
- Pointer dragging has touch handles and keyboard/button alternatives, including
  **Move boundary up/down**, numeric time and **Start section here**.

An empty inserted instrumental section can be filled directly. Generated missing
chord warnings clear when content is supplied, without marking its timing checked.
An explicit repeat annotation stays an annotation; editing it does not silently
duplicate rows or change song duration.

## Timing, evidence and confirmation

Each section shows a compact timing summary, for example:

`Chorus 2 · 1:12.4 · +18.6s · Matched from lyrics`

The first value is absolute within the song, never the setlist project's timeline.
The delta is the interval from the preceding section's start. The first section
shows zero and no preceding delta. Tempo changes affect playback conversion, not
the saved recording-relative coordinates; whole-chart offsets are displayed
consistently and not applied twice.

| Label | Meaning |
| --- | --- |
| Matched from lyrics | This start has retained evidence from automatic chart-to-timed-lyrics matching. Still unverified against playback. |
| Estimated — check timing | Interpolated, inferred from a lyric gap, missing evidence or an inherited old cue whose origin cannot be established. |
| Manually placed — check playback | Typed or dragged to a time, but not explicitly checked while listening. |
| Checked during playback | The user explicitly confirmed this section/page cue against playback. |

Content warnings (missing chords, unrecognized notation) remain separate from
timing state. Avoid an invented accuracy percentage or a green automatic “verified”.

The Timing view provides play/pause/stop, scrub/seek, a short **Play before cue**
action, marker dragging, numeric time, **Starts here** and **Mark checked**.
Section starts remain ordered and inside the song. Dragging cannot cross adjacent
markers. The zero-time first section remains explicit, including any opening gap.
There is no bar/beat snapping assumption for recordings with variable tempo.

Automatic suggestions are computed for the current effective draft, including
its lyric offset. Display their evidence; do not keep recalculating and moving
manually placed starts while the user types. Re-running suggestions must preserve
checked cues unless the user explicitly chooses to replace them.

Page cues remain tied to stable content, not page numbers. The preview uses the
real performance paginator. A changed screen size or font can create different
pages, so only still-applicable cue anchors retain their checked state. Chord-only
corrections preserve unaffected timing; changed wording, row splits or moved text
boundaries invalidate the affected links without resetting the whole song.

## Source comparison and local audio

**Change source chart** reuses UG search and direct URLs. Fetch the alternative
into an isolated candidate; show its chart and timing warnings before **Use this
chart**. Cancel, failure or closing comparison leaves the current authored draft
intact. Accepting a replacement explicitly replaces chart content/assignments,
retains a recoverable previous version and leaves stem routing/labels unchanged.
Lyrics-source replacement must also go through a deliberate review; it cannot
quietly regenerate over the musician's authored words.

Import audio preview uses the cached original recording when available. Fadr
library imports may have only stems; generate one cached preview from the music
stems, excluding generated click. Avoid trying to synchronize multiple HTML audio
players. Transcode to a browser-tested format with correct MIME, byte-range
seeking and a verified time origin; encoder delay must not shift saved cues.

Generate peak data for an overview and useful timeline zoom; current 480-bucket
stem profiles alone are insufficient for close timing placement. Show generation
progress, reuse the cache and retain text editing if audio is missing. Serve only
approved job-scoped assets. The click-review file is not suitable: it contains
music and click on separate channels.

This uses existing local audio and FFmpeg; no paid Fadr rerun or new cloud service.
Library playback/timing uses REAPER and must not require the importer. Source
replacement and importer audio preview can require that existing local service.
The library timeline must remain usable with markers and time labels when cached
waveform data is unavailable; waveform loading cannot block native audition.

## Saving, resume and update protection

Import drafts extend the existing revision-checked job journal. Autosave includes
authored content, section identities, timings and evidence, and remembers the
selected editing view. **Saved for import** means confirmed by the service;
**Add to REAPER** installs that exact accepted chart, not a fresh regeneration.

Library drafts start from the live project document. Keep an unsaved recovery draft
in the browser, keyed by project, song and base revision; **Save chart** applies a
validated edit to REAPER with acknowledgement and one native undo step. Restoring
a draft after another device edits the song requires resolving the revision
conflict, never silently overwriting it. After saving, indicate that the REAPER
project still needs its normal save to persist across shutdown.

Preserve current manual-edit protection during library updates, with the existing
explicit replace-edits option and snapshots/restore. Direct chart/lyric replacement
must recheck project, song and revision before applying. Keep original UG content
and timed-lyric evidence as provenance; do not pretend newly authored words have
the original source's exact line timings.

The authored chart is the display authority for both Lyrics and Chords. Any
derived fallback chart/text representation must use that authority too. Raw timed
lyrics remain evidence for suggestions, not a competing display source.

## Implementation order

1. **Document/edit contract and compatibility.** Define stable section/row IDs,
   line overrides, authored content ownership and cue provenance. Keep schema-2
   compatibility where practical; old documents gain conservative evidence labels
   on edit. Support a new blank chart and a recoverable legacy conversion without
   rebuilding the library automatically. Define when edits invalidate timing.
2. **Parser and editor prototype.** Implement plain-text round-tripping, coloured
   chord recognition, instrumental rows and input behavior. Prove paste, undo,
   alignment and mobile composition before building drag interactions around it.
3. **Safe persistence paths.** Extend importer drafts and Apply precedence; add
   validated native content edits, revision guards, undo and bounded chunked web
   transport. Existing saves have a roughly 36 KB raw payload cap, so account for
   content payloads with edit deltas or a tested bounded extension. Never send
   waveform/audio through project extstate. Adapt source replacement and updates
   before exposing a save button that could lose corrections.
4. **Library workspace.** Add Edit/Preview, split/merge and text-divider movement;
   save/reopen corrected content in both performance views. Preserve the local,
   single-file ReaSet runtime and existing performance behavior.
5. **Importer review and source comparison.** Reuse the same editor behavior and
   validation contract through HTTP adapters. Serve the shared inline editor core
   from ReaSet through the importer if needed, avoiding a second implementation
   or an importer dependency for ReaSet. Add draft recovery and isolated candidates.
6. **Audio and timing interaction.** Add cached import preview/peaks, native/browser
   transport adapters, timeline marker dragging, absolute/delta labels, suggestions
   and explicit listening checks. Verify source-to-preview timing before treating
   captured browser positions as usable cues.
7. **Workflow and native validation, documentation and release.** Deliver through
   both existing update branches only after the authoring and preservation paths
   work end to end. Bump the generator when generation behavior changes; existing
   library songs continue to update only through explicit library actions.

The shared editor remains vanilla JavaScript. No new framework, transcription
service, recording interface or chord-by-chord sequencer is needed.

## Acceptance checks

- Add chords to an empty intro/solo; edit a wrong lyric and its chord placement;
  save/reopen and see the same result in Lyrics, Chords and import preview.
- Paste mixed chord/lyric blocks, leading spaces, tabs, adjacent instrumental
  lines, slash/extended chords, Unicode accidentals, `N.C.`, repeats and ordinary
  lyrics beginning with “A”. Preserve unfamiliar notation and all intentional text.
- Test actual typing, undo/redo, selection, multiline paste and mobile composition;
  status polling must not move the caret or interrupt dragging.
- Edit under changed playback key and capo, then reset those settings: no pitch
  drift or double transposition. Changing song speed preserves cue coordinates.
- Split, drag and merge dividers; retain each content line exactly once. Duplicate
  chorus text must not share identities or inherit another occurrence's timing.
- Add/move timing markers, use numeric entry and tap cues during playback. Check
  absolute/delta times for a song far into the setlist and with a chart offset.
- Confirm automatic matches and guessed instrumental cues are distinguishable;
  manually moving a marker does not mark it playback-checked.
- Resize, change font and switch performance modes: content fits, page turns still
  work and checked badges follow valid anchors rather than stale page numbers.
- Reopen a partially edited import; switch jobs; fail autosave; edit from two tabs;
  change UG chart and cancel; accept a replacement and restore the previous draft.
- Apply an authored import twice through receipt guards. Update click/levels/full
  library, restart REAPER and restore an earlier version without silent edit loss.
- Exercise no-source/legacy charts, missing preview audio, Fadr stems without an
  original recording and mismatched/stale project revisions.
- Test 320x568, 390x844, tablet, desktop, 844x390 and 200% zoom. Inspect actual
  rendered editor/preview/timing screens; keep Save and Stop reachable. Browser
  emulation supplements a real iOS/Android keyboard and touch acceptance check.
- Run native scratch-project save/undo/restart/receipt checks and populated-library
  import/playback regressions. Preserve the original test library. Audible cue
  correctness is checked through representative playback, not text-match scores.
