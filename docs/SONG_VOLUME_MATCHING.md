# Automatic song-volume matching (v3.9)

The approved workflow measures final backing stems at import, and provides the
same operation for cached songs through the library updater. It changes one
per-song playback trim, preserving instrument balance and leaving click separate.

## Using it

- New imports: confirm stem selection as usual, then Apply. The final slot audio
  is measured before submission to REAPER. The completion message reports the
  matched starting percentage. No extra provider requests or paid splits.
- Existing songs: Importer > Manage > Update existing songs > **Volume matching
  only (keep charts and clicks)** > **Update whole library**. This mode also works
  for songs whose chart version is protected. Stop playback and choose Done in
  Recording first. Save the REAPER project after the batch completes.
- The default **Charts, click tracks and volume matching** mode also includes
  matching when updating selected songs or the whole library. Existing manual
  chart/timing edits are preserved unless replacement is explicitly selected.
- Manual playback sliders remain authoritative. The updater saves a suggestion
  but keeps your setting. Tick **Replace my manual playback levels with matched
  suggestions** only when you want those settings replaced.
- ReaSet > Backing shows the confirmed level and whether it is automatic or yours.
  **Use matched level** applies the stored suggestion and returns that song to
  automatic matching. Moving the slider marks it as manual again.

## Measurement and limits

The local ffmpeg EBU R128 scanner measures integrated loudness of an unnormalised
stereo sum of final selected slots, excluding CLICK and SKIP. It also measures
individual slot true peaks so phase cancellation cannot hide a loud return.
The implementation uses ffmpeg's documented [amix and ebur128 filters](https://ffmpeg.org/ffmpeg-filters.html#ebur128).

The common reference is **-23 LUFS**, with **-3 dBTP** peak headroom and a maximum
trim of unity (100%). Matching only attenuates; it does not compress, limit, boost,
or rewrite audio. Quiet or very dynamic recordings may remain below the target;
ReaSet labels those suggestions as limited for headroom. Silent/unmeasurable
sources retain their existing level and report why no suggestion is available.
The common target can make the library quieter overall than the former 65%
default; adjust the overall listening level at the mixer as needed.

This is a consistent starting point based on the complete cached backing mix.
Different IEM mixes, muted stems, EQ, track FX and later manual instrument balance
changes affect perceived volume. Matching does not chase these changes during
playback. Edited/trimmed/stretched or mismatched backing media is rejected by the
library update instead of applying a stale full-source measurement.

Older saved slider values different from the old 65% default are treated as
manual. Old releases did not record whether exactly 65% was chosen manually;
that indistinguishable legacy default receives automatic matching. New manual
choices, including 65% and zero, are explicitly marked and preserved.

## Persistence and recovery

`jamroom_loudness.py` caches a report in job.json using the generator, target,
final slot paths, file sizes and nanosecond modification times. New selections or
changed sources invalidate the report. Analysis runs before the import's durable
REAPER-submission boundary, so a preparation failure leaves review editable.

`ReaSet_Playback.lua` stores suggestions and automatic/manual ownership by stable
song GUID. Gain is applied from tracked item base levels, never compounded.
Library transactions snapshot the prior gain, ownership, suggestion and item
level metadata alongside existing chart/click snapshots. Failed transactions
roll back; repeated operation IDs do not reapply. Restore refuses to overwrite
later manual changes. Missing media never starts a download or Fadr split.

## Validation and installation

175 automated tests cover real ffmpeg measurement, cache invalidation, peak
headroom, silence/missing media, manual preservation, full/volume-only batches,
protected charts, and the confirmed browser action. Live scratch REAPER checks
cover import/playback, duplicate Apply, wrong-project rejection, level-only
transactions, stem balance, click/chart isolation, manual override, restore and
invalid requests. Recording/free-jam regressions are also checked.

An initial append test passed playback/content checks but detected a changed
original-project state counter. A repeat with extended diagnostics passed both
content and counter checks; no content differences were observed in either run.

Run `JamRoom Update.bat`, restart REAPER and refresh ReaSet/importer with Ctrl+F5.
Then run the volume-only whole-library update on the jam-room PC. Test-workstation
measurements do not change that PC's library automatically.

## v3.11.2: updates after backing timing changes

Library updates no longer reject matching cached stems because an item has a
position, length, start-offset or playback-rate difference. Matching uses the
cached-source loudness suggestion and reports an estimate when timing differs;
this is not a new measurement of edited REAPER playback. Tempo, pitch and item
timing remain untouched. Source-file and take-count checks remain in place, as
do manual-volume preservation and snapshot/restore. Retry failed songs from the
library update chooser after updating and restarting the importer.
