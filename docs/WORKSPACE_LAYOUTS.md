# Import and recording workspaces — v3.17

> **Active JamRoom PC - mandatory workflow (27 September 2026):** this
> installation is connected to the X32 and live REAPER library. Preserve all
> live projects, media, recordings, configuration and mixer state. Development
> tests must use a separate isolated dummy setup, never the live REAPER instance.
> Follow [the live-system workflow](LIVE_JAMROOM_WORKFLOW.md) before using any commands below.
> Earlier workstation results are historical; operator setup/update instructions
> are not authorization to change the live rig during development.

The approved [layout plan](WORKSPACE_LAYOUT_PLAN.md) is implemented. The importer
and recording screens now reserve space for their actions and scroll the working
content. The original SVG boards illustrate the design; they are not application
screenshots.

## Importing and updating

- Desktop shows the import queue beside the selected task. Phone switches between
  queue and task. **Add songs** stays accessible; each queue entry has **Open**.
  Search and filters help with bulk work. Removal stays under **More**.
- Review follows **Stems → Choose chart → Review chart**. Fresh chart selection
  searches automatically and loads the top matching Ultimate Guitar result;
  saved choices and drafts are retained. Stem previews can stay open together.
  The footer advances through the steps, ending with **Add to REAPER** after
  **Done reviewing**. Save status and **Keep for later** stay at the bottom.
  The intended project appears in the task header. Target checks still run before
  Apply; the importer never silently selects a different project.
- Reopening restores the selected job, tab and saved draft. Background completion
  does not switch away from the task being edited. Review tools contain explicit
  reload, retry-save and target-selection actions. A conflicting editor cannot
  silently replace the focused draft.
- **Song library > Update songs** has its own searchable chooser, selected count
  and reserved Update action. Selection options collapse on small screens.
  Replacement and restore controls live under **Update options and restore**.
  Returning to a loaded chooser preserves its selection without another scan;
  **Refresh** explicitly rescans. Activity remains the central progress view.
- **Settings** holds connection details and importer service controls. Setup
  failures appear above the workspace with a direct route to those settings.

## Recording and exporting

- **Prepare** puts inputs and meters first, with Song/Free jam and click/count-in
  settings. **Capture** shows the timer, selected inputs, Pause/Resume and Stop.
- **Review** shows the selected arrangement and saved mix. Listen, Add part, New
  take and Export recording remain reachable while the parts scroll. Backing
  controls list only groups present in the song. Rename/reset are in each part's
  More menu. Takes, Sessions and Settings have separate views.
- **Add part** shows input selection beside accompaniment on desktop, or as two
  tabs on phone. Click/count-in sit above the panes. Each desktop pane scrolls
  independently, so a long mix cannot bury input selection or session options.
- **New take** and **Redo** prepare before recording. Cancel restores review and
  input choices. Preparation creates no take and discards nothing; a redo discards
  the previous pass only after capture starts. Backing choices carry into capture.
- **Export recording > Create MP3** opens the selected export in the existing
  importer service. Its progress, download and QR links stay together, with a
  **Back to recording** link. **Exports** opens the complete export list. The
  service owns export progress; ReaSet does not maintain another job registry or
  display a separate working-export count.
- **Sessions > Export multitrack project** remains a separate
  operation with verified-copy cleanup. An MP3 leaves the multitracks saved.

These are controller/layout changes. Journals, project receipts, provider queue
limits, count-in audio and isolated MP3 rendering retain their existing ownership.

## Verification and rollout

All **224 automated tests passed** using `python -m unittest discover -s tools
-p 'test_*.py'`. Browser checks cover desktop, tablet, 320/390 px phones, 844x390 landscape and
200% zoom; large fixtures include 30 imports, 80 library songs and 24 recorded
parts. They check reachable actions and final rows, draft/tab restore, preparation
acknowledgement, autosave/conflicting editors, duplicate export prevention and
the export return path. Rendered screens are also inspected, including expanded
stem previews, preparation, capture and export. MP3/QR tests exercise Chromium
Android and WebKit iPhone emulation.

Native REAPER scratch-project checks cover prepare/cancel, capture, count-in,
same-input overdubs, part levels, restart recovery, MP3 request snapshots and
multitrack export. The populated-library import check covers repeated Apply,
wrong-target guards and native/ReaSet playback after appending songs. Both checks
verify the original project is unchanged.

Run **JamRoom Update.bat**, save and restart REAPER, then refresh ReaSet and the
importer on each device. Confirm the importer badge is **v3.17**. Existing saved
imports and recordings continue through their current journals.

This validation was performed on the former development workstation, not the
physical X32 room. Development now runs on the active JamRoom PC with separate
dummy tests. Actual room audio, Wi-Fi and mobile keyboard acceptance remain
separate tasks; the historical results do not establish those checks.
