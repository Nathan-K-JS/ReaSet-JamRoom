# Prior Attempt Reference — Jam Room Feature

> **How to use this document:** This describes a design produced during an earlier
> attempt at this feature, using a different AI coding assistant (ChatGPT + Codex), on
> the branch `feature/jamroom-stem-controls`. It reached a partially-implemented,
> statically-reviewed-but-not-live-tested state.
>
> **This is reference material, not a specification to implement.** Some of what's
> described here reflects genuine hard constraints (hardware limits, REAPER API
> limitations, licensing) that will apply no matter who designs the solution. Other
> parts reflect design choices that one particular reasoning process arrived at, which
> a fresh design pass might reasonably do differently — or might independently arrive
> at the same answer, which would itself be a useful signal.
>
> When forming your own design, please explicitly distinguish, in your own analysis:
> - What here is a **hard constraint** you must respect regardless of approach
>   (e.g. physical hardware, licensing terms, REAPER API capabilities/limitations).
> - What here is a **prior design decision** worth treating as one valid option among
>   others, to be adopted, adapted, or discarded based on your own judgment.
>
> Do not treat implementation details (function names, JSON field names, exact tag
> syntax, file layout choices) as required just because they appear below.

---

# ReaSet Jam Room Project Brief

## 1. Project Overview

### What the project is and what problem it solves

This project is a customisation of the open-source **ReaSet** web interface for **REAPER**, intended to run a home “jam room” rehearsal system.

The system uses:

* A Windows DAW PC running REAPER.
* A Behringer X32 Rack connected over USB as the audio interface and monitor mixer.
* Karaoke Version-style backing stems arranged in REAPER projects.
* A tablet-friendly ReaSet browser interface, normally controlled from an Android tablet over the local network.
* Existing ReaSet features for song/setlist selection, transport, lyrics, chords, Live view, Canvas view, loops, and section navigation.

The custom feature is a dedicated **Tracks** tab. It lets musicians see which backing groups are available for the current song and, in later milestones, mute or restore them with large touch-friendly controls. The system must work without exposing technical REAPER routing or X32 channel terminology to ordinary users.

### Intended user

Primary users are musicians rehearsing in a small home jam room, including non-technical family members and children. The system must feel like a simple rehearsal jukebox rather than a DAW administration interface.

The owner/operator prepares REAPER projects, imports backing stems, creates song regions, assigns buses, and configures the X32. Ordinary players use the tablet to select songs, follow lyrics/chords, start/stop playback, and eventually control which backing parts are heard.

### Core value proposition

The project provides song-specific, musician-friendly backing-track controls while preserving fixed mixer and IEM semantics. A song may call a backing group “Guitar 1 / Acoustic” while another calls the same semantic slot “Rhythm Guitar”; both still route through the same permanent X32 playback channel and retain the same IEM mix behaviour.

The design separates flexible song preparation from stable live-routing infrastructure. Players see only meaningful musical labels; REAPER and the X32 maintain fixed, dependable signal paths.

---

## 2. Functional Requirements

### Existing ReaSet functionality that must be preserved

The Jam Room work must not break the upstream ReaSet application’s existing capabilities, including:

* Setlist management and drag sorting.
* REAPER region-based song discovery.
* Nested region and marker-based song-section handling.
* Transport controls: play, pause, stop, cue, seek.
* Song chaining, looping, auto-stop, skips, and queued regions.
* Lyrics display.
* Chords display.
* Live view.
* Canvas view.
* MIDI mappings.
* Local browser persistence for setlists, song overrides, UI preferences, live settings, and Canvas settings.
* Native Loop support through `Requirements/ReaSet_NativeLoop.lua`.

### Jam Room feature set

#### Tracks tab

Add a top-level ReaSet tab named:

```text
Tracks
```

It must sit with the existing top-level views such as Show, Lyrics, Chords, Live, and Canvas.

The Tracks tab must:

* Be the only normal player-facing location for backing-track controls.
* Not clutter the Show screen.
* Use the existing ReaSet visual language.
* Be usable on a tablet touch screen.
* Show only active valid backing controls for the current song.
* Show controls in fixed semantic playback-slot order.
* Show dynamic, song-specific display labels.
* Show explicit state text: `Audible` or `Muted`.
* Avoid relying on colour alone for state.
* Keep technical details hidden from the ordinary player-facing view.

The initial Milestone 1 tab includes:

* Title: `Tracks`
* Temporary badge: `Status only`
* Read-only backing-control rows
* Collapsed-by-default `Setup issues` area
* Exact no-controls message:

```text
No backing stems configured for this song
```

The Tracks UI must not display, in the normal player-facing list:

* Internal slot IDs.
* Permanent PB bus names.
* REAPER routing.
* Hardware output numbers.
* X32 channel numbers.
* Source track names.

Technical details may appear only in `Setup issues`.

#### Dynamic backing-track discovery

Each song is represented by a top-level REAPER region.

The system discovers song-specific arrangement buses named:

```text
[JR:SLOT_ID] Display Label
```

Examples:

```text
[JR:DRUMS] Drums
[JR:PERC_FX] EDrum / SFX
[JR:BASS] Bass
[JR:GTR1] Guitar 1 / Acoustic
[JR:GTR2] Guitar 2 / Lead
[JR:KEYS] Keys
[JR:BVS] Backing Vocals
[JR:LEAD_VOX] Lead Vocal
[JR:CLICK] Click
```

Rules:

* `SLOT_ID` is case-insensitive in meaning and normalised internally to uppercase.
* Display labels are preserved as authored.
* Uppercase tag authoring remains the preferred convention.
* The bus is a REAPER folder/parent arrangement bus.
* Raw source stems sit beneath that bus as direct or nested descendants.
* A bus is active for a song only when at least one descendant media item has non-zero overlap with the active song region.
* `[JR:...]` buses with no overlapping descendant media are ignored for that song; they are not configuration errors.
* Empty fixed slots do not appear in the player-facing Tracks list.
* Only one active arrangement bus may claim a slot in a given song.

#### Fixed semantic playback slots

The dynamic labels map to fixed semantic playback slots. The slots, fixed REAPER outputs, and permanent X32 channels are:

| Slot ID    | Permanent REAPER bus | REAPER output(s) | X32 return channel(s) | X32 label     | Format         |
| ---------- | -------------------- | ---------------: | --------------------: | ------------- | -------------- |
| `DRUMS`    | `PB DRUMS`           |              1–2 |                 17–18 | `PB DRUMS`    | Stereo         |
| `PERC_FX`  | `PB PERC/FX`         |                3 |                    19 | `PB PERC/FX`  | Mono           |
| `BASS`     | `PB BASS`            |                4 |                    20 | `PB BASS`     | Mono           |
| `GTR1`     | `PB GTR 1`           |              5–6 |                 21–22 | `PB GTR 1`    | Stereo         |
| `GTR2`     | `PB GTR 2`           |              7–8 |                 23–24 | `PB GTR 2`    | Stereo         |
| `KEYS`     | `PB KEYS`            |             9–10 |                 25–26 | `PB KEYS`     | Stereo         |
| `BVS`      | `PB BVs`             |            11–12 |              `PB BVs` | Stereo        |                |
| `LEAD_VOX` | `PB LEAD VOX`        |               13 |                    29 | `PB LEAD VOX` | Mono           |
| `CLICK`    | `PB CLICK`           |               14 |                    30 | `PB CLICK`    | Mono, IEM-only |
| `EXTRA`    | `PB EXTRA`           |            15–16 |                 31–32 | `PB EXTRA`    | Stereo         |

This consumes all 16 reserved REAPER playback lanes. Version 1 must not add additional fixed slots.

#### Permanent PB buses

Each permanent `PB` bus is REAPER project-template infrastructure:

* It must exist once per project template.
* It must never contain song media itself.
* It must never appear as a dynamic ReaSet Tracks control.
* It is the only layer with direct hardware-output assignments.
* It is the actual mute target for Jam Room controls.

Required signal flow:

```text
Raw source stems
    ↓
Song-specific [JR:SLOT_ID] Display Label folder bus
    ↓
Permanent PB slot bus
    ↓
Fixed REAPER hardware output
    ↓
Fixed X32 playback return channel(s)
```

For example:

```text
Acoustic Guitar source stem
    ↓
[JR:GTR1] Guitar 1 / Acoustic
    ↓
PB GTR 1
    ↓
REAPER outputs 5–6
    ↓
X32 channels 21–22
```

#### Mute-state behaviour

The permanent PB bus mute state is the single source of truth.

This means:

* ReaSet must not maintain a separate browser-side mute map.
* Lua must not maintain a separate session mute map.
* A ReaSet control represents the mute state of its resolved permanent PB bus.
* Muting `PB GTR 1` affects any current or future active `[JR:GTR1]` arrangement bus routing through it.
* Mute behaviour therefore persists naturally through song changes.

#### Future interactive controls: Milestone 2

After read-only status is proven reliable, each Tracks row will become a large touch target that:

* Mutes/unmutes the resolved permanent PB bus.
* Does not use optimistic browser state.
* Waits for the Lua bridge to publish confirmed REAPER state.
* Cannot act on invalid, duplicate, inactive, or unresolved controls.

A bulk action will be added with the exact label:

```text
ALL BACKING ON
```

It must:

* Unmute only permanent PB buses corresponding to active valid non-click controls in the current song.
* Not affect `PB CLICK`.
* Refresh from confirmed REAPER state afterward.

`CLICK` remains a separate explicit player-facing control. X32 routing, not ReaSet, keeps `PB CLICK` out of room speakers while permitting it in selected IEM mixes.

### Diagnostics and validation

The Lua bridge must detect and publish setup issues for active candidate buses, including:

* Malformed `[JR:...]` tag.
* Missing display label.
* Invalid slot ID.
* Duplicate active slot claim.
* Missing required permanent PB bus.
* Eventually, duplicate permanent PB bus names.

Invalid, duplicate, or unresolved candidates must not appear as normal player-facing controls.

The application must safely show bridge unavailable, malformed, stale, error, and no-active-song states. It must not present cached or stale `Audible`/`Muted` information as confirmed live state.

### Explicitly out of scope for current implementation

The following are not part of Milestone 1 or Milestone 2:

* Direct X32 remote control from ReaSet.
* Dynamic renaming of X32 channels.
* Browser-side audio routing.
* Per-song direct hardware-output routing.
* A new custom native tablet application.
* Controlling stems using arbitrary REAPER selected-track actions.
* Adding more fixed playback lanes beyond the defined 16.
* Tempo or key/transposition control implementation.
* Validation of actual hardware-output assignments in the initial bridge.
* Cloud services, external databases, CDNs, or remote internet dependencies.

A future top-level tab named `Tempo & Key` is reserved, but must not be added as an empty placeholder. Its technical model is intentionally deferred until REAPER tempo-map, item timebase, preserve-pitch, stretch-marker, playrate, and click-track behaviour have been researched and tested.

---

## 3. Technical Architecture (as previously implemented)

### Repository and branch

Prior work occurred on branch:

```text
feature/jamroom-stem-controls
```

The project is a fork/customisation of ReaSet.

### Languages, libraries, and runtime

| Area                  | Technology                                    |
| --------------------- | --------------------------------------------- |
| Browser application   | Single-file HTML, CSS, and vanilla JavaScript |
| REAPER integration    | REAPER Web Interface globals                  |
| REAPER bridge         | Lua ReaScript                                 |
| Drag sorting          | SortableJS 1.15.7, minified vendored file     |
| DAW/runtime           | REAPER on Windows                             |
| Audio interface/mixer | Behringer X32 Rack over USB                   |
| Tablet interface      | Browser on Android over local Wi-Fi/LAN       |

There is no React, Vue, Angular, TypeScript, Node.js build system, package manager, REST backend, database server, or custom API server. (Note: whether this remains the right call is worth re-examining, though the absence of a REST/backend option is a REAPER Web Interface limitation, not a stylistic choice.)

### Important source files (existing repo, still applicable)

```text
ReaSet.html
Sortable.min.js
README.md
LICENSE
Requirements/
  X-Raym_Convert Lyrics track items notes for dedicated web browser interface.lua
  X-Raym_Convert Chords track items notes for dedicated web browser interface.lua
  ReaSet_NativeLoop.lua
  ReaSet_JamRoom_Stems.lua   <- prior attempt's implementation, exists on the other branch
docs/
  JAMROOM_ARCHITECTURE.md    <- prior attempt's architecture doc, exists on the other branch
```

Files that must normally remain untouched:

```text
Sortable.min.js
LICENSE
REAPER-owned main.js
Existing X-Raym scripts
Requirements/ReaSet_NativeLoop.lua
```

`main.js` is not included in this repository. It is provided by REAPER’s built-in web interface deployment and injects the browser integration globals.

### Browser-to-REAPER integration

`ReaSet.html` uses REAPER Web Interface globals:

```javascript
wwr_req(...)
wwr_req_recur(...)
wwr_onreply(results)
wwr_start()
```

Existing recurring requests include:

```javascript
wwr_req_recur("TRANSPORT", 33);
wwr_req_recur("REGION", 1000);
wwr_req_recur("MARKER", 1000);
wwr_req_recur("GET/PROJEXTSTATE/XR_Lyrics/text;GET/PROJEXTSTATE/XR_Lyrics/next", 10);
wwr_req_recur("GET/PROJEXTSTATE/XR_Chords/text", 200);
```

The prior attempt added:

```javascript
wwr_req_recur("GET/PROJEXTSTATE/ReaSetJamRoom/controls", 500);
```

This general mechanism (REAPER Web Interface globals, extstate as the two-way channel) is a genuine constraint of the platform — REAPER's web interface does not offer an alternative. The specific extstate key names, polling interval, and payload shape below were this particular implementation's choices.

### Jam Room data flow (as previously designed)

```text
REAPER transport/edit cursor
    ↓
Lua bridge determines active top-level song region
    ↓
Lua scans REAPER folder hierarchy and descendant media items
    ↓
Lua discovers active [JR:SLOT_ID] Display Label buses
    ↓
Lua validates slots and resolves permanent PB bus
    ↓
Lua reads PB mute state
    ↓
Lua writes JSON to project extstate:
  ReaSetJamRoom / controls
    ↓
ReaSet.html polls every 500 ms
    ↓
Tracks tab renders dynamic labels, confirmed status, and diagnostics
```

### Lua bridge (as previously implemented)

Implemented file:

```text
Requirements/ReaSet_JamRoom_Stems.lua
```

It is a deferred/background ReaScript.

Important functions from the prior implementation:

```lua
json_escape(...)
json_bool(...)
json_number(...)
issue_to_json(...)
control_to_json(...)
publish(...)
get_position(...)
find_active_song_region(...)
track_name(...)
parse_jr_name(...)
find_track_by_name(...)
descendant_range(...)
item_overlaps_region(...)
has_descendant_overlap(...)
discover(...)
main_loop(...)
```

Key REAPER APIs used (these are the actual available primitives — genuinely useful to know regardless of design):

```lua
reaper.GetPlayState()
reaper.GetPlayPosition()
reaper.GetCursorPosition()
reaper.EnumProjectMarkers()
reaper.CountTracks()
reaper.GetTrack()
reaper.GetTrackName()
reaper.GetMediaTrackInfo_Value()
reaper.CountTrackMediaItems()
reaper.GetTrackMediaItem()
reaper.GetMediaItemInfo_Value()
reaper.SetProjExtState()
reaper.time_precise()
reaper.defer(...)
```

### Active-song determination (as previously designed)

The prior bridge:

* Uses play position while REAPER is playing or recording.
* Uses edit-cursor position otherwise.
* Ignores the temporary region named `ReaSet Loop`.
* Selects the longest containing non-loop region as the active top-level song region.

Known limitation acknowledged at the time: this breaks if a project contains a large enclosing region wrapping many songs. Worth considering whether a different design avoids this class of problem entirely.

### JSON payload contract (as previously designed)

```json
{
  "schema": 1,
  "heartbeat": 12345.678,
  "status": "ok",
  "song": {
    "id": "7",
    "name": "Example Song",
    "start": 120.0,
    "end": 340.5
  },
  "controls": [
    {
      "slot": "GTR1",
      "label": "Guitar 1 / Acoustic",
      "pb": "PB GTR 1",
      "muted": false
    }
  ],
  "issues": [
    {
      "type": "missing_pb",
      "severity": "error",
      "message": "Missing permanent PB bus: PB GTR 1",
      "track": "[JR:GTR1] Guitar 1 / Acoustic",
      "slot": "GTR1",
      "pb": "PB GTR 1"
    }
  ]
}
```

Status values used: `starting`, `ok`, `no_active_song`, `error`.

### Storage model

There is no database. This is a real constraint (see Explicitly Out of Scope), not a design preference from the prior attempt.

Storage was split between:

1. **REAPER project extstate** — Jam Room bridge payload (`ReaSetJamRoom/controls`); existing lyrics/chords/native loop integrations use other extstate namespaces; state is associated with the REAPER project.
2. **Browser localStorage** — ReaSet setlists, song/section overrides, theme/UI preferences, lyrics/chords settings, Live view settings, Canvas settings, MIDI mappings. Existing key patterns include:

```text
reaper_setlists_v9_<projectKey>
reaper_current_setlist_<projectKey>
reaset_song_overrides_<projectKey>
```

### Licensing and source constraints (genuine constraints, not design choices)

* The repository is GPL v3.
* Preserve licence and copyright notices.
* `Sortable.min.js` is third-party MIT-licensed vendored code and should not be modified.
* X-Raym-derived scripts are GPL v3 and should retain attribution.
* The upstream repository contains existing mojibake/encoding artefacts; avoid unrelated broad encoding cleanup.
* The existing lyrics script may rely on `reaper.ULT_GetMediaItemNote`, potentially requiring a compatible environment such as Ultraschall API.

---

## 4. Key Design Decisions Made By The Prior Attempt (with reasoning given at the time)

These are presented as decisions worth evaluating on their merits, not requirements.

1. **Dynamic labels, fixed audio semantics.** Reasoning given: a player's IEM mix depends on stable channel meaning regardless of the current song's label for that slot.
2. **Three-layer audio model** (raw stems → dynamic JR bus → permanent PB bus → hardware). Reasoning given: prevents per-song routing mistakes, protects fixed X32 semantics.
3. **Mute PB buses, not JR buses.** Reasoning given: mute state persists by semantic slot through song changes without a fragile separate state map.
4. **Song membership determined by actual media overlap with the region**, not by track existence alone. Reasoning given: an empty arrangement bus can't be reliably attributed to a particular song.
5. **Only active candidates are validated**; inactive buses are silently ignored, not flagged as errors. Reasoning given: they may belong to another song or be deliberately unused.
6. **Musician-facing UI shows only labels + audible/muted state.** Reasoning given: must work for non-technical users, shouldn't resemble a routing matrix.
7. **Tracks is a dedicated top-level tab**, not nested under transport or Show. Reasoning given: distinct rehearsal task, keeps Show uncluttered.
8. **No empty "Tempo & Key" placeholder tab** until that feature is actually designed. Reasoning given: tempo/transposition in a stem-based project is nontrivial and deserves real design attention.
9. **Click is a separate, explicit control**, excluded from "ALL BACKING ON." Reasoning given: click is an IEM-only rehearsal aid, not a normal backing instrument.
10. **Read-only status proven before any interactive mute control is built.** Reasoning given: mistakenly muting the wrong track or showing stale audio state during rehearsal/performance is a worse failure than a delayed feature.

---

## 5. State of the Prior Implementation (for context only — lives on a different branch, not this one)

A Milestone 1 read-only version was implemented and statically reviewed (by the AI assistant itself, not through live testing in REAPER). It included: the Tracks tab UI, the Lua discovery/validation/publish bridge, and diagnostics for common misconfigurations. It was never confirmed working in an actual REAPER session with real hardware.

Known unresolved issues at the time work stopped (in case any are informative — e.g. the stale-data problem is a general hazard worth designing around regardless of approach):

* Stale bridge detection was unreliable — cached data could appear current even after the Lua bridge stopped running, because heartbeat advancement wasn't actually checked.
* Duplicate permanent PB buses weren't detected, risking mute commands targeting the wrong track.
* Tag matching was case-sensitive and whitespace-sensitive in a way that could cause false negatives.
* A UI state bug left the Tracks tab looking active after switching to another tab.
* The "longest enclosing region" heuristic for identifying the active song would misbehave with certain project/region layouts.

## 6. Open Questions the Prior Attempt Left Unresolved

* Practical REAPER template setup/validation workflow (creating PB buses, correct output assignment, preventing accidental parallel sends) — never documented or automated.
* Tempo and key/transposition model — deliberately deferred, no implementation decisions made.
* Final interaction design details for mute controls (tap vs. toggle, exact visual states) — not settled.
* Final DAW workstation hardware — not selected (separate from this feature's design).
* Deployment/recovery procedure for a non-technical operator — not documented.
* No live acceptance test had been run against real REAPER + X32 hardware.
