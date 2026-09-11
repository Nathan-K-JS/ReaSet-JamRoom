# Recording-following clicks (v3.5)

The v3.4 click was not adequately validated. It forced librosa's onset tracker to
use Fadr's BPM, followed strong offbeat attacks around fills, and extrapolated a
fixed grid outside detected beats. If the native dependency failed, it substituted
an unchecked Fadr grid. The synthetic test used click sounds as its input, and
REAPER playback tests established installation/playback, not musical correctness.

## Replacement method

- Reconstruct the music from cached leaf stems, excluding the click. Do not use
  Fadr BPM to select or force the pulse.
- Run the three published Beat This! final checkpoints locally on CPU. These are
  different seeds of the **same model family**, not three independent musical
  authorities. Their disagreement is retained as useful evidence.
- Decode their beat activations with a continuous pulse and locally estimated
  tempo. Temporary half/double-time interpretations do not change the click's
  pulse midway through the recording. Small local tempo changes remain supported.
- Centre activation peaks and reduce frame quantisation without snapping clicks
  to arbitrary drum-fill attacks. Stop at supported beat evidence instead of
  extrapolating an unchecked grid through the ending.
- Check the result against separately extracted drum attacks in 12-second
  windows. Retain the failed windows; do not hide them in an overall average.
  Missing alternate model beats can be reconciled only when independent drum
  alignment and phase consistency support the chosen pulse.

This is a pulse, with no assumed bar accents or claim that its BPM is the only
valid metrical interpretation. Abrupt tempo changes, rubato, syncopation and
drumless passages remain difficult. An absent drum attack does not prove a beat
is wrong; it can mean the automated check cannot establish the pulse there.

The model and weights are from [CPJKU's official Beat This! implementation](https://github.com/CPJKU/beat_this),
under the [MIT licence](licenses/Beat-This-MIT.txt). Checkpoint SHA-256 hashes are
pinned in `tools/jamroom_beat_runtime.py`. Package versions are in
`tools/requirements-runtime.txt`. Audio stays local; only packages and model
weights are downloaded. The first setup downloads about 243 MB of model weights
plus the runtime packages; subsequent imports reuse them. Analysis outputs are
cached per recording and model version. There is no Numba/librosa dependency.

## Acceptance and review

“Automatic timing checks passed” is **not listening approval**. Candidates with
flagged passages are installed as muted click items. The rest of the import can
proceed. If models, audio or dependencies are unavailable, the song imports
without a click and the result says **NO CLICK**. There is no tempo-only fallback.

Song Library → Update charts & click tracks → **Review click** opens a portable
report with the drum waveform, click positions, flagged ranges and synchronized
music/click audio. Both audio signals share one file and one playback clock;
their levels can be adjusted separately. A flagged candidate can be explicitly
enabled after reviewing it. This checks the project and exact click version,
waits for stopped playback, and uses the existing guarded transaction/restore
path. It does not replace the chart or its timing edits. The report retains the
automatic findings after listening acceptance.

To replace the first-generation library clicks on the jam-room PC:

1. Run `JamRoom Update.bat`; allow the first model download to finish.
2. Save and restart REAPER, then refresh ReaSet and the importer.
3. In Song Library's update chooser, select **Click tracks only**, then
   **Update whole library**. No new Fadr split or song reimport is needed.
4. Review any muted candidates using their reports. Restore remains available.

The click generator is now `recording-click-2`, so old clicks are eligible for
replacement. Interrupted batches cannot reuse an old generator's candidate.
Existing audio files remain available for snapshots and restore.

## Stronger verification

`python tools/verify_click_quality.py "imports/Lenny Kravitz - Fly Away" ...`
uses the production generator without changing the cached job or live project.
It verifies the actual WAV's pulse times, not just the planned timestamp array.
It also compares against recording-specific, manually selected drum-waveform
reference windows, whose audio hashes are pinned in
`tools/click_reference_windows.json`.

The reference scorer uses one-to-one precision/recall at the selected pulse
level. Extra, missing and phase-shifted beats count as errors. This addresses
the distinction between strict beat timing and allowing alternative metric
levels described in [mir_eval's beat evaluation documentation](https://mir-eval.readthedocs.io/latest/api/beat.html).
Shifted, drifting, random and half/double-speed controls must fail; dense random
clicks cannot get a perfect result merely by landing near every reference beat.

These are **visual waveform annotations**, not listening-certified ground truth
or a general accuracy benchmark. The three checked excerpts contain 28 beats:

| Recording/excerpt | Old matched beats | New matched beats | New matched p95 error |
| --- | ---: | ---: | ---: |
| Fly Away, 60–66s | 3/8 | 8/8 | 12 ms |
| All the Small Things, 62.7–66s | 8/8 | 8/8 | 27 ms |
| Dreams, 60–66s | 12/12 | 12/12 | 12 ms |

Full-recording automatic checks produced these results on the cached recordings:

| Recording | Result |
| --- | --- |
| Fly Away | Checks passed |
| All the Small Things | Checks passed |
| Misery Business | Checks passed; model metrical disagreements reconciled |
| Dreams | Checks passed |
| Bring Me to Life | Review 12–36s; drum evidence does not confirm the pulse |
| I Believe in a Thing Called Love | Review 156–168s |
| Beggin | Review 0–12s and 156–180s |

The last three are not declared fixed or ready for rehearsal. They have generated
candidates and specific review passages, and remain muted until explicitly
accepted. The audio and reports are under each song's `clicks/` directory;
audit evidence is under `imports/.click-audit/` and is not committed as audio.

Tests also exercise gradual tempo drift, strong offbeat fills, a deliberately
bad middle passage, absent native dependencies, actual Python-to-Lua booleans,
muted click installation and restore. The real model runtime has been exercised
with all Numba/librosa imports deliberately blocked. Native and browser tests
are separate evidence for installation, routing metadata and UI behavior;
they must never be reported as proof that a click sounds correct.

Release verification on the testing workstation (12 September 2026):

- 124 automated tests passed, including waveform-clock accuracy at 300 seconds.
- 27 native REAPER transaction checks passed.
- The real importer UI updated all five eligible songs in a disposable library;
  chart documents stayed identical and actual item mute states matched findings.
  The review audio advanced, explicit enable unmuted the item, and restore muted
  it again. This automated enable was immediately undone, not recorded as a
  musician's listening approval. Evidence: `imports/.visual/append-5819p2vx/`.
- Fresh imports of the flagged Evanescence candidate installed muted. Native
  and ReaSet playback passed after both imports and an aborted import. Evidence:
  `imports/.visual/append-r18cjbcm/`. Both runs left the original project unchanged.

Those live checks found and fixed a Python-to-Lua boolean conversion that lost
the mute flag, plus Windows file-lock handling that could leave a finished batch
looking active. Neither issue was caught by the previous mocked request tests.
