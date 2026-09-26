# Unified charts — v3.21

Import review now has **Stems** and **Chart**. Stem previews open together;
collapsing one does not close the others. Only the selected audio plays.
There is no separate lyric-timing checklist. Background lyric matches can help
suggest timing, but a chart is ready to use without checking every cue.

## Playing

Open **Chart** in ReaSet. **Scroll** shows the whole chart with surrounding
sections and follows approximately. Scrolling or browsing pauses following;
**Resume following** returns to playback. Pause, seeks and loops use REAPER's
position. Text size is remembered on each device.

Set section timings at the **actual musical start**, not early. The visible
**Turn/scroll early** control brings the chart ahead by **2 seconds** by default;
choose 0–4 seconds to taste. This is remembered on the browser/device and never
changes the saved section timing. It applies to Pages and Scroll, including
seeking. Long sections scroll through their full text span, keeping the estimated
reading position near the upper third with more material visible below. This is
approximate following between section markers, not individual lyric tracking.

**Show chords** hides or restores chords on that same chart. It does not create
different words or timing. The older Lyrics shortcut opens the chart with chords
hidden. **Pages** shows one authored section at a time. Long sections shrink only
to a readable minimum, then scroll; changing screen size never invents pages.

## Editing

Use **Edit chart** in ReaSet or **Chart → Review / edit chart** in the importer.
The editor shows surrounding sections. Write chords above words; recognised
chords are gold. **Auto / Chords / Lyrics** can override a line's recognition.
Tagged source chords retain their identity even alongside chord-shape notation.

- **Add section** inserts an empty section before or after the selected one.
- **Split here** divides at a chord/lyric pair. **Merge previous/next** joins text.
- Drag a divider between adjacent sections or use Move divider up/down.
- Drag a waveform marker, enter a start time, or tap **Starts here**. The marker's
  pointed tip and vertical guide show the exact time; its rectangle is a handle.
- **Next section starts now** advances the target while setting its start.
- **Timing → Whole chart offset** shifts the chart together.
- **Preview** uses the same Scroll/Pages renderer as ReaSet at the available size.

Timing adjustments are optional. Source headings remain the default grouping;
breathing gaps no longer generate extra instrumental pages. Missing timing uses
coarse estimates, and unsuitable lyric timestamps cannot compress the chart into
tiny intervals. No line-by-line timing or second page-timing exercise is required.

Drafts survive closing and reopening. Importer edits autosave; native content
changes are saved through REAPER after stopping playback. Save the REAPER project
to retain them on disk.

## Existing library and resumed imports

Old review tabs reopen as Chart. Saved routing, names, searches and chart drafts
remain available. Existing page cues convert into visible section boundaries
where this can preserve the text and timing. Conflicting cues keep the legacy
display; Edit chart offers **Use section starts** with an undo snapshot.

In **Song library → Update songs**, choose **Convert chart display (keep text and
timing)** for a local conversion of selected saved charts. It reads current project
data, keeps previous versions, and does not regenerate audio, click or volume
matching. Existing protected songs stay protected. Use a normal chart/library
update when you want to regenerate an old source using the corrected parser.

The parser now preserves music before the first heading, chords beside headings,
compound solo headings and tablature. Conversion alone preserves your existing
text; it cannot restore text missing from an earlier import.

## Installation and validation

Run **JamRoom Update.bat**, restart REAPER and the importer, and refresh the
browser. Confirm **v3.21**. The update does not silently regenerate your library.

v3.21 also removes the backing-control bridge's old 25.6 KB library limit. Larger
libraries no longer lose every stem control when their published data exceeds it.
Reads use small batches with retries; actual bridge errors appear in Backing
instead of being labelled as songs without stems. No song re-import is needed.

Validation includes the regression suite, browser checks at tablet and desktop
sizes, conversion parity and retries, and 53 cached real chart cases from the
45 named Fadr recordings. Those cases retain their source grouping and chord
tokens. Disposable REAPER projects verify following, authoring, saved timing,
appending imports and the import guards; the original project remains unchanged.
Room-side X32 and physical tablet testing are separate from these workstation checks.
