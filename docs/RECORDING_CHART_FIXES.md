# Recording count-in and tablet charts — v3.22.2

22 October 2026. Developed in the separate `codex/recording-chart-fixes`
checkout under the [mandatory live workflow](LIVE_JAMROOM_WORKFLOW.md).
Source release and live deployment are separate operations.

## Findings and fixes

- Song count-in previously used `ReaSetTK/bpm:<song name>`, which is an imported
  tempo label. The installed music-following click is generated independently.
  Read-only inspection of the recent Die With A Smile journal found an eight-beat
  lead-in of 6.075949 seconds: 79 BPM. Its installed click's opening pulses are
  approximately 158.73 BPM, with an overall median near 157.89 BPM. Free jam
  has one explicit tempo for both count-in and click and did not have this split.
- Song count-in now reads the installed click's existing beat report, applies
  the item's start, source offset and take rate, and uses the opening pulse
  spacing and phase. A bounded reader for generated mono PCM16 click WAVs
  supports installations without a readable report. Neither path rewrites the
  report, click or tempo map. An unreadable installed click produces an explicit
  count-in error instead of guessing from the unrelated tempo label. Songs with
  no click retain the validated imported-tempo fallback. Free jam is unchanged.
- Recording runs accompaniment in a temporary area after the library. The chart
  bridge used this physical position for song discovery, and the browser used it
  for chart progress, losing the song or selecting its final section. The
  recording controller now publishes project-scoped capture coordinates. The
  chart bridge selects the original song and includes those coordinates in its
  chart payload. Both modern and legacy browser readers map native transport
  position back to song time, including count-in and paused recording. Playback
  and review continue to use their ordinary timeline positions.
- The display observed the outer chart host, so expanding its inner reading
  area without resizing that host could retain narrow wrapping. It now observes
  the reading area too. Switching out of a structured chart disposes its resize
  observer and display class. Lyrics fallback now clears its own panel styles;
  it previously cleared the Chords panel instead.

No chart content, saved timing, song library, recording, importer journal,
live browser preference or mixer setting was changed.

## Current verification

The broad regression run completed 111 checks: 110 passed, with the single
pre-existing importer fixture failure described below. The 14 dedicated
recording/chart regressions all passed. Tests use in-memory REAPER substitutes,
temporary synthetic WAVs and fresh headless browser contexts with every request
intercepted:

```powershell
$env:PYTHONPATH='tools'
python -m unittest test_recording_chart test_unified_chart test_browser test_recording_parts test_recording_performance test_recording_guards test_recording_protocol test_tempo_bridge test_workspace_layouts.RecordingWorkspaceTests -q
```

The dedicated recording/chart regressions cover actual count-in PCM pulse
spacing and phase, the half/double-tempo case, WAV fallback without source
writes, source trims/rates, native bridge publication, stale project rejection,
song-start rounding, count-in/capture/pause/stop, Scroll and Pages following,
manual browse/resume, tablet rotation and inner-area width recovery.

One pre-existing broad-suite test remains incompatible with the guided import
review: `test_resumed_import_target_confirmation_and_safe_stop` attempts Apply
with an unreviewed empty-stem fixture. Its disabled-button timeout reproduces
unchanged at baseline `5752324` in the separate import-recovery checkout.
This recording fix does not change that importer flow.

`python tools/verify_recording_chart_isolated.py` also passed on REAPER 7.78.
It creates a new private resource/configuration directory, verifies Dummy Audio
and an empty project before any fixture writes, and uses only generated media
and copied Lua code. Song count-in preparation passed at project rates 1.0 and
0.8 with a deliberately wrong imported tempo, and free-jam preparation passed
at 100 BPM in 3/4. Generated pulse-onset error was at most one 48 kHz sample
(0.02084 ms). This measures generated audio, not live capture or X32 latency.
Transport remained stopped throughout; only the harness-owned process closed.
Final artifacts are under
`C:/Users/natha/AppData/Local/Temp/reaset-recording-chart-4m1ow0l3/`.

The live REAPER instance, service ports 8080/8765, library, recordings, browser
profiles and X32 were not operated or modified. Physical tablet and room-audio
acceptance remains a separate, explicitly authorized deployment/acceptance step.
