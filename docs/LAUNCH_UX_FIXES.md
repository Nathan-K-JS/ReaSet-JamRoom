# Launch UX fixes

Approved scope: review findings 1–10 plus moving SYNC out of the transport.

Implementation order:

1. Shared layout: move the More views popup outside the scrolling top bar; put
   performance controls below menus/dialogs in the stacking order; reserve their
   space in Live/Stage views; protect chart space on short screens.
2. Song navigation: readable mobile rows, silent title selection and explicit
   Play; preserve queue mode and existing MIDI cues. Put mobile secondary actions
   in the song menu. Add Add song and clarify setlist/library labels.
3. Recording: context-aware primary transport; cancelling without captured audio
   returns to setup and does not create export chores. Never drop unresolved
   media or other takes in the session.
4. Appearance and connection: show old text settings only for applicable views;
   replace duplicated Sync controls with confirmed connection status/Reconnect.
   Constrain the importer's chart-key selector.
5. Browser interaction/geometry regressions, controller and live scratch-project
   recording checks, visual review, and release to both update branches.

The listening-copy feature is planning only in this change. See
[LISTENING_RECORDINGS.md](LISTENING_RECORDINGS.md) for the proposed workflow,
rendering architecture and implementation gates.

## Resulting behaviour

- More opens a clickable view/connection popup on desktop and small screens.
  Live and Stage leave room for performance controls; switching views restores
  the correct transport and closes the previous screen.
- The tempo/key bar no longer draws across editors, menus or dialogs. Short
  screens use compact chart controls, omit the next-page preview and keep a
  readable music area; extremely constrained layouts can scroll.
- Phone song rows prioritise the title. Chain, loop and skip remain available
  in the song menu. Tapping a title selects without audio or a MIDI play pulse;
  its triangle button plays. Queue mode still queues a title tapped during playback.
- The recording footer offers Record/Pause/Resume/Listen as appropriate, using
  confirmed controller state. Free jam hides the unrelated song tempo/key drawer.
  Reconnect never repeats an unconfirmed recording/export action.
- Empty cancelled captures return to setup. Startup also retires older empty
  entries after checking their capture folders. No files are deleted; unresolved
  media, other takes and any unknown files remain discoverable for recovery.
- Legacy font/size/colour controls are hidden when section charts are in use;
  they remain available for legacy text displays. Stage has its own text controls.
- Add song is on the Songs screen. Setlist import/export and library updates
  (including playback levels) have explicit labels. The chart-key picker fits
  phone width.
- SYNC is removed from the transport. More and the sidebar show connection
  status with Reconnect; connection status expires without fresh REAPER replies.

## Updating

Run `JamRoom Update.bat`, restart REAPER and the importer, then refresh browser
pages with Ctrl+F5. This release does not require regenerating the song library.
The separate listening-copy proposal is not an available button yet.

## Validation

181 automated tests pass, including 46 Edge browser tests. New coverage checks
real clicks in the More menu, leaving full-screen views, modal stacking, readable
landscape charts, silent mouse/keyboard song selection, preserved queue behaviour,
recording transport, expiring connection state and hidden inapplicable settings.
Controller tests protect prior takes, unresolved audio and unknown files when
dismissing an empty capture.

The native scratch-project recording check passes cancellation and durable empty
cleanup, multitrack capture, pause/resume, keep/retry, restart recovery and verified
export, including free jams. The native append-import/playback check loads this
checkout's actual UI, verifies silent title selection and starts playback from
the selected song. Both confirm the original project is unchanged. The test PC
has no physical recording inputs; capture uses REAPER track-output recording,
so this does not constitute an X32 hardware retest.

Desktop, portrait tablet, 390px/320px phones and 844×390 landscape views were
visually inspected. The importer chart-source form fits 390px without horizontal
scrolling. Review screenshots are local test artifacts under
`imports/.visual/launch-fixes/`, not installed assets.
