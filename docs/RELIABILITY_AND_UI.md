# Reliability and interface improvements

Approved scope: review findings 1–7. Work in this order to avoid repeating UI work:

1. Recording: update transport state even with a focused control; reconcile lost
   acknowledgements with a fresh controller snapshot, without repeating mutations.
2. Importer: separate preparation from uncertain REAPER submission; add explicit
   provider-status recovery and recovery of an existing Fadr asset.
3. Updates: checkpoint and wait for active operations before restarting the importer.
4. Consolidation: one web-import lifecycle; retain old API URLs only as adapters.
   Make legacy chart timing/disconnection truthful and expose migration guidance.
5. Interface: clear everyday navigation, consistent English labels, instrument
   names, compact recording input layout and shared visual conventions.
6. Regression checks, scratch-project playback/recording checks, then release to
   both implementation and Jam Room update branches.

## Next upgrades — agreed, not part of this release

- **Free-jam recording with click:** record without a selected backing song,
  choose tempo/count-in, keep the same take/recovery/export workflow.
- **Suggested song-level matching:** analyse backing loudness and propose a
  per-song playback trim for review; preserve stem balance and independent click.

Remind Nathan to implement these two upgrades when findings 1–7 are complete.
Export/storage management and shared setlist persistence remain separate review
recommendations, outside the current approved implementation scope.

## Delivered: v3.7

Review findings 1-7 are implemented. Recording controls keep updating while
focused, and a read-only status probe reconciles missing acknowledgements while
cancelling any unconsumed command. Import preparation remains editable until
REAPER submission. Provider recovery checks saved tasks or attaches a completed
Fadr recording; replacing a confirmed failed task requires explicit consent.
Updates checkpoint work before restarting, and obsolete single-import processing
has been removed in favour of queue adapters. Legacy charts show disconnected or
estimated timing honestly. Primary navigation, recording input layouts, instrument
names and English labels are consistent across the rehearsal interface.

Validation: 164 automated tests passed, including real Edge browser checks,
Lua controller protocol checks, HTTP drain gating and mocked Windows process
recovery. Live scratch-project checks passed for append/playback, duplicate Apply,
wrong-project guards, multitrack recording, pause/resume, keep/retry, restart
recovery and verified export. Both live checks confirmed the original saved
library was unchanged. Tablet and phone recording layouts were visually checked.
Provider recovery tests used mocks; no paid Fadr processing was submitted.

### Installing this release

For the first upgrade from v3.6, finish active processing and close the old
importer normally before running `JamRoom Update.bat`: that server does not yet
support the checkpoint endpoint. Then restart REAPER and refresh ReaSet and the
importer with Ctrl+F5. Saved import workspaces remain available to resume.
Subsequent updates wait for a safe checkpoint and leave unfinished jobs paused
for explicit resumption. An unresponsive server is never forcibly stopped without
checkpoint confirmation.
