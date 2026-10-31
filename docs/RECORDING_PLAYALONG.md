# Recording as play-along

31 October 2026. The requested workflow is song selection, input selection,
ordinary chart play-along while recording, then take management after stopping.
Implementation is in a separate development checkout under the mandatory
[live workflow](LIVE_JAMROOM_WORKFLOW.md).

## Approach and acceptance

- Reuse the existing chart and transport. Once REAPER confirms a song take,
  leave the setup workspace and show the normal chart, preserving its display
  preferences. Show recording status and Stop/Pause without covering the chart.
- Start each take following the song from its beginning, including count-in.
  Keep the recording coordinates authoritative across independent chart,
  recording and transport polling. Capture changes must invalidate the native
  chart publication even when the song and project change count stay the same.
- Put a song chooser in setup, using confirmed native cursor selection. Keep
  input selection and readiness before recording. New take and Add part still
  prepare before starting; cancellation must preserve earlier audio.
- Open review after confirmed capture completion on the screen that started
  the take. Other tablets retain their chosen view. Discard, record another,
  overdub, mixing and exports remain after the take. Free jam retains its timer.
- Exercise the complete browser workflow, stale/reordered publications,
  repeat takes, pause/resume, tablet sizes, recovery and ordinary playback.
  Run native capture with synthetic media in a private Dummy Audio process.
  No live project, recording, browser preferences or hardware is test data.

The chart/transport reuse follows the user's requested direction. Automatic
review on the controlling screen, with other tablets keeping their view, is
an implementation choice to avoid interrupting each musician's display.

## Findings

The capture workspace replaced the chart with meters and hid normal transport.
The chart bridge only invalidated its payload for song/project/edit changes;
it did not invalidate for capture coordinates or transport recording state.
Earlier tests started with recording already active and manually incremented
the project edit count on stop, missing the real transition from a loaded chart.

## Verification

127 checks pass with no skips across the browser, chart, recording protocol,
parts, guards, performance, tempo and recording workspace suites:

```powershell
$env:PYTHONPATH='tools'
python -m unittest test_recording_playalong test_recording_chart test_recording_guards test_recording_parts test_recording_performance test_recording_protocol test_tempo_bridge test_workspace_layouts.RecordingWorkspaceTests test_unified_chart test_browser -q
```

Every browser request is intercepted and every Lua unit test uses in-memory
REAPER substitutes. Coverage includes delayed capture publication without a
project edit, independent clock updates, initial chart loading, another take,
song/input selection, confirmed pause/review, manual browse, another tablet,
reconnecting during a take, offline Stop, ordinary song automation and rotation.
Screens from 390 x 844 through 1366 x 768 retain chart width and accessible Stop;
the existing workspace suite also checks 320-pixel screens.

The older resumed-import fixture now contains a valid saved chart/stem review
and restores its review step. Its target-confirmation, cancellation and safe-stop
assertions all pass. No importer flow was changed to bypass those guards.

`python tools/verify_recording_playalong_isolated.py` passes on REAPER 7.78 with
a new private resource/configuration folder, copied Lua/SWS, a synthetic library
and Dummy Audio. Dummy Audio has no physical inputs, so the harness substitutes
input availability and uses native track-output recording, removing hardware
sends before capture. It verifies actual count-in/capture/pause, automatic end,
saved audio, preparation cancellation, another independent take, Add part,
discard returning to the parent arrangement and preservation of all three
recorded files. It then replays actual native state/chart publications through
the browser wire handlers and checks chart/review visibility and song position.

Native evidence, synthetic recordings and screenshots:
`C:/Users/natha/AppData/Local/Temp/reaset-playalong-o_kizcsr/`.
These are software acceptance checks; no live song, recording, mixer, device
latency or physical tablet audio was used as test data.

## Release

Version v3.23, 31 October 2026. The browser, recording controller and chart
publisher all need the new version. Follow the standing deployment workflow:
checkpoint the importer, wait for stopped/idle state and preserve unsaved work,
install and safely restart affected services, then refresh the browsers. No
dependency changes or library migrations are required. Deployment recovery
snapshots and read-only verification belong under `C:/JamRoomDev/deployments/`.
