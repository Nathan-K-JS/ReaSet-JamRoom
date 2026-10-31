# Recording count-in audio — v3.23.1

31 October 2026. Builds on the [recording play-along update](RECORDING_PLAYALONG.md).
Development and native capture use the [isolated live-PC workflow](LIVE_JAMROOM_WORKFLOW.md).

## Findings

Read-only inspection of the latest recording journals and generated audio found
103.448 BPM for I Just Might and 76.531 BPM for Great Expectation. Those match
the opening click spacing used by v3.22.2, but Great Expectation's song tempo is
150 BPM and its click is muted and flagged `needs_review`. The controller was
letting this rejected click override the song tempo. The journal's 6.272-second
lead-in confirms that the muted click was used. An enabled click supplies the
audible pulse; a muted click must leave the armed song's BPM authoritative.
The imported BPM label can represent half/double an enabled click pulse; preserve
that audible grid when enabled, including playback rate. This read-only
inspection is not a claim about the audio that reached the IEMs.

The earlier verification measured generated WAV files, without capturing their
native playback or testing a first beat more than one beat into the source.
`firstBeat % beat` discarded whole silent beats at the opening. For a first
click at 1.3 seconds on a 0.8-second grid, native output reproduced a 1.6-second
gap after the last count-in pulse. Great Expectation has this delayed-opening
shape. A second reproducible fault was trusting a stale review sidecar over a
replacement click WAV: count-in and played click could then have different BPM.

## Changes

- Read the installed PCM click first, using the existing bounded 30-second
  scan starting at the source trim; consult its review sidecar only when audio timing cannot be read.
  Apply item position, source offset and take playrate before deriving timing.
- Ignore muted click items when choosing count-in timing. A muted/absent click
  uses the armed song's validated BPM, never the unrelated project tempo. An
  enabled click that cannot be read still fails explicitly instead of guessing.
- Retain the first click's full time as well as its phase. Continue the
  generated pulse through missing opening beats until the installed click
  begins. The two-bar lead-in and original song/capture coordinates stay intact;
  accompaniment, original click media and tempo map are not rewritten.
- Explicitly set generated count-in take rate, offset and non-looping playback.
  The count-in and song share native transport and master playback rate. Free
  jam uses the selected BPM/metre at rate 1, independent of a previous song rate.
- Show the confirmed audible count-in BPM during capture. Publish the recording
  controller build so deployment checks can distinguish loaded code from files.

Variable-tempo songs retain their installed click timing. The count-in uses the
median opening pulse interval and anchors to the first installed beat; it does
not quantize the song or replace its click with a fixed grid.

## Acceptance

`tools/verify_countin_audio_isolated.py` creates a private REAPER configuration,
copies Lua and the SWS binary, uses Dummy Audio and synthetic files, and removes
all hardware sends before native Record. It captures the count-in and song/jam
click together through an internal track send. FFmpeg decodes the actual native
recording; assertions measure pulse intervals, the handover and source onsets.
All evidence is retained; only its own spawned process is terminated.

Twelve cases cover 103/150 BPM songs, 80%/120% playback, trimmed/stretched click,
delayed first beat, a variable opening with representative beat timestamps,
stale sidecar, a muted 75 BPM click with a 150 BPM song at normal/80% speed,
76 BPM free jam, and 137 BPM free jam in 3/4 while the previous
project rate is 60%. Repeat takes reuse a session and replace its generated
count-in; the cursor points at another song while the intended song is armed.
Free-jam capture has a separate session at its chosen tempo.

Before correction the native delayed-start case failed by 800 ms. All twelve final
native captures pass: maximum count-in/transition interval error 0.063 ms;
maximum measured source onset error 0.042 ms. Evidence and decoded measurements:
`C:/Users/natha/AppData/Local/Temp/reaset-countin-audio-knwapj0l/analysis.json`.
The reproduced failing baseline is `reaset-countin-audio-fiiliy3u/analysis.json`
under the same temporary root. No live transport, original recording/media,
library or mixer was used for tests.

The browser/chart/recording regression command is in RECORDING_PLAYALONG.md.
The play-along native verifier additionally checks pause/resume, automatic stop,
review, another take, Add part, cancellation and discard. The older preparation
verifier now allows the bounded sample rounding from reading the actual WAV
and restores its fixture mute between preparations, as core:park does between
real takes. Its earlier stub left the original click muted for the second case.
130 browser/Lua regression tests pass with no skips. The native play-along run
also passes; evidence/screens are in `reaset-playalong-4x30j3zf/` under the same
temporary root. All three private native preparation cases pass in
`reaset-recording-chart-4pazwgy1/` (maximum generated onset error 0.105 ms).

## Delivery

No dependencies or library migrations are needed. Push implementation and the
standard update branch after all required checks pass. Installation and bridge
activation must preserve unsaved REAPER work; recording-controller initialization
can perform recovery saves, so a hot reload is not a substitute for that gate.
Refresh tablets after the new browser and native controller are both activated.
