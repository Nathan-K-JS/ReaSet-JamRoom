# Recording transition performance

3 October 2026. The user approved implementing the recording cleanup fix and
investigating the remaining import/save delays. Development is on
`codex/recording-performance`, outside the live `C:\JamRoom` installation.
The [mandatory live workflow](LIVE_JAMROOM_WORKFLOW.md) still applies; this is
isolated test evidence, not live deployment or acceptance.

## Finding and change

`ReaSet_RecordingTimeline.lua` journals original mutes for library items before
recording creates temporary playback items. Chart items are included. Previously,
`ReaSet_RecordingCore.lua`'s `park()` scanned the entire project once for each
journal GUID. With 8,388 items and journal entries, this requires 70,358,544 item
lookups during restoration. Stop, review, preparation and recovery paths use
this cleanup.

Restoration now visits each current item once and looks up its original mute in
the existing journal. It runs after temporary-item cleanup, retains no item
pointers between transitions, skips GUIDs that no longer exist and leaves
unjournaled library items unchanged. Original zero and nonzero mute values are
preserved. Empty journals add no restoration scan. Recording-item parking,
disarming, pitch/rate restoration and clearing the journal only after success
retain their existing behavior. Project saves and recovery checkpoints are
unchanged.

## Verification

18 focused tests pass: five new restoration regressions plus existing recording
parts, guards and protocol tests. Coverage includes the large-library operation
count, original mute values, sparse/deleted GUIDs, cleanup order, pitch zero,
disarming, repeat calls and retaining the journal after a simulated native error.

```powershell
python -m unittest tools.test_recording_performance tools.test_recording_parts tools.test_recording_guards tools.test_recording_protocol -v
```

Native measurements used REAPER 7.78, a fresh private resource/configuration
directory, a separate process with Dummy Audio and a generated project. The
fixture has 46 tracks, 52 song regions, 380 audio items and 8,008 chart items.
Synthetic extstate padding makes the saved project approximately 14 MB.
Import adds ten separate 210-second silent WAVs and 200 chart items. No live
project, media, configuration or importer pointer was copied or modified.

| Operation | Measured elapsed time |
| --- | ---: |
| Fixed `park()`, all 8,388 mutes restored and verified | 0.033 s |
| v3.21 `park()` | Still incomplete at the 15 s comparison limit |
| Save project, journal and verify receipt | 0.090 s |
| Repeat save and verification | 0.074 s |
| Save backing snapshot | 0.035 s |
| Reconcile library gains | 0.012 s |
| Import ten stems and 200 chart items | 0.141 s |
| Reconcile after import | 0.013 s |

The old-code comparison completed 13.5 million item lookups before its time
limit. Its total duration is **not** measured; no exact whole-workflow speedup
is claimed. A smaller initial native fixture measured fixed cleanup at 0.054 s.

`tools/profile_recording_performance.py` reproduces the native comparison. Run
with an isolated development Python environment on Windows:

```powershell
python tools/profile_recording_performance.py --sws "$env:APPDATA\REAPER\UserPlugins\reaper_sws-x64.dll"
```

The harness copies only Lua code and the supplied SWS DLL into a newly allocated
temporary directory. It verifies its resource path, Dummy Audio and empty
initial project before opening generated data. It uses no web ports, hardware
outputs or transport operations. Artifacts remain for inspection (approximately
250 MB); the printed PID identifies the only process it may close. Baseline
code defaults to Git revision `ee51aac`. Reports include per-call import timings
and any failure. The larger run's local evidence is at
`C:\Users\natha\AppData\Local\Temp\reaset-performance-g4m0eg55\result.json`.

## Remaining limits

The native test confirms the recording cleanup bottleneck. It does not reproduce
the reported 30–60 second final-import freeze. The fixture does not run all
background bridges, use the live chart documents, exercise the importer HTTP
handoff, or reproduce OneDrive/antivirus behavior at the library location.
Read-only inspection found the live project readable in about 26 ms, which
does not establish its save latency. No storage relocation or sync changes
are justified by these results.

Keep the save/recovery checkpoints and import redraw/undo behavior intact.
Investigating any remaining live import lag requires narrowing which stage
stalls; the retained isolated profiler measures native Apply calls but is not
an end-to-end importer benchmark. The recording fix must be deployed explicitly
before it can improve the running rig. No live action, restart, deployment or
library migration was performed during this work.
