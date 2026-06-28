# ReaSet Jam Room Architecture

Status: inspection-only architecture note for `feature/jamroom-stem-controls`.

This document records the current local architecture before any application behavior changes. It is based on inspection of `README.md`, `LICENSE`, `ReaSet.html`, `Sortable.min.js`, all Lua files under `Requirements/`, and the local repository file list. No local REAPER-owned `main.js` file is present in this repository.

The Jam Room control architecture is now an approved, locked decision: ReaSet will expose dynamic, song-specific browser controls that map onto fixed semantic REAPER/X32 playback slots.

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

Future Jam Room stem state:

- Jam Room browser controls are dynamic per song and come from `[JR:SLOT_ID] Display Label` parent/folder buses in REAPER.
- Each dynamic control maps to one fixed playback slot ID, not to a globally fixed display label.
- One dynamic control may represent one raw source stem or multiple child source stems grouped below the parent bus.
- A Jam Room bus is active for the selected song only when at least one descendant media item has non-zero time overlap with the active top-level song region. Descendant includes direct and nested child tracks inside the folder bus.
- A `[JR:...]` folder bus with no overlapping descendant media is ignored for that song rather than reported as a per-bus configuration error, because it may belong to another song or be intentionally unused.
- The web state should store the bridge-published controls for the active top-level song region in fixed playback-slot order, including display label, normalized slot ID, confirmed mute state, and setup diagnostics.
- Empty or unused fixed slots should not appear in the browser panel for that song.
- When no active valid Jam Room buses are found, the browser should display `No backing stems configured for this song`.

## 4. Safest Jam Room Stem-Control Integration Point

The safest integration point is a modular addition to `ReaSet.html` that does not alter existing setlist, transport, lyrics, chord, loop, or marker parsing behavior:

- Add a compact, touch-friendly Jam Room panel on the main ReaSet screen immediately below the existing transport controls, styled with existing button/toggle patterns.
- Add new JavaScript state dedicated to Jam Room controls, separate from `displayList`, `setlists`, `g_subRegionMap`, and `window.subStates`.
- Poll a new Lua/ReaScript bridge through `GET/PROJEXTSTATE/ReaSetJamRoom/controls` or similarly named project extstate.
- Send user commands through a small command extstate key, such as `SET/PROJEXTSTATE/ReaSetJamRoom/command/...`, then let Lua apply the change and publish actual confirmed state back.
- Update control discovery and availability whenever the active top-level song region changes, using the existing `currentPos`/`activeRegion` derivation as the browser-side song context.

This keeps Jam Room logic beside, but not inside, the existing region/setlist control path. Player-facing controls show dynamic labels only. Fixed slot IDs remain diagnostic/setup information rather than the main visible control name. The browser interface must never infer or alter X32 channel names. ReaSet labels are dynamic and song-specific; X32 labels are permanent playback-slot labels.

## 5. Can The Current Architecture Read And Control REAPER Track Mute Directly?

Not reliably in its current form.

The existing browser architecture can send REAPER web commands, poll transport/regions/markers/extstate, and trigger action IDs. It does not currently request track lists, folder hierarchy, track names, media items, parent-bus mute values, or hardware-output routing. The existing app also has no track-name-to-slot mapping and no representation of whether a Jam Room bus contains child source media in the active song region.

Even if a generic REAPER action could toggle some selected track's mute state, that would be unsafe for this feature because Version 1 requires `[JR:SLOT_ID] Display Label` parsing, duplicate-slot validation among active buses, actual parent-bus mute-state refresh, and descendant media overlap checks within the active song region. The browser does not currently have enough information to do that directly.

## 6. Is A New Lua/ReaScript Bridge Required?

Yes. A small bridge is required for reliable Version 1 behavior.

The bridge should run in the background like the existing lyrics/chords/native-loop scripts and should:

- Discover `[JR:SLOT_ID] Display Label` parent/folder buses associated with the active top-level song region.
- Parse the slot ID and display label from each bus name.
- Treat slot IDs as case-insensitive, normalize them to uppercase internally, preserve the original display label exactly as entered, and treat slot IDs that differ only by case as duplicates.
- Validate that the normalized slot ID is one of the fixed permitted IDs: `DRUMS`, `PERC_FX`, `BASS`, `GTR1`, `GTR2`, `KEYS`, `BVS`, `LEAD_VOX`, `CLICK`, or `EXTRA`.
- Inspect only candidate Jam Room buses with at least one descendant media item overlapping the active song region. Descendant includes direct and nested child tracks inside the folder bus.
- Ignore `[JR:...]` buses with no overlapping descendant media for that song rather than reporting them as per-bus configuration errors.
- Treat each active valid bus as one ReaSet user-facing control.
- Read the parent bus's actual mute state via REAPER track APIs.
- Expose dynamic display labels to ReaSet.
- Expose the fixed slot ID for validation and diagnostics.
- Publish controls in fixed playback-slot order.
- Omit empty or unused slots from the normal browser panel.
- Report configuration errors for active candidates when a Jam Room tag is malformed, a normalized slot ID is invalid, a display label is missing, or more than one active bus claims the same normalized slot ID.
- Exclude invalid or duplicate entries from player-facing controls and instead publish diagnostics for a small expandable `Setup issues` area showing affected track name, issue type, and slot ID where available.
- Accept commands from the web UI to set a valid bus audible/muted or set all active valid non-click buses audible.
- Apply mute changes to the matching parent bus, thereby muting or unmuting all raw child source stems beneath that bus together.
- Publish confirmed state back to project extstate for the web UI to poll.
- Publish bridge-health and stale/error states.

The bridge is small but important because the required source of truth is REAPER's track/folder/media model, not the browser's current setlist model.

## 7. Locked Dynamic-Bus And Fixed-Slot Model

The system has two separate layers:

- Dynamic, song-specific ReaSet controls: these are the labels seen in the browser/tablet interface. They may differ for every song. One control may contain one raw source stem or many source stems grouped together.
- Fixed semantic REAPER/X32 playback slots: these preserve stable X32 channel names and stable personal-IEM mixing from song to song. The X32 must never receive arbitrary changing instrument roles on the same channel.

Each song is represented by a top-level REAPER region. When preparing a song, the user creates only the control buses that make musical sense for that song. Each control bus is a parent/folder bus, with the raw Karaoke Version or other source stems beneath it as children.

Each control bus is named:

`[JR:SLOT_ID] Display Label`

Slot IDs are case-insensitive and normalized to uppercase internally. The recommended authoring convention remains uppercase:

`[JR:GTR1] Guitar 1 / Acoustic`

Examples:

- `[JR:DRUMS] Drums`
- `[JR:PERC_FX] EDrum / SFX`
- `[JR:BASS] Bass`
- `[JR:GTR1] Guitar 1 / Acoustic`
- `[JR:GTR2] Guitar 2 / Lead`
- `[JR:KEYS] Keys`
- `[JR:BVS] Backing Vocals`
- `[JR:LEAD_VOX] Lead Vocal`
- `[JR:CLICK] Click`

The parent bus routes to the corresponding fixed REAPER hardware-output slot. Its descendant tracks contain the raw source stems. One ReaSet toggle controls the mute state of the matching parent `[JR:SLOT_ID]` bus.

A bus is active for a song only when at least one descendant media item has non-zero time overlap with the active top-level song region. Buses without overlapping descendant media are ignored for that song. Only active candidate buses are inspected for malformed tags, invalid slot IDs, missing display labels, and duplicate normalized slot IDs.

Architectural rationale:

- Raw stem names and numbers vary by song.
- Musicians need dynamic, intelligible song-specific labels in ReaSet.
- Personal IEM mixing requires fixed X32 channel semantics.
- Therefore, dynamic ReaSet labels must map to fixed playback slots.
- Only one active control bus may use each fixed slot within a song.
- REAPER routes `CLICK` to its fixed playback slot. X32 configuration, not ReaSet, keeps `PB CLICK` excluded from room speakers while available to selected IEM mixes.

## 8. Proposed File-Change Plan

Existing files to modify after approval:

- `ReaSet.html`: Add Jam Room panel markup/CSS/JS below the existing transport controls, bridge polling, command dispatch, confirmed state rendering, no-stems message, and expandable setup diagnostics. Keep changes modular and avoid altering setlist/transport behavior except reading the active song region already computed by the app.
- `README.md`: Add short setup pointer after implementation, preserving upstream attribution and existing bilingual style if desired.

New files to add after approval:

- `Requirements/ReaSet_JamRoom_Stems.lua`: Background bridge for `[JR:SLOT_ID] Display Label` bus discovery, case-insensitive fixed-slot validation, descendant-media overlap detection, parent-bus mute state, commands, diagnostics, and extstate publishing.
- `docs/JAMROOM_SETUP.md`: Dynamic bus naming convention, fixed playback-slot map, preparing song regions, routing parent buses to hardware outputs, placing raw source stems as children, installing/running the Lua bridge, launching the interface, and troubleshooting.
- `docs/JAMROOM_TEST_PLAN.md`: Manual verification matrix for dynamic controls, fixed slot validation, duplicate slots, empty buses, direct REAPER mute changes, song changes, refreshes, play/stop, lyrics/chords, and offline LAN use.

Files to remain untouched:

- `Sortable.min.js`: Third-party minified dependency.
- REAPER-owned `main.js`: Not included locally and should not be modified.
- Existing X-Raym scripts unless a separate compatibility fix is explicitly approved.
- `LICENSE`: Do not alter GPL text.

## 9. Compatibility And Licensing Risks

- GPL v3 applies to this repository. Keep copyright/license notices and provide source for distributed modified versions.
- SortableJS is MIT licensed; because it is minified third-party code, avoid modifying it and preserve its header.
- X-Raym-derived scripts are GPL v3; preserve attribution if reusing their patterns.
- The current README and files show mojibake/encoding artifacts in some comments/text. Avoid broad encoding churn during implementation.
- The current lyrics script contains a likely typo in `GetNextTrackItem`: it references `item` instead of `start_item`. This does not affect default behavior because `next = false`, but it is a known risk if next-lyrics support is enabled later.
- `reaper.ULT_GetMediaItemNote` may require a compatible API environment such as Ultraschall API, as noted in the README.
- REAPER web interface command support is supplied externally by REAPER's `main.js`; the repo cannot be fully tested standalone.
- ExtState polling should remain modest. The app already has frequent transport and lyrics polling; Jam Room state polling should be small and avoid adding unnecessary load.
- Bus naming should use `[JR:SLOT_ID] Display Label` syntax and fixed permitted slot IDs. Slot IDs are case-insensitive, normalized to uppercase internally, and should be authored uppercase by convention.
- The fixed playback-slot map exhausts the 16 reserved REAPER playback lanes. Version 1 must not propose additional fixed slots.
- The browser must not rename, infer, or mutate X32 channel labels. X32 and personal-monitor apps keep permanent playback-slot labels.

## 10. Manual Test Plan

Baseline before Jam Room changes:

- Load `ReaSet.html` through REAPER's web interface.
- Confirm `SYNC`, region list, play, pause, stop, cue, auto-stop, chain, skip, loop, sub-region expansion, Live View, lyrics, and chords still work.
- Confirm setlist ordering and preferences persist after browser refresh.

Jam Room Version 1 tests after implementation:

- Panel placement: Jam Room controls appear on the main ReaSet screen immediately below the existing transport controls.
- Bridge health: panel shows a clear unavailable/offline state when the Lua bridge is not running.
- Valid bus discovery: active `[JR:SLOT_ID] Display Label` parent buses are recognized for the selected top-level song region.
- Active bus definition: a bus is active only when at least one direct or nested descendant media item has non-zero overlap with the active song region.
- Fixed order: the panel shows active valid buses in fixed playback-slot order, not arbitrary track order.
- Dynamic labels: browser buttons use the song-specific display label only, while diagnostics retain the fixed slot ID.
- Empty slots and inactive buses: unused fixed playback slots and `[JR:...]` buses with no overlapping descendant media are not shown in the normal panel and are not reported as per-bus configuration errors.
- No stems: a song with no active valid Jam Room buses displays `No backing stems configured for this song`.
- Invalid slot: an active candidate with an unrecognized `[JR:...]` slot reports a setup issue and does not render as a player-facing control.
- Duplicate slot: more than one active bus claiming the same normalized slot in one song reports a setup issue and does not render duplicate player-facing controls.
- Case duplicate: slot IDs that differ only by case are treated as duplicates.
- Malformed tag or missing label: active candidates with malformed Jam Room tags or missing display labels report setup issues and do not render as player-facing controls.
- State display: initial buttons reflect actual parent-bus mute state, not browser defaults.
- Individual toggle: tapping each valid control changes the parent bus mute state and the UI updates only from confirmed refreshed state.
- Grouped child stems: muting one parent bus mutes all raw child source stems beneath it together.
- Direct REAPER change: changing parent-bus mute inside REAPER is reflected in the browser on the next poll.
- Song change: selecting/cueing another song refreshes dynamic controls and availability without resetting mute choices.
- All backing on: the explicit `ALL BACKING ON` action unmutes all active valid non-click parent buses and then refreshes confirmed state.
- Click control: `CLICK` remains a separate explicit user-facing control and is not affected by `ALL BACKING ON`.
- Click routing: REAPER routes `CLICK` to `PB CLICK`; X32 configuration, not ReaSet, keeps `PB CLICK` excluded from room speakers while available to selected IEM mixes.
- Browser refresh: state after refresh reflects actual REAPER parent-bus mute state.
- Playback: play/stop/cue behavior remains unchanged while toggling Jam Room controls.
- Lyrics/chords: existing lyric and chord displays continue to update with their scripts running.
- Offline/local network: no external network/CDN dependency is introduced.
- Error state: communication loss or malformed bridge payload produces a clear non-destructive UI state.

## 11. Recommended First Implementation Milestone

Start with a read-only bridge and display.

Milestone 1 should add `Requirements/ReaSet_JamRoom_Stems.lua` and a small read-only panel below the existing transport controls. It should show each active valid `[JR:SLOT_ID] Display Label` control for the selected song in fixed playback-slot order, using dynamic display labels as the player-facing names. It should publish fixed slot IDs only for diagnostics, confirm parent-bus mute state, ignore inactive buses with no overlapping descendant media, display `No backing stems configured for this song` when appropriate, and expose malformed/invalid/duplicate active candidates in an expandable setup area. No mute buttons should be interactive until this state path is proven reliable.

## Milestone Plan

Milestone 0: repository and integration analysis

- Complete this architecture review.
- Confirm the branch and clean worktree.
- Confirm no local `main.js` exists and do not modify REAPER-owned files.
- Identify the need for a small Lua bridge.
- Lock the dynamic ReaSet controls plus fixed REAPER/X32 playback slots design.

Milestone 1: read-only stem availability/status display

- Add the Lua bridge in read-only mode.
- Discover active `[JR:SLOT_ID] Display Label` parent buses for the selected top-level song region.
- Define active buses by non-zero overlap between the song region and at least one direct or nested descendant media item.
- Normalize slot IDs to uppercase while preserving display labels exactly as entered.
- Validate permitted slot IDs, duplicate normalized slot claims, malformed tags, and missing labels only among active candidate buses.
- Publish bridge heartbeat, dynamic labels, fixed slot IDs, parent-bus mute state, and active-region availability.
- Add a non-interactive web panel below the transport controls that renders confirmed bridge state in fixed playback-slot order.
- Hide empty/unused slots and inactive buses from the normal panel.
- Add the no-stems message and expandable setup diagnostics.
- Preserve existing ReaSet behavior.

Milestone 2: interactive mute/unmute controls

- Add commands for individual parent-bus mute/unmute.
- Add `ALL BACKING ON` command for active valid non-click buses.
- Keep `CLICK` as a separate explicit user-facing control because it is IEM-only.
- Keep button state driven by refreshed actual REAPER state, not optimistic UI state.
- Ensure malformed, duplicate, invalid, or inactive buses cannot be toggled misleadingly.

Milestone 3: robust state synchronisation and error handling

- Add stale-data/bridge-offline detection.
- Verify direct REAPER parent-bus mute changes are reflected by polling.
- Add clear UI states for invalid slots, duplicate slots, malformed labels, missing labels, no active stems, and communication loss.
- Add docs and manual test plan.

Milestone 4: future tempo/transposition investigation

- Investigate REAPER project/item settings for synchronized tempo changes across stem media items.
- Investigate pitch/key transposition without affecting the click track.
- Test item timebase, project timebase, preserve pitch behavior, stretch markers, tempo map behavior, and item pitch/playrate interactions before implementation.
- Keep tempo/key controls out of Version 1.

## Human Decisions Needed Before Coding

- No blocking architecture decisions remain before Version 1 implementation.
- Optional implementation detail: choose the exact collapsed/expanded visual treatment for the `Setup issues` diagnostics area.

## Locked Decisions

The approved control convention is:

`[JR:SLOT_ID] Display Label`

Slot IDs are case-insensitive and normalized to uppercase internally. Display labels are preserved exactly as entered. The recommended authoring convention remains uppercase, for example:

`[JR:GTR1] Guitar 1 / Acoustic`

A bus is active for a song only when at least one direct or nested descendant media item has non-zero overlap with the active top-level song region. Inactive `[JR:...]` buses are ignored for that song. When no active valid Jam Room buses are found, the browser displays `No backing stems configured for this song`.

The Jam Room panel is locked to the main ReaSet screen immediately below the existing transport controls. Player-facing controls show dynamic labels only; fixed slot IDs appear only in setup/diagnostic contexts.

The bulk action label is `ALL BACKING ON`. It unmutes active valid non-click buses only. `CLICK` remains a separate explicit control because it is IEM-only. REAPER routes `CLICK` to the fixed `PB CLICK` playback slot; X32 configuration, not ReaSet, keeps that slot out of room speakers.

Fixed playback slots:

| Slot ID | REAPER hardware output | X32 mixer channel(s) | Permanent X32 label | Format |
| --- | ---: | ---: | --- | --- |
| `DRUMS` | 1-2 | 17-18 | `PB DRUMS` | Stereo |
| `PERC_FX` | 3 | 19 | `PB PERC/FX` | Mono |
| `BASS` | 4 | 20 | `PB BASS` | Mono |
| `GTR1` | 5-6 | 21-22 | `PB GTR 1` | Stereo |
| `GTR2` | 7-8 | 23-24 | `PB GTR 2` | Stereo |
| `KEYS` | 9-10 | 25-26 | `PB KEYS` | Stereo |
| `BVS` | 11-12 | 27-28 | `PB BVs` | Stereo |
| `LEAD_VOX` | 13 | 29 | `PB LEAD VOX` | Mono |
| `CLICK` | 14 | 30 | `PB CLICK` | Mono, IEM-only |
| `EXTRA` | 15-16 | 31-32 | `PB EXTRA` | Stereo |

This exhausts the 16 reserved REAPER playback lanes. Do not add fixed slots in Version 1.
