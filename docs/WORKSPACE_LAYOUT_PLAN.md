# Import and recording workspace redesign

Status: proposed, 22 September 2026. Application behaviour is unchanged.

The v3.16 features work, but their controls accumulate vertically. The next
iteration should reorganise complete tasks, including their empty, busy,
resumed and error states. Adding more collapsible cards to the existing pages
would leave the underlying navigation problem in place.

## What was actually inspected

Rendered the current HTML and JavaScript in Edge with local, simulated API and
REAPER state. This was a layout/workflow review, not another hardware test.
Fixtures included twelve import jobs in mixed states, eight review stems, an
80-song library, an eight-part recording, a pending-recordings reminder, solo
overdub preparation, capture and ordinary recording setup. Screens were checked
at 1440x900, 768x1024, 390x844 and, for recording, 844x390.

Concrete observations:

| Current layout | What it means in use |
| --- | --- |
| Importer is capped at 900 px; recording content at 760 px, even on a wide desktop. | Space is left unused while task controls stack vertically. |
| In the phone import fixture, review begins at y=2469 and Add to REAPER at y=5636. | A restored review can be loaded correctly while looking as though it has disappeared. Explicit Open scrolls to review; restoring the selected job does not give it a dedicated view. |
| With 80 library songs, Update selected is at y=8021 on a phone. The ordinary library list is also below the update chooser. | Selecting songs and starting an update requires travelling through large lists twice. |
| Eight-part phone review puts Add another part at y=1763 and Export recording at y=2135. | The persistent Listen/Stop buttons help playback, but do not help the decisions made after listening. |
| Overdub Record part is at y=3088 in that phone fixture. The persistent transport still says Listen. | The main visible action disagrees with the task the musician is preparing. Auto-scrolling to inputs separates them from accompaniment controls. |
| Recording setup opens with archive/recovery/device information above instrument selection. | In the phone fixture, no input selector fits in the first screen, despite the persistent Record button. |
| Review repeats global recorded/backing toggles, part controls, up to ten backing buttons, next-take buttons, export, saved recordings and hardware setup. | A growing take changes the location of every subsequent task. |
| Healthy connection checks, Retry saving, Reload saved review and Use open project are permanently offered alongside normal work. | Exceptional maintenance actions have the same prominence as routine decisions. |

These pixel positions describe the named fixtures, not every real session.
All three design boards linked below are static proposals, not working UI.

## Shared layout rules

1. A compact persistent header answers: which song/session, which take/job, what
   is happening, and are changes saved? Names may wrap; status never silently
   replaces the name. Errors affecting the current task have an inline remedy.
2. One primary work area occupies the remaining height. Desktop can use two
   explicitly bounded panes. Phone uses a single content pane with task tabs;
   do not stack the desktop sidebar above its contents.
3. A reserved bottom action area stays reachable. It changes with confirmed
   task/transport state. It occupies layout space and cannot cover the last row.
4. Routine controls remain visible; technical details, source routing, rare
   restore actions and logs move to named secondary views. Standalone recording
   discard stays easy to find, with its exact scope stated.
5. Use the existing dark palette, restrained green for the main next action,
   red for actual recording/Stop and restrained destructive styling. Keep text
   labels and at least 44 px touch targets. Reduce repeated prose, not legibility.
6. Background progress updates neither scroll the page nor switch tasks. Only a
   deliberate navigation action or confirmed capture/stop changes the main view.
7. Layout state is distinct from REAPER state. Never represent a locally selected
   input, a saving draft or a pending command as confirmed success.

## Importer: queue plus one selected task

See [desktop import review](ui-layout/importer.svg).

Top-level destinations: **Imports**, **Song library**, **Exported recordings**.
Settings contains connection details and Stop importer safely; the latter must
still explain that stopping the service also stops phone downloads.

On desktop, Imports has a 260-300 px queue pane and a flexible selected-job pane.
Queue search and filters: **Needs attention**, **Ready to review**, **In progress**,
and **Completed**. Show counts without continually reordering a list someone is
using. Each row has a name, concise state and one explicit Open/Resume action;
Move first, pause and remove live under that row's More menu. **Add songs** stays
visible. A new song uses the main pane and returning restores the review draft.

On phone, **Imports (11)** opens a dedicated queue view; selecting a song opens
its detail view. Back returns to the same queue position. No horizontal row of
eleven song tabs. The selected song's identity is always visible.

The selected job has **Stems / Lyrics / Chords** task tabs with concise statuses.
They are freely navigable; do not force a wizard or claim that merely opening a
tab constitutes review. Warn about missing optional lyrics/charts and actual
blocking errors separately; do not require every stem to be played before Apply.

- Stems: compact rows containing name, destination and preview. Expand only the
  selected stem's waveform/player and display-name field. Preserve original stem
  identity alongside its editable display name. One preview plays at a time.
- Lyrics: current source/timing, preview and correction tools for this song.
- Chords: selected chart and search/change tools, occupying this view rather than
  extending below every stem. Keep manual chart choice explicit.
- Reserved footer: autosave state, intended REAPER target, **Add to REAPER**.
  On small screens target/name belongs in the header to leave button space.
  Unmatched targets show their remedy here; never silently retarget imports.
- After confirmed Apply: a receipt and **Review next ready song**. Do not
  automatically switch songs while the user is reading the result.

Reopening on the same browser restores the selected unfinished song, task tab
and saved fields directly into the main pane. With no valid saved selection,
open a concise queue overview showing **Continue review**, resumed work and
items needing a decision. The server journal owns job state; localStorage only
remembers navigation. An unknown paid split remains an explicit recovery task.

Keep one compact activity summary while editing. Full Activity becomes a named
view with a return path, not another column of logs below the form. Show a badge
for background failures without replacing the current song's status. Healthy
setup collapses to connection status; relevant failures expand in place.

## Library maintenance: its own work area

Use **Browse / Update songs** inside Song library. Update mode/scope, search,
eligible/problem filters and selected count are visible above the song list.
The footer says **Update 24 selected songs** and shows the selected operation.
Do not render the ordinary library list a second time below this chooser.

Replacement options sit in a clearly named **Update options** section, with
active overrides summarised next to Start. Restore is an explicit secondary
task with affected-song scope, not an equally prominent normal update button.
During execution, show current song, stage, counts and **Pause after this song**.
After execution, show failures first with Retry/inspect actions. Returning from
Activity restores filters, selection and scroll without rescanning the library.

## Recording: prepare, capture, review

See [desktop solo overdub](ui-layout/recording.svg) and
[phone setup, review and export](ui-layout/phones.svg).

The Record destination becomes a full workspace inside ReaSet's existing app
shell. Header: session/song, current take, save/device state, **Sessions** and
settings. An ordinary backlog becomes **Saved sessions (3)**, not a large warning
above the instruments. Actual interrupted/unresolved audio remains an explicit
attention message, with recovery access; it must not be hidden as routine history.

### Prepare

Choose Song or Free jam, then input selection and meters form the main content.
Group Voices, Instruments and Additional inputs. Keep selected additional inputs
visible even when their group is collapsed. Tempo/meter/click/count-in sit in a
compact settings area; show a short selected-input summary beside the action.

Desktop: inputs and session options side by side. Phone: compact session options
followed immediately by inputs; footer **Record** remains visible with selected
count. Reconnect appears for unavailable input/device state or under device
details, rather than consuming a healthy setup screen.

### Capture

Show a prominent recording/count-in/paused state, elapsed time, session identity
and meters for selected inputs. Bottom actions are **Pause/Resume** and **Stop**.
Do not show history, exports, unrelated input mapping or a second set of transport
buttons in the content. Keep status visible if a tablet reconnects mid-recording.
Native Record already runs during count-in; the display must reflect that design.

### Review and balance

After confirmed Stop, show the selected take and its mix immediately. Compact
rows: part name, Hear, horizontal level slider, value. Rename/reset go in the row's
More menu; playback mute and volume remain directly accessible. For song sessions,
use **Recorded parts / Backing** tabs with counts and mute summaries; only actual
available backing groups are shown. Absent groups require native state publication
instead of the current hardcoded list of ten. This is part of the design work.

**Listen**, **Add part**, **New take**, **Export recording** stay in a reserved
action area. Desktop uses one row; portrait phone uses a labelled 2x2 grid.
Listen becomes Stop listening while auditioning. State-changing recording/export
actions explain when listening must stop; they do not silently interrupt audio.
The normal song tempo/key strip and song transport are replaced in this workspace
by these recording actions. Existing emergency Stop remains reachable during
capture, audition, stalled commands and loss of connection.

The review header identifies the latest pass: e.g. **Added Harmony + Guitar 2**.
Place **Redo latest** and **Discard latest** there, with scope text. For a first
take use **Redo take / Discard take**. Discarding an addition affects the newly
captured pass, not the inherited parts; there is no invented per-item delete
operation. Retry/discard remains recoverable using existing saved-session rules.

Take switching is a visible header control. Desktop may show a take list pane;
phone opens a dedicated Takes view and returns to the selected mix. Entries show
name, duration, favourite and **Built on Take 2 / 8 parts**, as appropriate. Raw
capture passes and complete layered arrangements must not look like duplicate
unrelated recordings. Discarded takes are filtered from the ordinary list but
Restore remains accessible. Renaming/favourites do not each need a large button.

### Add part and new take

**Add part** opens a preparation view, not a section appended below the mix.
Desktop shows **Recording inputs** beside **What you will hear** (the existing
part mix and backing choice). Phone has **Inputs / Accompaniment** tabs, with a
persistent summary of both and the **Record part** action. Click, count-in and
free-jam Stop at end are visible settings. Auditioning accompaniment preserves
chosen inputs. Meters belong to live inputs; sliders belong to recorded parts.

Example: Recording Vox 1; hearing Lead vocal, Bass, Keys; count-in 2 bars. The
older Vox 1 performance remains disarmed and audible. After Stop, the combined
mix opens with the new harmony identified. The same view supports several new
inputs in one pass.

**New take** also opens Prepare, remembering the previous input selection but
allowing changes before Record. It retains the previous take as an independent
alternative and makes the absence of earlier recorded accompaniment explicit.
This requires a small controller change: today's `keep` and `retry` immediately
start capture. Add a preparation/cancel transition for New take and Redo without
creating a new journal take or discarding the old pass until Record is pressed.
Cancel returns to the same review, input selection and mix. A redo keeps its
parent arrangement and selected count-in/click/end settings.
For both paths, command acknowledgement—not a browser guess—opens Capture.

### Quick export and leaving

**Export recording** opens a focused view naming the selected take/arrangement,
audible parts and backing choice, with **Create MP3**. If the mix is wrong, Back
to mix preserves all settings. The resulting view keeps queued/rendering/ready/
failed state in the same place and reveals **Play / Download MP3 / Show QR** when
ready. Include room-Wi-Fi instructions and a copy-link fallback by the QR.

The importer service continues to own jobs and phone downloads. Existing job
links remain stable. A user can return to recording while an export runs and
reopen it through **Exports (1 working)**. Do not duplicate the registry in ReaSet
or imply remote internet access. A cross-app handoff must identify the selected
recording and provide a clear Back to recording path.

**Export multitrack project** is a separate labelled session action, reachable
from the session header's menu and Sessions. It retains its verified-copy and
setlist-cleanup behaviour. Making an MP3 never implies the multitrack session has
been removed. A simple saved-on-room-PC status allows walking away safely.

## Workflow walkthroughs

| Situation | Intended sequence and visible essentials |
| --- | --- |
| Bulk import while Fadr works | Add songs; queue shows progress; open a ready review beside it; map stems; switch to charts; Apply; Review next. Each action stays in its own area as the queue grows. |
| Return tomorrow mid-review | Open importer; selected song and task reopen with saved fields. Needs-attention and ready counts remain visible. Explicit Resume handles interrupted work without repeating paid submissions. |
| Library update of 80 songs | Open Update songs; filter/select; see selected count and Update action without travelling to the bottom; follow progress; inspect only failures. |
| Four-mic group | Free jam; select four voices; click and count-in; Record; Stop; Listen and adjust four levels; Export. Hardware setup stays out of the normal path. |
| Full band, no click | Free jam; instrument inputs and meters; click off; Record/Stop always visible. After listening choose New take; change players/inputs before recording again. |
| Solo layers on the same mic | Review lead; Add part; choose Vox 1; balance lead accompaniment; Record part; combined review; repeat. No scrolling between arm selection and accompaniment. |
| Bad new harmony | Review identifies the latest addition; Discard latest returns to the prior combination, or Redo latest prepares the same pass again. Existing parts remain intact. |
| Compare earlier versions | Take switcher opens versions with lineage and part counts; choose explicitly, then Listen. Favourite/name controls remain available without crowding the mix. |
| Finish while friends leave | Export recording stays visible; confirm mix/backing; Create MP3; ready page exposes QR/download and same-Wi-Fi instructions. Return to playing while rendering. |
| Several tablets in one room | They control one shared REAPER transport. Every action names the confirmed session/take; stale revisions re-sync instead of applying to another take. No promise of independent simultaneous audition/mixing. |
| Reconnect, restart or unknown status | Show last-confirmed state and explicit uncertainty; keep native Stop guidance/recovery available. Retry reads and receipt checks, never blindly replay Record, Apply or paid splits. |

## Implementation order

1. Define view state and shared layout primitives: header, content bounds, action
   area, responsive panes, focus/scroll restoration and acknowledgement handling.
   Define the small controller changes for preparing independent takes and redo,
   returning to review on cancel, and publishing available backing groups.
2. Refactor recording Prepare/Capture/Review/Add part around the existing commands
   and journal. Replace its transport once, including short-screen behaviour.
3. Integrate Takes/Sessions and the MP3 handoff/progress/QR return path; preserve
   archive/recovery actions and existing phone-share pages.
4. Refactor importer queue/selected-job navigation and tabbed review while keeping
   autosave, target checks, stable job IDs and receipts intact.
5. Move library updates into the same workspace shell; consolidate activity and
   exceptional setup/recovery controls. Remove superseded containers and handlers.
6. Run the workflow matrix visually and through interaction tests, then native
   controller/export/import regression checks where those paths changed. Deliver
   through both existing update branches after validation.

This order builds reusable layout behaviour before fitting individual features
into it. It does not need a framework, new database, authentication system,
waveform editor, cloud service or new audio engine.

## Acceptance criteria

- Test 320x568, 390x844, 768x1024, 1024x768, 1440x900, landscape 844x390 and browser
  zoom at 200%. Short/zoomed windows use a compact header and one-row action area
  when needed, while content and secondary navigation remain reachable.
- In normal portrait/desktop layouts, Apply/Record/Stop/Listen/Add part/New take/
  Export are visible as appropriate without scrolling through data lists. For
  the smallest/zoomed layouts, transport stays visible and other task actions
  are within one explicit navigation action, never buried below the list.
- Content can scroll to its final row above the action area. No whole-page plus
  nested-card scrolling on phone. Two independently labelled panes are allowed
  on desktop. Use dynamic viewport and safe-area sizing, not hardcoded offsets.
- Actual screenshots are inspected after every major state transition, including
  opened menus, long names, errors, keyboard focus and expanded stem previews.
- Typing, dragging, media preview, selection, open controls and scroll position
  survive background polling. Save failures keep the draft and a visible remedy.
- The on-screen keyboard can expose the focused field and its confirmation action;
  physical iOS/Android keyboard behaviour remains a room/device acceptance check.
- Review matrices include 1, 8 and 24 parts; 1 and 30 imports; an 80-song update;
  no history; many saved takes; interrupted work; service restart; two tabs with
  stale revisions; export still running; disconnected REAPER.
- Browser workflow tests assert key controls are in the usable viewport, not
  merely present in the DOM or free of horizontal overflow. Native regressions
  verify prepared/cancelled takes do not start Record and existing capture,
  count-in, mix/export, cleanup and import guards remain intact.

## Source locations

- `ReaSet.html`: recording CSS around line 3396, transport adaptation around 8997,
  and `recRender()` around 9115. Refactor view rendering rather than append another
  section to this renderer.
- `tools/importer.html`: stacked workspace markup and `showReview()`.
- `tools/importer-queue.js`: queue insertion before source selection, selected-job
  persistence, autosave, target confirmation and row actions.
- `tools/importer-activity.js`: reusable confirmed progress and connection state.
- `Requirements/ReaSet_RecordingCore.lua`: review/overdub/keep/record command
  transitions and state publication; preserve version-2 journal ownership.
