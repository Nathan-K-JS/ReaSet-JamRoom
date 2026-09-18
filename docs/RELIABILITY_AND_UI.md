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
