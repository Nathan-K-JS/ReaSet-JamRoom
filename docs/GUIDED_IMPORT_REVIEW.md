# Guided import review - v3.22

Approved and implemented on 3 October 2026. Source development and tests use a
separate checkout; the [live workflow](LIVE_JAMROOM_WORKFLOW.md) still applies.
This document describes the new build, not deployment to the active rig.

## Musician workflow

1. **Stems:** preview stems and choose their playback groups. The primary action
   is **Continue to chart**.
2. **Choose chart:** entering this step searches Ultimate Guitar automatically
   and selects the first matching result for a fresh import. Existing matching
   rules still rank artist/title suitability before votes and rating. The
   selected source and other versions remain visible. Search again, enter a
   different query or paste a chart link to change it.
3. **Review chart:** **Continue to review** opens **Preview**, with **Edit** beside
   it. **Done reviewing** saves the draft and returns to the final **Add to
   REAPER** action. Closing without confirming leaves **Review chart** as the
   primary action. No playback or timing checklist is required.

There is no separate Timing tab in the shared editor. **Timing adjustments**
beside the player expands exact section start, suggestions, whole-chart offset,
zoom and timing confirmation. Timeline markers, playback and Starts here remain
available from Preview and Edit. This also applies to the editor embedded in
ReaSet; old saved Timing views reopen in a supported view.

## Preservation and asynchronous work

- Returning to an import retains stem choices, source, chart edits and completed
  review. Existing selected sources or saved chart drafts are never automatically
  replaced. Old review tabs map to chart selection.
- Automatic search is attempted once per job per page session when chart
  selection is needed. Failed/no-result searches stay at that step with retry,
  query and paste-link controls. They never silently advance to Add.
- Search responses carry a job/selection generation and request sequence. A late
  response cannot choose a source for another song or overwrite a newer search.
- A fresh first chart uses the existing candidate/accept transaction. Replacing
  a selected chart still opens a cancellable candidate preview and keeps the
  previous chart. Revision checks reject stale acceptance. Replacement clears
  the saved review confirmation on the server as well as in the browser.
- The final UI action requires a chart and successful review save. Existing
  target-project checks, unresolved Apply recovery, operation receipts, Fadr
  processing and native import/save behavior retain their existing ownership.

The importer now serves the shared chart-display core with its pagination
asset. Previously that HTTP route returned only the legacy helper fragment,
even though the editor's Preview needs `ChartDisplay`. Browser regressions now
use the actual asset handler so a standalone generated test asset cannot hide
this mismatch.

## Isolated verification

57 tests passed: eight guided-flow browser tests and 49 existing workspace,
chart-authoring and import-queue tests. Desktop, tablet, phone, landscape and
WebKit keyboard-height layouts were exercised. This is isolated acceptance;
the live runtime was not updated or restarted.

`test_import_chart_flow.py` exercises the real browser UI with every HTTP
request intercepted. It covers the three-step flow, automatic first choice,
retained stem edits, the review gate, empty/failed searches, stale results after
switching jobs, replacement cancellation/acceptance, saved drafts, and optional
timing controls at desktop/tablet/phone/landscape sizes. It reads JavaScript
through the production asset handler. Screenshots are under the development
checkout's `imports/.visual/import-chart-flow/`.

The existing importer workspace, chart authoring and import queue suites also
cover draft conflicts/recovery, source replacement, native authoring messages,
pitch preservation and WebKit phone editing with a short keyboard viewport.
Browser fixtures and the queue test's temporary local service are separate from
the live importer. No Ultimate Guitar request, paid processing, live library
operation or mixer change is part of these tests.

Run with the isolated development Python environment (Playwright/Edge, and
WebKit installed into a separate development browser directory):

```powershell
python -m unittest discover -s tools -p test_import_chart_flow.py -v
# From tools/:
python -m unittest test_workspace_layouts.ImporterWorkspaceTests test_chart_authoring test_import_queue -v
```

The older `verify_import_playback.py` is not suitable here: its hard-coded port
8080 and live-project snapshot behavior fail the mandatory isolation rules.
It was inspected, not executed. Native import Lua and transport were not changed
in this UI work. Physical-phone/network-provider acceptance and live deployment
remain separate from the isolated browser and backend verification.
