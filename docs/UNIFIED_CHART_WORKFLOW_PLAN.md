# One chart, one timing workflow

Implementation: **v3.20**, documented in [Unified charts](UNIFIED_CHARTS.md).
Known-duration charts receive usable numeric section estimates instead of a
mandatory unplaced-cue workflow. Preview uses the actual available viewport;
tablet/desktop reference sizes are checked in browser tests. Optional automatic
split suggestions and simulated device previews remain future conveniences;
Add/Split/Merge and measured page fitting are available now.

Proposed 26 September 2026. Ready for implementation review. This document and
the accompanying layout board are planning artifacts; application behaviour has
not changed. This work takes priority over the room-memory/mixdown proposal.

Revised after the [full named Fadr library audit](FADR_CHART_WORKFLOW_AUDIT.md):
45 recordings, 53 recording/chart cases and four browser sizes per case. Source
preservation, protection against broken timing data and restraint in inferred
splitting belong behind the scenes. They must not become extra setup chores.
The layout board remains an illustration; the usability priorities below govern
implementation where an earlier mockup or audit recommendation conflicts.

## Product priority: get friends playing

This is a plug-and-play jam room, not a live-stage cue system. A readable chart
that follows approximately, leaves context visible and is easy to steer is more
useful than apparently precise tracking that repeatedly lands on the wrong line.

- A normal import must be ready to use without checking every cue, listening
  through the song or completing a timing checklist. Refinement is optional.
- Default to full-chart Scroll with comfortable text and surrounding context.
  Prefer stable, broad section following over frequent jumps or line highlighting.
- Approximate timing is a normal usable result, not an unfinished/error state.
  Missing evidence for one section must not disable following for the whole song.
- Keep timing provenance, detailed warnings and fit diagnostics in editing tools.
  The normal screen needs the chart, playback and an obvious Resume following
  action after manual scrolling, not a wall of confidence badges.
- Preserve content, recordings, edits and honest transport/save state rigorously.
  That reliability requirement does not imply exact chart-to-audio alignment.
- Use bounded background lookup and simple fallback estimates. Do not turn this
  work into a new word-alignment engine or delay usable playback chasing accuracy.

## Decisions

1. Show every stem waveform/player expanded when a review opens.
2. Reduce import review to **Stems / Chart**. Remove the separate lyric-timing
   review and its first-vocal check/offset requirement.
3. Make the authored chart the single source of displayed words, chords, grouping
   and performance timing. **Show chords** is a display preference.
4. Use one timed section as the unit the musician edits. Its text boundary and
   start time are visible together. Eliminate independently generated page cues.
5. Offer **Scroll / Pages** using those same sections and cues. Recommend Scroll
   for ordinary rehearsal; retain Pages for people who prefer a stationary view.
6. Fit Pages to the user's chosen sections and actual computer/tablet space.
   Resizing must never invent another page or another timestamp.

The word **section** in the UI means a user-chosen block of chart text. It can
be a whole verse or part of one. A label such as `Verse 2 - continued` is enough
when a long passage needs splitting; do not introduce another hierarchy of
musical sections, display blocks, pages and scroll anchors for users to manage.

See [proposed layout board](ui-layout/unified-chart-workflow.svg).

## What the current code explains

| Finding | Location | Consequence |
| --- | --- | --- |
| Previews start hidden, and opening one closes every other preview | `tools/importer-workspace.js`, `compactStems()` | Repeated clicks are explicitly enforced by the UI |
| Review still has Stems/Lyrics/Chords, first-vocal audition and lyric offset | `tools/importer.html`, `tools/importer-workspace.js`, `tools/importer-queue.js` | The old lyric workflow remains visible after chart authoring was introduced |
| Newer Lyrics and Chords views already read the shared document, but paginate in different modes | `ReaSet.html`, `renderStructuredChart()` | Shared words do not yet mean identical display boundaries/cue selection |
| Pages are generated from viewport width/height, with a fixed 280px height deduction and a narrow font-size search | `ReaSet.html`, `chartBuildPages()` | Space is underused in some layouts and page contents change with the viewport |
| Later pages use a manual row/column cue, a lyric-row cue, or an evenly divided section duration | `chartBuildPages()` | Correct section starts do not guarantee correct page changes |
| Editor preview forces minimum 300px width/520px height into the paginator | `tools/chart-author.js`, `drawPreview()` | The preview can disagree with the available performance area |
| Timeline markers show sections, while page corrections live on rows/columns | `tools/chart-author.js`, `Requirements/ReaSet_ChartEdit.lua` | Some timing edits are invisible on the main waveform |
| The background generator uses timed lyric matches to suggest chart cues and find gaps | `tools/jamroom_chart.py`, `tools/jamroom_import.py` | Removing all lyric analysis would also remove useful chart assistance |

The lyric-timing **step is no longer necessary**. Timed-lyric lookup remains
useful as optional background evidence for the one chart. It must not determine
a second set of displayed words or create a second correction task.

## Stem review

Show waveform, play/seek controls, duration, routing and label for every stem by
default. Opening a fresh or resumed review starts expanded. Within that visit,
allow independent collapse and an **Expand all / Collapse all** convenience;
background refreshes must preserve the user's current expansion and scroll.

Expansion must not download/decode/play all audio. Use existing cached waveform
profiles and `preload="none"`; start the selected audio only on audition. Maintain
one audition player across stem and chart review, pausing the previous one when
another starts. Switching songs or leaving review also stops that audition.
Multiple visible previews must never imply multiple simultaneous players.

Keep v3.19's validated PCM duration/seek path, visible loading/errors, and routing
policy: nonempty sparse stems go to Extras; only measured digital silence is
automatically excluded. Removing the dedicated lyric player removes a duplicate
audition control, not the vocal stem from the Stems list.

## Import review and lyric retirement

### Source preservation and evidence validation

Preserve meaningful source content even when it appears before the first heading.
The current Boston parser loss must be fixed before either new view ships. Keep
source-span provenance and a conservation check across parsing, grouping and
rendering. Classify preambles rather than putting chord dictionaries or author
notes on performance pages; uncertain material stays available for review.

Separate a heading from chords/tab printed on the same line. Recognize compound
musical headings such as Bagpipes solo and Sax Solo without misreading ASCII riff
diagrams as headings. Extend rows with a kind: lyric/chord pair, notation,
performance instruction or source note. Preserve fixed-width tab as optional
notation, with a visible placeholder if a view suppresses it. Do not call every
non-chord line a lyric or include instructions in vocal matching statistics.

Keep source-authored section boundaries as the default grouping. A blank timed
lyric line may mean breathing space, not an instrumental section. Show internal
gap evidence on the waveform and offer Accept break; do not automatically split
every gap into a page. Missing opening/ending material can still be flagged or
suggested explicitly. User-inserted and source-authored instrumental sections
remain first-class content.

Validate candidate lyric timestamps themselves: bounds after legitimate offsets,
order, song/artist identity, text coverage and plausible intervals. A database
duration matching the recording is not sufficient. Out-of-range evidence must
not be clipped silently or squeezed into tiny sections. A long gap after the
last lyric can be a legitimate instrumental ending and needs different treatment.

Retain exact lookup and add identity-checked broader search when it fails; manual
candidate search can also need that fallback. Queries may match album titles or
cover artists, so never select the first relaxed result unconditionally. Preserve
meaningful title parentheses, and tolerate artist-name articles in searching
without weakening the final song/artist identity check.

The chart picker should show rating plus vote count and a short content summary,
not use popularity as proof of completeness. Surface actual missing content or
a clearly wrong source. Put estimated cues and page-fit advice inside the relevant
editing tools; they are not a review queue that must be cleared. Unmatched
instructions and harmless vocal asides should not produce routine warnings.

### Normal review flow

The normal path becomes:

`Choose song -> preparation -> Stems -> Chart -> Add to REAPER`

The Chart tab shows the selected source, **Review / edit chart**, **Change source**,
and a short summary such as `9 sections`. Add to REAPER remains readily available.
Selected source and edited draft remain distinct. Use one unobtrusive
`Approximate timing` description when appropriate, not a counter of unchecked
cues. No timing confirmation is required to import or start following the chart.

Remove the standalone Lyrics tab, first-line vocal check, global lyric-shift form
and independent lyric-replacement flow from normal import/library tools. Retire
their handlers and required DOM assumptions together; hiding the tab alone would
leave old draft/apply logic active.

Keep background timed-lyric acquisition/alignment to suggest section starts.
Missing or poor timing evidence is non-blocking. Bound lookup/retry work and fall
back to coarse section estimates instead of waiting for a perfect match.
Cached analysis is reused;
changing a chord or dragging a divider does not trigger another network lookup.
Expose **Retry timing suggestions** in Chart tools when useful. Advanced source
selection may choose a different timing reference, but it must preview proposed
cues and never overwrite the authored chart's words or checked starts.

Without a UG chart, allow a pasted/manual chart. Available plain or timed lyrics
can seed a words-only chart once; it is then the same editable chart model.
Instrumental-only and completely unscored songs must also remain importable.

In performance, rename the primary destination **Chart** and replace the separate
Lyrics destination with **Show chords** within it. Existing Lyrics links, saved
preferences and MIDI/navigation actions should resolve to that same view with
chords hidden. Preserve an existing chords-only preference under secondary
display options, without retaining a separate timing engine for it.

Hiding chords changes rendered rows/spacing only. It cannot change the selected
section, its start/end, word order or reviewed status. Keep instrumental section
headings visible even with chords hidden, so an instrumental interval does not
display the next verse prematurely. This is section following, not karaoke.

## One editor: content and cue side by side

### Layout

Desktop/tablet landscape uses a compact section outline beside a full scrollable
chart. All sections remain visible in order; the selected section supports inline
text editing using the existing chord recognition and line-type overrides.
Other sections remain readable, and dividers are visible between them.

The selected section header shows its name, absolute song start, `+xxs` since
the preceding section, and timing status. Selecting it highlights the matching
waveform marker; selecting a marker highlights its text. Neither selection starts
audio. Seek and Play remain explicit actions.

Keep **Add section**, **Split here**, **Merge previous** and Undo accessible in
the working toolbar. A persistent lower area contains the waveform, time ruler,
Play/Pause/Stop, **Starts here**, **Play before cue**, save status and Save/Done.
Use reserved grid rows and one scrolling content area, not floating controls over
the last lines. At narrower tablet widths collapse the outline, not the chart
or the transport. Phone usability can degrade to basic scrolling/editing; phone
dimensions must not constrain chart grouping or font sizes.

**Performance preview** switches the main area to the real renderer. Select
Scroll/Pages and an actual-size tablet/computer target. Do not run a second
pagination approximation. The waveform and save controls stay in their reserved
area while previewing.

### Structural actions

- **Add section** offers a clear choice to insert a new empty section before or
  after the selected section. Name it, type/paste text, and place its cue. This
  covers a missing intro, solo or outro without needing an existing lyric row.
- **Split here** divides at the selected chord/lyric pair. Chords and their words
  move together. It creates one new section and one visible timing marker.
- Dragging a divider changes the text assigned to adjacent sections. Keyboard
  Move divider up/down remains available. It does not reorder the song's words.
- **Merge previous** removes a divider, concatenates the text in order and keeps
  the earlier start. Undo restores both sections and cues. For the first section,
  offer Merge next. Removing a divider must never delete its content.
- Deleting actual text is a separate explicit edit. Deleting an empty section is
  straightforward; deleting a populated section belongs under More with a clear
  explanation and Undo. Repeated choruses have distinct section/row identities.

Use matched timing evidence to seed a new split where defensible; otherwise give
it a visible estimated start between its neighbours only when the interval is
plausible. With no defensible interval, leave the cue explicitly unplaced. Do not
force a millisecond-long first section to satisfy validation. Moving text across a divider
keeps the existing start until changed and notes the edit in timing details.
Do not silently redistribute the remaining section timings after a content edit.

Add-before-first at a positive existing musical start creates an intro at zero
and preserves the old start. When the current first block already starts at zero,
the user must place the following block's new start; the editor must not pretend
that two sections can start at the same time. The trailing interval ends at the
known song duration. Gaps can be explicit empty/instrumental sections.

### Timing actions

Every placed section has exactly one start marker. An unplaced section appears
in the outline with **Set start**, not at a fabricated waveform position. Drag
a placed marker, enter a time, or press
**Starts here** while listening. A **Next section starts now** shortcut supports
one pass through the song; display the target section's name before the tap.
Both actions edit the same section start seen in the waveform and used in both
performance views. Remove **Page starts here** and its separate page-cue editor.

Retain `Matched`, `Estimated`, `Manually placed` and `Checked during playback`,
and add `Unplaced` where no usable time is available. Keep these as provenance
available in timing details, not a checklist or a badge on every performance
section. Listening confirmation is optional. Show ordinary cue labels to whole
seconds by default; finer adjustment may remain available in the editor without
implying estimates are that accurate. Invalid/crossing markers are constrained
visibly with feedback, rather than silently reordering sections.

Keep one whole-chart offset under Timing tools for a uniformly shifted chart.
It is distinct from the display's read-ahead preference. **Starts here** subtracts
that offset once; it never saves the read-ahead adjustment into musical timing.

Import drafts autosave during review. Native editor drafts remain recoverable;
structural changes save to REAPER after playback stops, as today. Pure timing
corrections to the confirmed native chart can retain the existing guarded live
save path. Do not mix a pending structural draft with live commands referencing
the old section indices. Show whether changes are saved in the draft, confirmed
in REAPER, or still require saving the project.

## Pages: the user chooses the contents

One section equals one page, at every screen size. Change page contents by moving
its visible section divider or editing its text. There is no downstream automatic
page allocation and no page-only timing. Previous/Next navigate these sections.

Fit against the actual chart-content rectangle after the real header, controls
and optional next-section preview have been measured. Replace the fixed 280px
deduction. Opening a menu must not shrink the working area or create new pages.
Use a small reserved timing/status area so entering Timing is also stable.

Use a comfortable preferred font (initial targets: 28px tablet, 32px desktop),
then reduce it to fit the complete section. Treat 18px as the initial minimum
for fit-to-page, subject to visual calibration. Font preference is per device.
Wrap chord/lyric pairs together at appropriate boundaries; preserve their
alignment, chord spelling, repeat marks and transposition/capo behaviour.

The editor's preview reports concrete results, for example:

`Tablet landscape: fits at 24px. Laptop: fits at 28px.`

If fitting requires smaller text than the preferred size, show a modest **Text
will be reduced** indicator. If it cannot fit at the readable minimum, keep all
content accessible via vertical scrolling inside that section and offer **Split
here** or **Use Scroll view**. Do not silently cut off content, create another
timed page or force unreadably small text. This is the deliberate compromise
when a user chooses a very large block.

Fit checks are preview advice, not import blockers. Reference targets are tablet
landscape 1024x768, tablet portrait 768x1024, laptop 1366x768 and desktop 1920x1080,
each using the real application chrome. Actual window size still wins at runtime.

Add **Suggest splits** for oversized sections: propose ordinary section boundaries
at source paragraphs, repeated passages or dependable matching evidence. Preview
their text and cue implications, then accept selected proposals. This is optional
help for Pages, never automatic repagination or a second set of timestamps.

## Scroll: the full chart stays available

Render every section in sequence, with the previous and following material
visible around the current section. Use a consistent comfortable font rather
than shrinking each section. Highlight the current section with a restrained
border/background and retain a compact section index.

Recommended behaviour:

1. Follow confirmed audio position using the same section starts as Pages,
   including estimated starts. Confirmed transport does not mean confirmed chart
   alignment. Put
   the current section near the upper quarter of the visible chart, retaining
   some previous context. Keep the next section visible where space permits.
2. For a section that fits comfortably, hold the text still. Move only when the
   reading area needs to advance, using a short transition and read-ahead.
3. For a section taller than the available area, use gentle, bounded movement
   over its approximate interval, keeping surrounding text available. Start with
   simple section-based following; a new row-tracking engine is not required.
   Guard against impossible intervals and excessive speed. Fall back to a broader
   passage or hold locally where no useful estimate exists, without switching
   the whole chart to manual mode. Clamp at the document end and cancel stale
   animations. Never rush through long text because of a tiny guessed interval.
4. A long section with pauses, uneven phrasing or repeats may need one additional
   split/cue. **Split here** creates the same normal section used in Pages; do
   not create a separate scroll-marker editor. Accurate line highlighting is
   outside this feature.
5. Mouse wheel, touch drag, scrollbar or navigation keys suspend following.
   Show **Resume following** prominently. Do not snap back after an arbitrary
   timeout. Selecting another section for browsing must not seek the audio.
6. Seeking, looping and switching songs recompute from the current audio position,
   not elapsed wall time. While following, seeks/loops jump to the correct place;
   when browsing, preserve the user's position and show where playback is.
   A newly selected song starts at its own current position with Follow enabled.
7. Pause stops movement. Disconnection stops movement and shows status; returning
   data resynchronizes only if Follow remains enabled. Respect reduced motion.

Read-ahead moves the viewport without making an upcoming section appear to be
the one currently sounding. Use the real playhead for the active-section label.
Retain the existing 0.75s read-ahead initially, applied in wall-time terms using
the playback rate; keep it separate from the shared chart offset.

Resize, browser zoom, font changes and Show chords recalculate geometric offsets
while retaining the selected/visible section and row identity. Store no pixel
positions as song timing. Native following uses REAPER position; importer
following uses validated audition audio. Neither uses a constant pixels/second
timer independent of playback.

Default new display preferences to **Scroll, chords shown**. Preserve an existing
explicit Pages/chords preference until the user changes it. Mode/font/show-chords
are per-device display settings; content and musical cues remain shared.

Charts with uncertain or unplaced cues remain readable, importable and eligible
for automatic following. Use available anchors, source order and song duration
to seed coarse estimates for the gaps. Keep these estimates in the same section
model used by the editor and both views; never label them as confirmed or replace
saved manual starts. Where no usable interval can be inferred, hold that passage
with manual scrolling/Next available and resume following at the next usable cue.
Do not skip its text or require every boundary to be checked first. With no usable
timing or duration at all, show the full readable chart with manual navigation;
offer timing tools without making them a prerequisite for playing the song.

## Shared document and implementation boundaries

Introduce chart document schema 3 to make the timing change explicit. Keep the
existing transport envelope separate: the outer ReaSetCL envelope need not change
version just because its nested chart document changes.

```text
chart schema 3
  revision, duration, timing_offset, source/provenance
  sections[]                         // the single ordered timing/display unit
    id, label, start?, end?           // null for unplaced cues/unknown intervals
    timing_status, review_reason
    rows[]
      id, kind, text, chord_line, anchors, line_modes, repeat data
      source_span?                   // retained musical content can be audited
      timing_evidence?                // suggestion provenance, not a page cue
```

No active `row.page_cues`, independent lyric offset, or generated page timestamp
belongs in schema 3. Retained legacy evidence lives in migration/source snapshots.
The rendered pages/scroll geometry are disposable browser calculations; they
must not rewrite the document or require a generator rerun after resizing.

Placed starts must increase in chart order and remain inside the recording;
unplaced starts are explicitly null, not NaN, zero or epsilon placeholders.
Derive an end only when the adjacent boundary is known (or the song end for a
placed final section). Include an `unplaced` state in Python/Lua/browser
validation. A zero-time opening display block can still represent an intro or
unscored opening; do not make all following unknown cues equally authoritative.

Separate source lyric evidence from chart-derived lyric display items before
changing `lyric_items()`: currently generation uses that helper for matching too.
Otherwise using the chart's own generated lyrics as alignment evidence could
create a feedback loop. Internal REAPER text items may remain as compatibility
projections of the canonical chart, never a second authorable source of truth.

Share pure normalization, section lookup, row rendering and measured layout
between importer preview and native performance. Continue vanilla JavaScript and
the embedded single-file ReaSet deployment. Update the embedding/extraction tool
and server route together; do not leave a stale standalone paginator. Native
playback/editing must remain independent of the optional importer service.

## Existing songs and half-finished imports

Migration is essential; hiding old controls would not solve the underlying model.

- Read schema 2 and legacy text-item songs. Create a deterministic in-memory
  adapter for display/editor access, without rewriting projects simply on open.
- Preserve authored text, chord columns, repeats, section labels and stable IDs
  wherever possible. Do not fetch a new source or regenerate over manual edits.
- Keep current effective section starts and whole-chart offset. Convert each
  explicit manual page cue into a visible section boundary/cue at its stored
  row/column, with a continuation label. Do not convert every approximate lyric
  row cue into a section: that would recreate the excessive page count.
- Where a manual cue begins inside a wrapped row, split the row losslessly at
  that column and translate the remaining chord offsets. Retain source-row
  lineage. If a boundary cuts through a chord/word, several cues conflict, or
  times cross, preserve the original snapshot and present the specific cue as a
  migration issue for resolution. Never silently discard a checked cue.
- Resolve old lyric/chord checkpoint repairs against the effective chart timing
  that is actually displayed. Do not add both repair scopes or apply an offset
  twice. Conflicting legacy scopes remain in the backup with a review explanation;
  the canonical chart is the authority for the new view.
- A conversion with unresolved conflicts stays available through the legacy
  reader until reviewed; it is not advertised as fully converted. Once accepted,
  schema 3 has only section starts, not an invisible live legacy cue layer.
- Lyrics-only legacy songs become words-only chart sections using their existing
  grouping/timing, preserving all text. No chart/source remains an explicit empty
  state with Create chart, not an exception or a fabricated progression.
- Persist conversion only on explicit chart save, import Apply, or a selected
  library operation. Keep the prior document/checkpoint state for Undo/Restore.
  Offer a **Convert chart display (keep text and checked cues)** library operation
  separately from source regeneration. It must not require reimporting audio,
  resetting song tempo/key, paid Fadr work or click regeneration.
- Migrate resumed queue tab names (`lyrics`/`chords` -> `chart`), editor view and
  legacy offset drafts once. Preserve stem choices and the selected source.
  Fold offsets into the effective existing draft exactly once; authored drafts
  take priority over regenerating from evidence. Test this against real saved
  jobs, not just newly created reviews.
- Reject old browser writes that would downgrade or corrupt schema 3. Preserve
  revision/project/song guards and display a refresh message when a stale client
  uses `pagecue` or an obsolete lyric-replacement endpoint on a converted chart.

## Work order

| Phase | Deliverable | Main files |
| --- | --- | --- |
| 1 | Expanded stem previews with independent collapse and shared audition ownership | `tools/importer-workspace.js`, `tools/importer-workspace.css`, `tools/importer.html` |
| 2 | Source conservation, typed notation/instructions, trustworthy reference selection; schema 3 with unplaced cues, evidence/display separation and reversible migration | `tools/jamroom_chart.py`, `tools/jamroom_chart_author.py`, `tools/jamroom_import.py`, `Requirements/ReaSet_ChartAuthor.lua`, `Requirements/ReaSet_ChartEdit.lua` |
| 3 | Shared section renderer, measured Pages, full-chart Scroll and Show chords | `ReaSet.html`, shared embedded chart-display code, `tools/embed_chart_author.py`, importer script route |
| 4 | Unified editor with Add/Split/Merge, all cue markers and real performance preview | `tools/chart-author.js`, native chart save commands |
| 5 | Stems/Chart importer, source/timing tools consolidation, durable draft/apply migration | `tools/importer.html`, `tools/importer-workspace.js`, `tools/importer-queue.js`, `tools/jamroom_import_queue.py`, `tools/jamroom_importer_server.py` |
| 6 | Native publication, legacy adapters, explicit library conversion, undo/restore and stale-client guards | `Requirements/ReaSet_ChordsLyrics.lua`, `Requirements/ReaSet_ChartUndo.lua`, `tools/jamroom_song_transaction.lua`, `tools/jamroom_chart_library.py`, `tools/jamroom_updates.py`, import generation |
| 7 | Scenario/visual/playback verification, documentation and normal release delivery | existing test/verification tools and setup/user docs |

Implement readers/adapters before switching any writer to schema 3. Phase 2 can
land compatibility support, but schema 3 writing remains gated until editor,
publisher, importer and transaction paths all accept it. Do not publish a release
with mixed readers/writers. The isolated stem fix can ship separately.

Bump the chart generator when generation changes, update both native/importer
assets together, and deliver through the standard implementation/update branches.
Library conversion and source replacement remain explicit user operations.

## Acceptance scenarios

The primary usability check comes before timing refinement: import an ordinary
song, leave timing tools unopened, press Play and follow a readable chart. Repeat
with a few cues several seconds early/late and one missing cue. Context and calm
movement must make these tolerable; the user can scroll freely and resume with
one action, without a forced review pass or disabling the rest of the following.

1. **Bulk imports:** open a 12-stem review, inspect every waveform without
   expansion clicks, audition several stems, change routing, switch songs and
   return. No overlapping audio, lost choices, unsolicited scrolling or hidden
   Apply button; no eager download of all preview audio.
2. **Resume:** close halfway through a chart edit and restart. Restore selected
   job, source, edited text, section boundaries, cue times and review state.
   Repeat with a real pre-upgrade job containing a lyric offset and page taps.
3. **One timing pass:** correct section dividers, play once, mark each start,
   Apply, then open native Scroll and Pages. Both use exactly those starts.
   No follow-up page-timing pass is needed.
4. **Missing instrumental:** Add intro/solo, enter chord-only rows, set its cue,
   merge and undo. No dropped chords, text, repeat marks or invalid zero-length
   intervals. Hiding chords still retains the instrumental interval.
5. **Large section:** deliberately include many chord/lyric pairs. Pages uses
   available space and shrinks within limits, warns appropriately, and never
   silently creates more timed pages. Scroll shows all rows at comfortable size.
6. **Uneven long section:** test a held line, instrumental pause and repeated
   refrain. Approximate long-section scrolling is identified as approximate;
   adding one split makes both views follow it without another timing system.
7. **Following and browsing:** manual scroll holds until Resume; test pause,
   forward/backward seeks, loops, stopped selection, changed master playrate,
   reconnect and immediate song changes. No stale animations or timer drift.
8. **Content projection:** Show chords on/off retains section/cue identity and
   exact lyrics. Test chord-only songs, plain lyrics, Unicode, capo/transposition,
   repeated sections and unusually long rows.
9. **Responsive layout:** inspect screenshots at 1024x768, 768x1024, 1366x768 and
   1920x1080, plus a short window and browser zoom. Open menus/timing controls;
   last rows, waveform, status and actions remain accessible. Resizing never
   mutates cues or creates a different section count.
10. **Persistence and regression:** conversion twice is identical; snapshots
    restore the original; concurrent edits/stale tabs cannot overwrite; a library
    conversion preserves all media/tempo/key/levels/click settings. Save/reopen
    and native Undo work. Apply to a populated disposable setlist and confirm
    native/browser playback still starts correctly after import.

Extend the existing chart-document/authoring/browser/queue tests with shared
schema/migration fixtures. Use synthetic chart text for public tests and cached
real songs locally for visual/audio checks. Run the existing
`verify_song_visual.py --playback-check --edit-check` and
`verify_import_playback.py --queue-guards` workflows only during implementation,
against disposable projects with stopped REAPER and saved originals. Reading this
plan or creating its layout board performs no project/library modifications.

Definition of done: friends can import a song and start playing with a readable,
approximately following chart without opening timing tools. If they choose to
refine it, they can author a passage and mark its time once, then use Pages,
Scroll or hidden chords on computer/tablet without another timing exercise.

Additional release gates from the real-library audit: no Boston opening loss;
retain same-line riff chords; recognize compound solo headings; preserve tab
without classifying it as sung lyrics; do not force Chasing Cars/Gold On The
Ceiling into every inferred lyric-gap fragment; reject invalid timestamp tails;
recover Two Strong Hearts through an identity-checked lookup; never rapid-scroll
the no-evidence Chain Reaction stress case. Test these using small synthetic
public fixtures and the retained private real examples.
