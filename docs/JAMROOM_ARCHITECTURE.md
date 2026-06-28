# ReaSet Jam Room Architecture

Status: inspection-only architecture note for `feature/jamroom-stem-controls`.

This document records the current local architecture before any application behavior changes. It is based on inspection of `README.md`, `LICENSE`, `ReaSet.html`, `Sortable.min.js`, all Lua files under `Requirements/`, and the local repository file list. No local REAPER-owned `main.js` file is present in this repository.

## 1. Current Codebase Map

- `README.md`: User-facing project documentation in English and Spanish. It describes ReaSet as a REAPER web interface for live setlist management, transport control, region navigation, lyrics, chords, sub-regions, local persistence, visual configuration, and manual installation into REAPER's web root. It also states that `main.js` is supplied by REAPER and is not included here.
- `LICENSE`: GNU GPL v3 license text. The project should preserve GPL notices and source availability for distributed modified versions.
- `ReaSet.html`: The complete web application in one no-build HTML file. It contains CSS, markup, and JavaScript for the setlist UI, REAPER web communication, region and marker parsing, transport actions, local storage, lyrics/chords panels, live view, canvas view, MIDI learn, and native-loop integration.
- `Sortable.min.js`: Third-party minified SortableJS 1.15.7, MIT licensed. It is only used to drag-sort setlist entries. Treat as vendored third-party code and do not modify.
- `Requirements/X-Raym_Convert Lyrics track items notes for dedicated web browser interface.lua`: Background ReaScript that finds the `lyrics` track, reads the item under the play/edit cursor, and writes current and optional next lyric text to REAPER project extstate namespace `XR_Lyrics`.
- `Requirements/X-Raym_Convert Chords track items notes for dedicated web browser interface.lua`: Background ReaScript based on the lyrics script. It finds the `chords` track, reads item notes at the current position, and writes text to project extstate namespace `XR_Chords`.
- `Requirements/ReaSet_NativeLoop.lua`: Background ReaScript for stronger loop behavior. It watches extstate namespace `ReaSet`, creates/removes a temporary `ReaSet Loop` region, controls REAPER repeat and loop time range, and advertises readiness via `ReaSet/nativeLoopReady`.
- REAPER `main.js`: Not present locally. `ReaSet.html` expects `wwr_req`, `wwr_req_recur`, and `wwr_start` to be injected by REAPER's built-in web interface when deployed beside REAPER's `main.js`.

## 2. How ReaSet Communicates With REAPER

`ReaSet.html` uses REAPER Web Interface globals:

- `wwr_req_recur("TRANSPORT", 33)` for play state and current play position.
- `wwr_req_recur("REGION", 1000)` for project regions.
- `wwr_req_recur("MARKER", 1000)` for markers.
- `wwr_req_recur("GET/PROJEXTSTATE/XR_Lyrics/text;GET/PROJEXTSTATE/XR_Lyrics/next", 10)` for lyric text from the lyrics Lua script.
- `wwr_req_recur("GET/PROJEXTSTATE/XR_Chords/text", 200)` for chord text from the chords Lua script.
- `wwr_req("GET/EXTSTATE/ReaSet/nativeLoopReady")` and a recurring poll for native-loop availability.
- Direct commands such as `wwr_req(1007)`, `wwr_req(1008)`, `wwr_req(1016)`, `wwr_req("SET/POS/..." )`, `wwr_req("SET/REPEAT/0")`, and `wwr_req("SET/EXTSTATEPERSIST/ReaSet/..." )` for transport, seeking, repeat, and Lua bridge signaling.

All inbound web responses are processed by `wwr_onreply(results)`, which splits lines/tabs and updates browser-side state for transport, regions, markers, extstate, lyrics, and chords.

## 3. Current State Representation

Song regions:

- Raw REAPER region rows are collected into `g_regions`.
- `syncRegions()` turns them into `displayList` entries with `id`, raw `name`, cleaned `displayName`, `start`, `end`, `duration`, `color`, and behavior flags.
- Top-level songs are inferred as regions that are not contained by a longer region. Contained regions become sub-regions.
- Temporary region `ReaSet Loop` is ignored.

Setlists:

- `displayList` is the active ordered setlist in memory.
- `setlists` stores named setlists as arrays of `{ id, chain, skipped, loop }`.
- Storage keys are project-namespaced after `REGION_LIST_END` using a fingerprint derived from region IDs: `reaper_setlists_v9_<projectKey>` and `reaper_current_setlist_<projectKey>`.
- Drag sorting is handled by SortableJS and persisted to localStorage.

Transport:

- `isPlaying` and `currentPos` come from `TRANSPORT` replies.
- Play/pause/stop/cue are sent through REAPER action IDs and `SET/POS` commands.
- End-of-region logic, queued regions, auto-stop, chain, and loop behavior live in `updatePlaybackUI()`.

Lyrics and chords:

- Lua scripts read item notes from exact track names `lyrics` and `chords`.
- Lua writes text into `XR_Lyrics` and `XR_Chords` project extstate keys.
- The web UI polls those keys and renders lyrics/chords panels and canvas widgets.

Sub-regions:

- Region-contained sub-regions are preferred where available.
- Marker-based sections are built from markers inside a song when no region sub-regions exist.
- `parseRegionFlags()` and `parseMarkerName()` support inline behavior/display commands such as `+LOOP`, `+LOOP:N`, `+LOOPFULL`, `+PAUSE`, `+SKIP`, `{info}`, `[color]`, `[mm:ss]`, `[.class]`, and `>>> Target`.
- Per-section live state is stored in `window.subStates` with loop, skip, loop count, and loop defaults.

Local storage and user preferences:

- Setlists and current setlist are project-namespaced after region fingerprinting.
- Song and section overrides are stored in `reaset_song_overrides_<projectKey>`.
- UI preferences such as theme, hide skipped, lyrics fonts/sizes, filters, live settings, canvas positions, and MIDI mappings are stored in localStorage.

Live state:

- `updatePlaybackUI()` derives the active song and active sub-region from `currentPos`.
- It updates active row CSS, progress fills, remaining time, lyrics/chord titles, live view, canvas view, loop counters, and special marker triggers.
- `queuedRegion`, `lastActiveID`, native-loop globals, and special-trigger guards hold transient playback state.

## 4. Safest Jam Room Stem-Control Integration Point

The safest integration point is a modular addition to `ReaSet.html` that does not alter existing setlist, transport, lyrics, chord, loop, or marker parsing behavior:

- Add a `BACKING STEMS` panel near the existing main controls or sidebar area, styled with existing button/toggle patterns.
- Add new JavaScript state dedicated to Jam Room stems, separate from `displayList`, `setlists`, `g_subRegionMap`, and `window.subStates`.
- Poll a new Lua/ReaScript bridge through `GET/PROJEXTSTATE/ReaSetJamRoom/stems` or similarly named project extstate.
- Send user commands through a small command extstate key, such as `SET/PROJEXTSTATE/ReaSetJamRoom/command/...`, then let Lua apply the change and publish actual confirmed state back.
- Update availability whenever the active song region changes, using the existing `currentPos`/`activeRegion` derivation as the browser-side song context.

This keeps stem logic beside, but not inside, the existing region/setlist control path.

## 5. Can The Current Architecture Read And Control REAPER Track Mute Directly?

Not reliably in its current form.

The existing browser architecture can send REAPER web commands, poll transport/regions/markers/extstate, and trigger action IDs. It does not currently request track lists, track names, media items, or track mute values. The existing app also has no track-name-to-track mapping and no representation of whether a named track contains media in the active song region.

Even if a generic REAPER action could toggle some selected track's mute state, that would be unsafe for this feature because Version 1 requires exact track-name matching, actual state refresh, and media availability within the active song region. The browser does not currently have enough information to do that directly.

## 6. Is A New Lua/ReaScript Bridge Required?

Yes. A small bridge is required for reliable Version 1 behavior.

The bridge should run in the background like the existing lyrics/chords/native-loop scripts and should:

- Find exact track names: `STEM_DRUMS`, `STEM_BASS`, `STEM_GUITAR_1`, `STEM_GUITAR_2`, `STEM_KEYS`, `STEM_VOCALS`, `STEM_CLICK`.
- Read each track's actual mute state via REAPER track APIs.
- Check whether each stem track has at least one media item overlapping the active song region.
- Accept commands from the web UI to set a role audible/muted or set all stems audible.
- Apply mute changes to the actual matching tracks.
- Publish confirmed state back to project extstate for the web UI to poll.
- Publish missing-track, unavailable-stem, and bridge-health/error states.

The bridge is small but important because the required source of truth is REAPER's track model, not the browser's current setlist model.

## 7. Proposed File-Change Plan

Existing files to modify after approval:

- `ReaSet.html`: Add Jam Room panel markup/CSS/JS, bridge polling, command dispatch, state rendering, and error display. Keep changes modular and avoid altering setlist/transport behavior except reading the active song region already computed by the app.
- `README.md`: Add short setup pointer after implementation, preserving upstream attribution and existing bilingual style if desired.

New files to add after approval:

- `Requirements/ReaSet_JamRoom_Stems.lua`: Background bridge for stem discovery, availability, mute state, commands, and extstate publishing.
- `docs/JAMROOM_SETUP.md`: Track naming convention, preparing song regions, placing media items, installing/running the Lua bridge, launching the interface, and troubleshooting.
- `docs/JAMROOM_TEST_PLAN.md`: Manual verification matrix for stem state, missing stems, direct REAPER mute changes, song changes, refreshes, play/stop, lyrics/chords, and offline LAN use.

Files to remain untouched:

- `Sortable.min.js`: Third-party minified dependency.
- REAPER-owned `main.js`: Not included locally and should not be modified.
- Existing X-Raym scripts unless a separate compatibility fix is explicitly approved.
- `LICENSE`: Do not alter GPL text.

## 8. Compatibility And Licensing Risks

- GPL v3 applies to this repository. Keep copyright/license notices and provide source for distributed modified versions.
- SortableJS is MIT licensed; because it is minified third-party code, avoid modifying it and preserve its header.
- X-Raym-derived scripts are GPL v3; preserve attribution if reusing their patterns.
- The current README and files show mojibake/encoding artifacts in some comments/text. Avoid broad encoding churn during implementation.
- The current lyrics script contains a likely typo in `GetNextTrackItem`: it references `item` instead of `start_item`. This does not affect default behavior because `next = false`, but it is a known risk if next-lyrics support is enabled later.
- `reaper.ULT_GetMediaItemNote` may require a compatible API environment such as Ultraschall API, as noted in the README.
- REAPER web interface command support is supplied externally by REAPER's `main.js`; the repo cannot be fully tested standalone.
- ExtState polling should remain modest. The app already has frequent transport and lyrics polling; stem state polling should be small and avoid adding unnecessary load.
- Track name matching should be exact for stem tracks and case behavior should be documented. The existing lyrics/chords scripts use case-insensitive matching.

## 9. Manual Test Plan

Baseline before Jam Room changes:

- Load `ReaSet.html` through REAPER's web interface.
- Confirm `SYNC`, region list, play, pause, stop, cue, auto-stop, chain, skip, loop, sub-region expansion, Live View, lyrics, and chords still work.
- Confirm setlist ordering and preferences persist after browser refresh.

Jam Room Version 1 tests after implementation:

- Bridge health: panel shows a clear unavailable/offline state when the Lua bridge is not running.
- Track discovery: all seven standard stem tracks are recognized by exact expected names.
- Missing track: a missing standard track is shown as unavailable, not silently assumed off/on.
- Availability: if a stem track has no media item overlapping the active song region, its control is disabled or marked unavailable.
- State display: initial buttons reflect actual REAPER mute state, not browser defaults.
- Individual toggle: tapping each role changes REAPER mute state and the UI updates only from confirmed refreshed state.
- Direct REAPER change: changing mute inside REAPER is reflected in the browser on the next poll.
- Song change: selecting/cueing another song refreshes stem availability for that region without resetting mute choices.
- All stems on: the explicit action unmutes all available stem tracks and then refreshes confirmed state.
- Browser refresh: state after refresh reflects actual REAPER track mute state.
- Playback: play/stop/cue behavior remains unchanged while toggling stems.
- Lyrics/chords: existing lyric and chord displays continue to update with their scripts running.
- Offline/local network: no external network/CDN dependency is introduced.
- Error state: communication loss or malformed bridge payload produces a clear non-destructive UI state.

## 10. Recommended First Implementation Milestone

Start with a read-only bridge and display.

Milestone 1 should add `Requirements/ReaSet_JamRoom_Stems.lua` and a small read-only panel that shows each standard stem role as present/missing, available/unavailable for the active region, and muted/audible according to actual REAPER state. No mute buttons should be interactive until this state path is proven reliable.

## Milestone Plan

Milestone 0: repository and integration analysis

- Complete this architecture review.
- Confirm the branch and clean worktree.
- Confirm no local `main.js` exists and do not modify REAPER-owned files.
- Identify the need for a small Lua bridge.

Milestone 1: read-only stem availability/status display

- Add the Lua bridge in read-only mode.
- Publish bridge heartbeat, track presence, mute state, and active-region availability.
- Add a non-interactive web panel that renders confirmed bridge state.
- Preserve existing ReaSet behavior.

Milestone 2: interactive mute/unmute controls

- Add commands for individual role mute/unmute.
- Add `ALL STEMS ON` command.
- Keep button state driven by refreshed actual REAPER state, not optimistic UI state.
- Ensure unavailable/missing stems cannot be toggled misleadingly.

Milestone 3: robust state synchronisation and error handling

- Add stale-data/bridge-offline detection.
- Verify direct REAPER mute changes are reflected by polling.
- Add clear UI states for missing tracks, unavailable stems, and communication loss.
- Add docs and manual test plan.

Milestone 4: future tempo/transposition investigation

- Investigate REAPER project/item settings for synchronized tempo changes across stem media items.
- Investigate pitch/key transposition without affecting the click track.
- Test item timebase, project timebase, preserve pitch behavior, stretch markers, tempo map behavior, and item pitch/playrate interactions before implementation.
- Keep tempo/key controls out of Version 1.

## Human Decisions Needed Before Coding

- Where should the Backing Stems panel live in the current UI: main screen under transport, sidebar section, Live View, or a dedicated Jam Room mode toggle?
- Should stem track matching be strictly case-sensitive, or should it accept case-insensitive matches while warning about non-standard names?
- When a standard track is missing, should the UI show the role as hidden, disabled, or visible with an explicit missing warning?
- Should `STEM_CLICK` default to the same global speaker path as the other stems, or is it expected to be routed separately in REAPER while still controlled from this panel?
