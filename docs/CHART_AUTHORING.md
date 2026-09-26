# Chart authoring — v3.18

For the current controls and shared Scroll/Pages workflow, see
[Unified charts — v3.20](UNIFIED_CHARTS.md). The separate Lyrics/Chords navigation
and page-timing controls described below are retained here as historical context.

Open **Edit chart** from Lyrics or Chords in ReaSet. In an import review, open
**Chords → Review / edit chart**. A song without a chart offers **Create chart**;
existing legacy words are copied into the draft when available.

## Writing and reviewing

Write chord names on the line above their lyrics. Chords turn gold as they are
recognised. Spaces keep them aligned. Consecutive chord lines work for solos and
instrumental passages; bars, repeats and blank lines remain editable. Tabs expand
to four-column stops. Use the current line's **Auto / Chords / Lyrics** selector
when recognition is ambiguous, particularly a lyric containing just “A”.

Editing uses the original recording's sounding pitch. Capo and performance
transposition are display settings; they are not applied again to saved words or
chords. Both Lyrics and Chords display the saved chart document.

Select a section without starting playback. Put the text caret at a later
chord/lyric pair and choose **Start section here**. **Merge previous** removes the
divider while keeping the text; the first section offers **Merge next**. Drag a section divider from the section list onto
a line in either adjacent section, or use **Move divider up/down**. Pasting a chart
with `[Verse]`, `[Chorus]` and similar headers creates sections needing timing review.

On small screens, switch **Edit / Preview / Timing**. Short windows and phone
keyboard layouts put structural commands under **Tools**, leaving the text and
Save/Stop accessible. The preview uses the performance paginator.

## Timing

The timeline's numbered markers are section starts. Drag a marker, use arrow keys
(0.1 seconds, or Shift for one second), enter its start time, or press **Starts
here** at the desired playback position. Clicking the timeline seeks. Moving a
text divider changes grouping; moving a timeline marker changes timing.

Every section shows its absolute song time and the interval since the preceding
section. Labels distinguish **Matched from lyrics**, **Estimated**, **Manually
placed** and **Checked during playback**. A match is a suggestion, not musical
confirmation. Press **Checked during playback** after listening. In Preview,
**Page starts here** during playback checks the displayed page's cue. Page cues
remain attached to their row and character column through pagination.

**Suggest timing** reuses a retained lyric match for the section's opening line,
when available, and explains its evidence. It keeps checked section starts.
**Play before cue** auditions from two seconds before the selected start.
Chord-only corrections retain lyric timing; changed words require review.

Imports audition the cached original recording, or a cached mix of stems with the
click excluded. Preparing audio reports its status; text editing remains available
if audio cannot be prepared. Waveforms support zoom. This private preview is
separate from the MP3 recording-sharing workflow. ReaSet uses native REAPER playback
and does not require the importer for chart editing or timeline review.

## Saving and changing sources

Import edits autosave into the existing queue journal. Reopen the import after a
restart to continue. Apply installs that authored document; it does not regenerate
over it. Conflicting revisions from another browser are rejected.
The import journal also remembers the last editor view.

Library drafts recover on the same browser/device. **Save chart** waits for REAPER
confirmation and requires stopped playback and no active recording/review lock.
Then **save the REAPER project** to retain the changes after closing REAPER.
Saving chart content replaces any old timing-checkpoint corrections with the
section times displayed in the editor.

Use **Change source chart** to search or paste another Ultimate Guitar chart.
ReaSet opens this in the optional importer. Preview it, then choose **Use this
chart**; closing the preview keeps the existing draft. **Restore previous chart**
recovers the preceding accepted version. Source replacement from Song Library also
uses preview and a project/song/revision check before installation.

One REAPER Undo restores a saved chart edit. Chart snapshots use an inert property
on the existing Lyrics track (master track when necessary), since project extstate
alone does not create an undo step. The background chart script synchronises the
restored snapshot back to the published document. Audio, levels and routing are
not changed by this mechanism.

Library updates preserve authored charts by default. The existing explicit
replacement option regenerates them from sources and retains update snapshots.

## Maintenance and checks

`tools/chart-author.js` is embedded in the single-file `ReaSet.html`. Run
`python tools/embed_chart_author.py` after editing it. This also refreshes the
generated importer copy of the native paginator. The importer serves the editor
and paginator from the native HTML; there is no additional performance dependency.

Validation includes parser and timing tests, queue restart/conflict/source-preview
tests, Chromium phone/tablet layouts, iPhone WebKit editing at keyboard height,
cached-audio origin/click-exclusion checks, real REAPER author/save/undo checks,
full-song visual/playback editing, and append/import queue guards. Evidence from
the test workstation is under `imports/.visual/chart-author/` and the scratch
folders named in its logs. No room-library rebuild is performed automatically.

Install with **JamRoom Update.bat**, restart REAPER and the importer, then refresh
ReaSet and importer pages. Confirm **v3.18**. Physical phone keyboard/browser and
room-network acceptance can be checked on the jam-room setup after updating.
