# Song browsing and recovery — v3.13

- Songs first prepared from YouTube can be reopened from the matching Fadr
  library recording. Identity is checked against the saved source URL and Fadr
  asset ID, including IDs learned after the queue entry was created. Removing
  an entry retains its cached audio, review choices and original operation ID.
  Selecting it again restores the existing workspace without a new paid split.
  Different recordings with the same title still require distinct names.
- Import rows have a named Open button. Remove from queue is under More and
  asks for confirmation; cancelling leaves the workspace alone. A restored
  review opens directly at the stem review rather than the Activity screen.
- Playback lists default to Artist A–Z. The visible Sort selector offers Song
  title A–Z and Custom order. The choice is saved per project/setlist. Dragging
  a song selects Custom order. Sorting changes browser playback order, not
  the audio positions in the REAPER project, and does not start playback.
  Artist/title parsing uses the established `Artist - Song` naming convention;
  names without an artist sort by their full name after named artists.
- The Live dashboard and Stage display entries and keyboard shortcuts are
  removed. Their DOM is inert for compatibility with shared rendering helpers.
  The former More menu now contains only connection status and Reconnect.

After JamRoom Update.bat, restart the importer and refresh ReaSet and the
importer with Ctrl+F5. Re-select the previously blocked recording from Fadr;
its existing work should open for review (legacy cached jobs may ask to resume).
