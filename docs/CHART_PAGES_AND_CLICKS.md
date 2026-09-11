# Chart pages and rehearsal clicks — v3.4

## Using it

- In ReaSet, open **Timing**. **Earlier 0.5s**, **Later 0.5s**, or the numeric
  offset moves the entire song's chart timing. Positive offsets delay it.
  **Reset** returns to zero. The offset is saved in the REAPER project and shared
  by connected browsers. Section/page taps remain available and account for it.
- Pages turn **0.75 seconds early while playing**, with the first chord/lyric
  line of the next page in a preview. Stopped browsing uses the saved cue.
  Timing controls overlay the preview area; opening them cannot repaginate the
  chart and invalidate the page cues being edited.
- **Chart** and **+ Lyrics** are the chord views. Big and Timeline are removed;
  their old saved preferences fall back to + Lyrics.
- Every newly prepared import adds an unaccented click to **PB CLICK** through
  the normal Jam Room CLICK group. Use the normal group controls to mute it.
- For existing songs, open **Update charts & click tracks**, select
  **Click tracks only (keep charts)**, then **Update selected** or
  **Update whole library**. This also works for charts marked Keep this version.
  The default **Charts and click tracks** mode retains chart protections and
  the explicit replacement requirement for manual section/timing edits.

Run **JamRoom Update.bat** on the jam-room PC, restart REAPER, and refresh ReaSet.
The updated recovery helper installs missing click-analysis dependencies even
when invoked by an older copy of the updater. Setup and the importer launcher
use the same dependency manifest. This workstation's test imports do not update
the jam-room library; run that PC's chosen library operation afterward.

## Missing instrumental passages

Tested the already-split Fadr recording **Evanescence - Bring Me To Life**,
asset `6a9a76bb4da17246c44951dc`. No new separation was purchased.

The most-voted [source chart](https://tabs.ultimate-guitar.com/tab/evanescence/bring-me-to-life-chords-662308)
starts at Verse 1 and supplies no intro. The old generator displayed that verse
from zero. Explicit lyric gaps inside otherwise vocal sections also disappeared
as independent pages, and repeated vocal text caused Interlude to be renamed Outro.

The shared generator, **source-pages-5**, now exposes an opening gap and explicit
lyric gaps of at least four seconds as instrumental pages. Their boundaries are
estimates, not certified vocal-activity measurements. Written rows and chord
columns stay in order. Missing chords are labelled **chords not supplied**;
the generator does not fabricate an instrumental progression. Vocal interludes
and breaks keep their source names instead of being renamed after a later repeat.

The [second highly rated chart](https://tabs.ultimate-guitar.com/tab/evanescence/bring-me-to-life-chords-1704496)
supplies intro and outro chords. It was selected for the final cached test import
and visually reviewed in real REAPER. Two internal lyric gaps still have no
authored chords and remain labelled. Existing installations keep their chosen
source; select this alternative through Chart tools if desired.

## How clicks work, and their limits

[Fadr's documented metadata](https://fadr.com/docs/api-endpoints) supplies tempo,
sample rate, beat length and offset. Its documented stem outputs do not include
a ready-made click WAV. A global REAPER metronome would also need a tempo map for
the entire multi-song project.

Instead, local [librosa beat tracking](https://librosa.org/doc/0.11.0/_modules/librosa/beat.html)
uses the cached drum stem and Fadr tempo to locate recording-relative beats.
Tempo is constrained: unconstrained detection chose approximately 108 BPM for
Fly Away despite Fadr's 80 BPM pulse. Individual beat positions can still follow
small timing changes. Opening and ending spans without detected beats are
extrapolated. If no usable rhythmic audio is available but valid Fadr metadata
remains, the fallback is explicitly recorded as **Fadr fixed grid**.

The result is an ordinary mono PCM WAV with a click at each estimated beat.
It needs no runtime plugin, network connection, or project tempo-map change.
There are no guessed bar accents or pre-roll/count-in. A half-time tempo estimate
can produce a half-time pulse. These are **estimated rehearsal clicks**: listen
against the recording before relying on them, especially for tempo changes or
long passages without drums. Beat tracking is not a proof of musical correctness.

Content-addressed WAVs preserve previous audio for undo/restore. Cached analysis
avoids repeat work; fresh analysis after initial library loading took roughly
1–2 seconds on this workstation. Source/metadata changes invalidate the cache.
The generated duration includes stem-codec padding through the region end.
Updates only replace importer-owned click items and reject an unowned item on
the generated click track. Click-only operations preserve chart documents and
text items, and use the same durable snapshots and guarded restore path.

## Validation

### v3.4.1 Windows audio runtime repair

The first click release checked installed package versions without loading their
native dependencies. A jam-room import exposed a Numba `_typeconv` DLL load error.
The launcher and updater now run an actual beat-tracking calculation in a fresh
Python process. DLL failures trigger installation of the official Microsoft Visual
C++ runtime matching Python's architecture, with Authenticode verification before
execution, followed by another beat-tracking check. Windows may request elevation
or a restart. The exact missing DLL on the remote PC was not identifiable from
the error alone. Microsoft documents the runtime at
<https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist>;
Numba's installation troubleshooting is at
<https://numba.readthedocs.io/en/stable/user/faq.html#numba-could-not-be-imported>.

If native analysis remains unavailable, valid cached Fadr beat metadata supplies
an explicitly labelled fixed-tempo fallback. It may drift against the recording.
Apply logs, the library chooser and batch results identify that limitation.
Fallbacks remain eligible for click-only whole-library updates and are retried
instead of permanently cached as completed beat detection. Existing click media
remain available for restore. Missing/invalid Fadr metadata still produces an
actionable failure rather than an invented click.

Run `JamRoom Update.bat`, reopen/refresh the importer, and retry the already-split
song. Cached stems do not need another Fadr split. After runtime repair, use
**Click tracks only** to replace any fallback clicks while keeping chart edits.

Validation: 114 automated tests passed, including native-load failure injection,
fallback recovery and whole-library retry eligibility. The real cached Fly Away
audio generated a fallback under the injected DLL error, then 297 recording-based
beats on a healthy retry. Seven live append/playback checks passed in disposable
REAPER tabs; the original project and state counter were unchanged. Healthy
updater startup passed locally. The repair must still execute on the jam-room PC;
this workstation does not reproduce its missing system DLL.

### v3.4 chart and click validation

- 108 automated chart, browser, transaction, batch and audio tests passed; the synthetic
  tempo-drift test checks 95th-percentile click error below 45 ms against known
  attacks. It is a regression test, not a quality score for arbitrary music.
- `python tools/verify_reaper_live.py`: 26 live checks, including offset saves,
  click creation, replacement without duplicates, chart preservation and restore.
- `python tools/verify_song_visual.py "imports/Evanescence - Bring Me To Life" --playback-check --edit-check`:
  actual chart/lyrics screenshots, early page turns, section editing, timing taps,
  offset save/reset, and preservation of the original project.
- `python tools/verify_import_playback.py "imports/Lenny Kravitz - Fly Away" --click-library-check`:
  append imports and native/browser playback, then the actual importer UI's
  whole-library click-only operation on five eligible songs in a disposable copy.
  All five completed, all chart documents were unchanged, and native Play passed
  afterward. The original project and state counter were unchanged.

Local screenshots and receipts are under `imports/.visual/evanescence/`,
`song-fq37g52x/`, `song-h5gjprk7/`, `song-h4kvkg15/` and `append-f4nvkg58/`. Source lyrics and cached
recordings are not committed as public fixtures.
