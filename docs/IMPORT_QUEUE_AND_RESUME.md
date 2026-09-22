# Import queue and restart recovery

Status: implemented in importer **v3.6** (18 September 2026). The approved design
and investigation are preserved below; this section describes the released controls.

## Using the queue

Run `JamRoom Update.bat`, close the old importer process, then launch
`JamRoom Importer.bat` and reload its page. The current badge should show **v3.17**. The queue and review now use
[separate workspaces](WORKSPACE_LAYOUTS.md), with Stems/Lyrics/Chords tabs.

- **Your imports** lists unfinished songs. Use **Open** to see progress or
  review. **Add songs** remains available while other songs are processing.
- Stem routing, skipped stems, individual labels, lyric offset and chart/lyrics
  search fields autosave. Wait for **Saved**. Chosen lyrics and charts are saved
  too. Switching songs flushes pending edits first.
- Closing the browser leaves processing running. After stopping the importer or
  rebooting, reopen a saved review directly, or choose **Settings > Resume unfinished**.
  Startup never submits new paid work automatically. Existing caches appear in
  **Completed and cached songs**; they are not assumed to be unfinished imports.
- **Pause / continue queue** stops at stage boundaries. Already accepted remote
  tasks may continue. Queued songs also have **Move first** and **Pause** controls.
  **More > Remove from queue** hides the workspace but keeps its files; the Song library can reopen it.
  A workspace with an unresolved Fadr task must be checked first, because hiding
  it would leave a potentially running task blocking the remote processing budget.
- Apply each reviewed song explicitly. Its target project is shown in the task header;
  **Review tools > Use open REAPER project** deliberately changes that target before applying.
  Finish recording/playback first. Save the REAPER project after a successful Apply.
- An interrupted Apply uses **Check Apply** or **Check / retry Apply**. It keeps
  the same operation ID and freezes its review until reconciled, so a retry cannot
  overwrite audio or append the song twice. **Review / re-add** on a completed job
  starts a fresh operation with explicit project selection.
- If another browser changed the same review, the unsaved draft stays on screen
  with an error. **Reload saved review** explicitly discards that browser's unsaved
  changes; **Retry saving** is for transient connection failures.
- A different recording of the same song needs a distinct title, such as
  `Song (live)`. It gets separate cached files instead of overwriting the first version.

Two preparation workers share four transfers, one Fadr task and one local
analysis worker. This overlaps source downloads, stem work and review; it does
not claim to make Fadr itself faster. Two simultaneous Fadr tasks remain disabled
until account behavior is validated with deliberately queued songs.

The local `imports/import-queue.json` journal includes a previous checkpoint;
per-song `job.json` files also keep a previous copy. No API key is copied into the
queue. Interrupted stem downloads retain their partial files, refresh signed
URLs and reuse completed transfers. Upload and task intent are written before
submission, and returned asset/task IDs before polling. If acceptance is unknown,
the job stops with **needs checking** rather than repeating a possibly paid request.

Validation: automated restart/draft/conflict/worker-isolation and provider recovery
tests, a real Edge browser against the HTTP server, and native plus ReaSet playback
in a scratch copy of the populated REAPER library. The live test also repeats Apply
and requests the wrong target project, checks unchanged item/region/track counts,
and verifies that the original library remains unchanged. No paid Fadr submissions
were made for testing.

## Recommendation

Use a persistent import queue with a switchable song list and bounded background
processing. Queueing and switching songs solve different problems: the queue
controls resource use; selecting a song opens its own progress/review workspace.
Review must never occupy a processing slot or prevent adding another song.

Keep one importer page. Always show **Add song** and the current jobs, for example:

| Song | Status | Main action |
| --- | --- | --- |
| Fly Away | Ready to review | Review |
| My People | Separating stems | View progress |
| Another song | Downloading source | View progress |
| Next song | Queued | Move up / Pause |

Selecting a row switches the main panel without stopping another job. On a
tablet this can be a compact song chooser; avoid requiring multiple browser
tabs. Different browsers may view different songs independently. Show counts for
Processing, Ready to review and Needs attention, plus a collapsible completed list.

## Findings in the current implementation

- `tools/jamroom_importer_server.py` has one process-local `STATE`, one `CURRENT`
  job folder and one `BUSY` lock. `ACTIVE_STATES` includes `review`, so reviewing
  song A blocks starting B even after the preparation worker releases its lock.
- Restarting the server resets that active state. Completed stage flags and
  cached files survive in each song's `job.json`, but there is no durable queue
  or explicit unfinished-import workspace.
- Saved local songs can already be reopened through `orphan_jobs()` and
  `run_readd_local()`. This is partial recovery, not a complete resume workflow:
  it depends on cached audio and does not represent each interrupted stage.
- Stem routing, per-stem labels and lyric offset from the review form are handed
  to `run_apply()` when Apply is pressed. Those unsaved form choices need their
  own persistence; saving only the completed pipeline stages is insufficient.
- Stem downloads already run concurrently (default four workers), with partial
  download recovery. Simply multiplying that worker count per song could make
  bandwidth contention worse.
- Main, vocal and melodic Fadr splits are currently waited on sequentially.
  The main asset ID is saved after the main task finishes. Upload asset IDs and
  in-flight task IDs are not durably checkpointed before waiting. A shutdown in
  that window can cause a repeat upload/task instead of reconnecting.
- The importer replaces module-global logging callbacks. Multiple preparation
  threads cannot safely share the current job/state/log ownership model.
- Applying to REAPER still uses shared request/receipt mechanisms. Concurrent
  preparation must not become concurrent project mutation.

## Fadr capability and limits

Fadr documents independent asynchronous stem tasks, task-ID status queries and
queries for several IDs. A created task can therefore be tracked separately from
the browser request that started it. Source assets also expose their resulting
stems. See the [API endpoints](https://fadr.com/docs/api-endpoints) and
[API overview](https://fadr.com/docs/api).

These docs do not specify an account concurrency limit, a guaranteed throughput
gain for simultaneous jobs, or task-creation idempotency keys. Do not interpret
the multi-ID query endpoint as a promise of unlimited parallel processing.
Task creation is billable; polling an existing task is distinct from creating
another one. See [Fadr billing](https://fadr.com/docs/api-billing).

Proposed resource policy:

- Accept multiple queued songs immediately; start with two active preparation
  workspaces, so one can download while another waits for Fadr.
- Use a global Fadr task limit, initially one. Validate two outstanding tasks
  using songs already deliberately queued by the user before enabling a limit
  of two. If the account rejects concurrency, retain one; the queue and review
  workflow still work. Share this limit with vocal/melodic sub-splits.
- Use a global download budget of four transfers, with fair sharing between
  songs, rather than four new transfers for every song.
- Run one expensive local analysis/mixdown job at a time initially to avoid
  competing with REAPER for CPU and memory. Preview/review remains responsive.
- Serialize all REAPER mutations with the existing library-update operations.
  Awaiting review, an offline REAPER, or playback must not block preparation.
- Handle provider throttling with backoff and Retry-After where available;
  show waiting/retrying truthfully. Measure stage timings before promising speedups.

## Resume and autosave

Each job needs a durable identity independent of its display name, a source
fingerprint, queue position, intended project, stage states, timestamps, logs,
configuration snapshot, Fadr asset/task references and a review draft revision.
Store this locally beside the existing cached work, with atomic writes and a
previous valid checkpoint. No new service or database is needed.

Save review edits as they change: stem-to-slot assignment, individual labels,
skipped stems, lyric offset, chosen lyrics/chart and any editable chart draft.
Show Saving / Saved / Could not save. Flush on switching songs; do not depend
on browser-close events. A browser crash can lose edits not yet acknowledged,
so never call those edits saved. Separate processing fields from review fields
and serialize writes per job to prevent worker/browser updates overwriting each
other. Use job IDs and revision checks in every editing and Apply request.

| Interruption | Reopen behavior |
| --- | --- |
| Browser closes, importer stays running | Work continues. Reopen the song list with current server state and saved drafts. |
| Importer exits or PC shuts down | Restore all job cards. Reconcile remote tasks and local files; offer **Resume unfinished** and per-job Resume. Do not silently launch new paid tasks at startup. |
| Stopped at stem review | Open that exact saved review immediately; do not rerun Fadr or completed analysis. |
| Fadr still processing | Query the saved task ID and resume waiting; do not create a replacement task. |
| Download interrupted | Verify completed files, continue supported partial transfers, and refresh expired download URLs. Restart only the incomplete file if range resume is unsupported. |
| Local analysis interrupted | Reuse validated completed outputs and restart only the incomplete stage. |
| Apply acknowledgement lost | Reconcile the project receipt before offering retry; never blindly append the song again. |

Persist the upload/asset receipt immediately, and the task ID immediately after
submission, before polling. Also journal submission intent before each request.
If a network failure or crash leaves task acceptance uncertain, query the known
asset/task information to recover it. If acceptance cannot be proved either way,
show **Fadr submission needs checking** and retain the job. Do not automatically
resubmit a billable POST. Exact-once remote submission cannot be guaranteed by
a local journal alone without provider idempotency support.

On the first upgraded start, inspect existing `imports/*/job.json` records and
offer recoverable unfinished work in the same list. Validate prerequisites rather
than treating any existing stem file as a completed job. Keep previously imported
cached songs available separately; a song absent from the currently open REAPER
project is not necessarily an unfinished import.

## Everyday controls and safeguards

- **Add song** adds a job without replacing the selected review. Adding the same
  source/song twice returns its existing job. Different recordings with the same
  title require an explicit replace/new-version choice and separate working data.
- **Review** only opens a song's workspace. **Apply to REAPER** remains an explicit
  per-song action after review; no unattended auto-apply or automatic batch apply.
- **Pause queue** prevents new stages/submissions. Existing remote Fadr tasks
  may continue; do not imply pausing locally cancels them or refunds processing.
- **Retry** resumes the failed stage with its valid cached results. An error on
  one song does not stop the others. **Remove from queue** retains cached files;
  deleting media is a separate, explicit action.
- Applying requires the intended project to be open, stopped, and outside
  recording/review. Show its identity beside Apply. If the project changed,
  require deliberate target selection instead of importing into whichever tab
  happens to be active.
- Use a unique Apply operation ID and a project-side receipt/ownership marker.
  Check it before any append. Preserve the distinction between an acknowledged
  in-memory import and a saved RPP; after REAPER restarts, reconcile against the
  actual project rather than trusting an old `applied.txt` file alone.

## Implementation order and acceptance checks

1. Durable per-job state, source identity and remote-task checkpoints; migrate
   existing resumable work without issuing Fadr requests that create new tasks.
2. Song switcher, Add song, autosaved review drafts and restart recovery. Prove
   recovery before adding extra workers.
3. Bounded scheduling, job-specific logs, shared network/analysis budgets and
   isolated failures. Validate Fadr concurrency on authorized queued work.
4. Job/project-scoped Apply with duplicate prevention, integrated with existing
   recording and library-update locks.

Verify browser refresh and importer restart during download, each Fadr task,
stem download, analysis, review and Apply. Include a submission response lost
before checkpointing, expired URLs, corrupt checkpoints, throttling, duplicate
Add/Apply taps, two browsers editing different/same songs, a project switch,
REAPER recording, and one failed song while another succeeds. Tests must prove
that review drafts survive, task IDs are reused, files/logs do not cross songs,
and an uncertain Apply or Fadr submission cannot silently duplicate work.

The proposal was approved before implementation. Implementation lives in
`tools/jamroom_import_queue.py`, `tools/importer-queue.js`, and the existing
importer/REAPER bridge. Run `python -m unittest discover -p "test_*.py"` from
`tools`, plus `python tools/verify_import_playback.py "imports/Lenny Kravitz - Fly Away"
--queue-guards` from the repository root for the scratch-project integration check.

## Reopening and stopping (v3.15)

Run JamRoom Importer.bat to reopen a running importer from the same installation
and version. Closing a browser tab leaves imports and MP3 downloads running.
Use **Stop importer safely** to pause new work and stop after active work reaches
a saved checkpoint. Restart with the launcher; use **Resume unfinished** when ready.

A resumed review may retain an old project ID, or have none if prepared offline.
**Apply to REAPER** now offers to select the currently active REAPER project when
that target does not match. Check the active project tab before confirming. Drafts
and downloaded stems are retained. Save the REAPER project to preserve its identity.
An unresolved previous Apply must be checked in its original project to avoid
adding the same song twice; it cannot be redirected.

An older running version is not silently replaced. Run JamRoom Update.bat to
checkpoint and restart it through the existing update recovery process.
