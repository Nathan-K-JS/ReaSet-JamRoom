# X32 remote control — research and implementation handoff

> **Active JamRoom PC - mandatory workflow (27 September 2026):** this
> installation is connected to the X32 and live REAPER library. Preserve all
> live projects, media, recordings, configuration and mixer state. Development
> tests must use a separate isolated dummy setup, never the live REAPER instance.
> Follow [the live-system workflow](LIVE_JAMROOM_WORKFLOW.md) before using any commands below.
> Earlier workstation results are historical; operator setup/update instructions
> are not authorization to change the live rig during development.

Date: 27 September 2026 (Australia/Brisbane)
Status: ReaSet integration remains planned; separate, explicitly authorized
hardware inspection and bounded capability probes have since run on the room PC.
Repository: Nathan-K-JS/ReaSet-JamRoom
Planning branch: feature/jamroom-claude
Reviewed baseline: ee51aacd5b76aa893c32a42b16de5d4bf946f6b9 (v3.21)

## Purpose and decisions from the conversation

Nathan wants to extend the existing ReaSet jam-room project so he can inspect
the X32 Rack setup and eventually change routing, channel names, effects and
bus configuration. Saved IEM settings for different musicians or band setups
are a key use case.

The planning conversation took place in ChatGPT on Nathan's phone. Most previous
implementation work used VS Code/Codex on a separate workstation. Development
now takes place on the active JamRoom PC connected to the X32 and live REAPER
library. The v3.21 checkout and served browser deployment have been inspected.
No X32 bridge, isolated test environment or library migration has been installed
by this documentation work. Subsequent inspection verified direct OSC control at
192.168.68.56:10023, X32RACK-0E-2F-85, firmware 4.13. Standalone probe source is in
the separate `C:\JamRoomDev\x32-capability-proof` worktree; evidence is under
`Documents\JamRoom Inspections`. These probes are not deployed ReaSet features.

The intended software arrangement is:

| Component | Role |
| --- | --- |
| REAPER | Playback, recording, track structure and DAW routing. |
| ReaSet browser interface | Song controls and proposed mixer inspection/control UI. |
| Existing ReaSet local Python service | Host a proposed X32 OSC component alongside the existing service features. |
| X32-Edit | Manual mixer setup, comparison and backup/recovery tool. |
| VS Code + Codex + Git | Development and testing tools, not rehearsal requirements. |

No Mixing Station, OSCII-bot, X32Reaper daemon, new cloud service or database is
required by the proposed architecture. They were researched as alternatives,
not selected dependencies. The Python service is already part of this project;
the X32 component is new work to be added to it. Any new Python package must be
justified during implementation, not assumed necessary now.

X32-Edit does not need to relay commands or remain running for direct OSC control.
The X32 component would need to run while using the new mixer controls.
Ordinary ReaSet playback must continue to work without that component.

This document records research and a basic direction. Detailed write behaviour,
preset scope and UI are proposals to resolve before implementing the relevant
stage, following the repository's plan-before-build workflow.

Firmware updates, factory resets and boot/service operations are outside scope.
Nathan explicitly excluded firmware work during hardware acceptance. Stereo,
FX and band/quartet workflows should use explicit parameter scopes with capture,
readback and restoration; a full scene recall is not interchangeable with a
scoped preset. Phantom testing needs an operator-confirmed unplugged socket.

## What the research establishes

### X32 access

Behringer documents Ethernet remote control and X32-Edit synchronisation in both
directions: Console to PC reads the desk; PC to Console writes the editor state.
USB audio and Ethernet control serve separate purposes. The mixer retains its
fixed hardware/DSP resources, including 16 mix buses and eight effects engines;
FX 1–4 can serve send/return or insert processing, while 5–8 are insert-only. [1]

The detailed OSC reference is unofficial: Patrick-Gilles Maillot expanded
Behringer's original protocol specification through investigation and working
implementations. The consulted edition is labelled 4.06–09, 17 March 2022, for
firmware 4.0 and later. Check the actual Rack firmware before using its tables. [2]

| Area | External capability | Evidence |
| --- | --- | --- |
| Channel identity | Read/write names, colours, icons and input source selection. | [3] |
| Channel processing | Read/write levels, mutes, pan, EQ, gate, dynamics, delay and inserts. | [3] |
| IEM sends | Read/write send levels, enables, pan and tap configuration, respecting paired controls. | [3] |
| Bus configuration | Read/write names, links, processing, master levels and output assignments. | [4], [5] |
| Routing | Read/write input banks, Card/USB, AES50, physical output patch and User routing. | [5] |
| Preamps | Read/write hardware gain and phantom power. | [2] |
| FX | Read/write algorithm, supported parameters, sources and insert/return settings. | [2] |
| Metering | Read signal/processing meters. | [2] |
| Saved state | Retrieve/apply scenes, snippets and selected parameter sets. | [6] |

OSC runs over UDP at the mixer IP, port 10023. Queries read current parameters;
writes set them. Change subscriptions require renewal: /xremote expires after
10 seconds and is documented for up to four active clients. UDP needs paced
requests, timeouts and reconciliation. Native updates do not replace an initial
snapshot or explicit read-back after writes. [2]

Examples of actual address families include /ch/01/config/name,
 /ch/01/mix/01/level, /config/buslink/1-2 and /config/userrout/in/01.
Do not treat these textual examples as ready-to-send packets; OSC types,
encoding and value conversions matter. [2], [3], [5]

Full digital configuration access does not identify physical instruments,
cables or external headphone-amplifier knob settings. Those require operator
confirmation. No connection to Nathan's actual mixer was made during research.

### REAPER access and its limits

Cockos documents ReaScript access to track identity, recording configuration,
FX and sends/hardware outputs. Relevant APIs include
GetSetMediaTrackInfo_String, GetMediaTrackInfo_Value,
GetTrackSendInfo_Value, SetTrackSendInfo_Value and CreateTrackSend.
These expose the DAW side of the proposed combined inspector; USB audio alone
does not make the X32's mixer state part of the REAPER project. [7]

REAPER's OSC control-surface interface has configurable message mappings.
It is not an automatic X32 configuration API. OscLocalMessageToHost targets
REAPER itself, not an arbitrary network destination. A native socket/helper or
external bridge is needed for direct mixer communication; the existing local
Python service is the proposed home for that work. [7], [8]

An exported X32 scene plus a saved RPP can support an initial offline comparison.
A scene is not a complete backup of every global preference, show and library;
Maillot documents separate state/show/library retrieval tools. [6]

### Alternatives investigated

- Mixing Station desktop offers HTTP/WebSocket and OSC APIs for mixer parameters,
  subscriptions and metering. Its API explorer reveals actual parameter coverage.
  It targets the majority of mixer parameters; full coverage of our routing/FX
  requirements would need checking. Its API is desktop-only. Not required here. [9]
- X32Reaper demonstrates two-way DAW/mixer integration, but its track/control
  mapping is not automatically suitable for this project's separate live inputs
  and backing returns. Not selected. [6]
- Cockos OSCII-bot can translate MIDI/OSC and send/receive UDP OSC. It would add
  another process and scripting layer. Not selected. [10]
- MIDI can trigger selected controls/recalls; many additional OSC-style commands
  can be carried in SysEx. Ethernet is the proposed route for inspection and
  continuous feedback. [2]

## Current project context to preserve

Read the current versions of these files before implementation:

- [Project context](../CLAUDE.md)
- [Jam Room architecture](JAMROOM_DESIGN.md)
- [Recording setup and live channel map](RECORDING_SETUP.md)
- [Playback and recording](PLAYBACK_AND_RECORDING.md)
- [Update procedure](UPDATING.md)
- [Local service](../tools/jamroom_importer_server.py)
- [Browser application](../ReaSet.html)

The current setup guide explicitly says ReaSet does not remotely configure or
rename the X32. Its USB recording map is intended configuration, not measured
mixer state.

The current live-input plan is:

| X32 channels | Intended labels |
| --- | --- |
| 1–4 | Vox 1–4 |
| 5 | Bass |
| 6 / 7 | Guitar 1 / Guitar 2 |
| 8 | Utility Mic |
| 9–10 | Drums EAD10 L/R |
| 11–12 | Keys L/R |
| 13–16 | Spare 1–4 |

Use this current repository map rather than older conversation maps.
Channels 17–32 are the backing/playback returns. Their detailed slot/output map
is in JAMROOM_DESIGN.md. The intended recording patch is inputs 1–16, but local
versus AES50 source sockets, expansion card and current Card routing remain
unverified.

Retain hardware monitoring on the X32. Mixer control must not introduce REAPER
software monitoring or change the low-latency live audio path. Distinguish:

- A physical input/preamp.
- An X32 processing channel.
- A USB channel in either direction.
- A REAPER track or hardware send.
- An X32 mix bus.
- A physical output socket.

Matching numbers do not prove these are connected. Trace the actual assignments.
Likewise, changing an X32 effect does not automatically reproduce that effect
in ReaSet's separately rendered MP3 export.

## Proposed architecture

Keep the existing REAPER web interface and Lua paths for DAW operations. Add a
separate X32 module to the local Python service, exposed to ReaSet through a
small HTTP API; use polling or a streaming interface after evaluating existing
server conventions. Ordinary browsers need a local bridge for this UDP protocol.

The X32 module should own:

- Mixer address, identity, firmware detection and connection health.
- Parameter queries, decoding, subscriptions and bounded request pacing.
- Confirmed current values with freshness information.
- Validated writes followed by read-back.
- Snapshot/preset persistence and explicit scope.

Use one service-to-mixer connection shared by ReaSet clients. Keep its work
independent of slow import jobs and audio analysis. Design what happens when
the existing importer service is stopped; its current stop action must not
silently become a mysterious mixer disconnect.

Prototype module/API names are implementation choices, not a fixed contract.
Preserve the single-file browser app, local operation, existing deployment
workflow and installation-relative paths. No React/Node build conversion.

The X32 remains authoritative for mixer settings and REAPER for DAW settings.
Do not silently synchronize every REAPER fader with an X32 fader: they can
control different parts of the audio path.

## Implementation stages and acceptance

### 0. Establish the actual jam-room environment

1. The active JamRoom PC is now the development host; the inspected checkout is
   v3.21 (`ee51aac`). Use local execution for hardware work. [11] Keep executable
   development in a separate checkout and obey the mandatory live workflow.
2. Identify the running REAPER instance, active project, deployed web files,
   installation checkout, Python service and mixer network address.
3. Use a separate development checkout/branch while retaining the working
   installation. Be explicit about which checkout deploys into which REAPER.
4. Before explicitly requested hardware changes, preserve the X32 scene and
   REAPER configuration without overwriting originals. Routine tests use an
   isolated REAPER instance with Dummy Audio and separate dummy projects. Never
   use a scratch tab in the performance instance or the live library for routing
   experiments. Any hardware experiment needs its own explicitly agreed scope.
5. Verify Ethernet control connectivity separately from USB audio.

CLAUDE.md and AGENTS.md now identify this checkout as the active JamRoom PC and
require `LIVE_JAMROOM_WORKFLOW.md`. Future checkouts must verify their environment.
Do not rebuild, migrate, save or otherwise change the live song library during
development or tests. An unchanged-original check after a test is not isolation.

### 1. Read-only connection and setup inspector

Start with identity/firmware and a small parameter query, then expand to the
required channels, routes, buses and FX. Compare selected results against
X32-Edit. Read the REAPER track/input/output configuration through existing
project conventions and present both sides with their source and timestamp.

Acceptance:
- Correct values after mixer edits made outside ReaSet.
- Clear offline/stale state after disconnect and accurate refresh on reconnect.
- No mixer writes during inspection.
- Representative end-to-end routes match the real room, with physical wiring
  identified separately from software observations.

### 2. Controlled editing

Begin with channel names and selected IEM send levels; then add bus setup,
processing, routing and FX as separate reviewable increments. Show proposed
changes, apply explicit target values and report confirmed versus failed writes.

Do not assume a multi-parameter change is atomic or covered by REAPER Undo.
Keep before-values and an operation record; after interruption re-query the
mixer before deciding what to retry or restore. Treat shared preamp gain,
phantom power and routing as explicit setup operations.

Acceptance: changed values match X32-Edit and actual intended audio behaviour;
an interrupted change is reported accurately rather than marked successful.

### 3. Musician and band presets

Define scope before coding. Initial proposal:

- Personal IEM preset: selected channel/FX-return sends and agreed bus settings.
- Band setup: several named IEM assignments plus explicitly selected settings.
- Full rig setup: separate operator action for routing, preamps, links and FX.

Keep shared gain, recording routes and room mix out of a personal preset unless
explicitly included. Store stable identities/targets, not just display names.
Decide how a person's preset maps to a different physical IEM bus pair.
A browser's last-selected preset is not proof the mixer still matches it.

Acceptance: individual recalls change only their declared scope, persist across
service restarts, and remain accurate after external mixer changes.

### 4. Room acceptance and delivery

Verify actual IEM/room destinations, click routing, stereo links, recording
inputs, FX returns, simultaneous X32-Edit use, reconnects and cold starts.
Check ordinary playback/recording still works with the mixer service offline.

Commit and push at natural checkpoints. Deliver through the normal
feature/jamroom-claude update channel after testing, following current repository
instructions; do not force-push over divergent work.

## Questions to resolve on the jam-room PC

- Installed mixer firmware, card model, IP and actual source/output patch.
- Current number of IEM mixes and their physical socket/bus-pair assignments.
- Exact personal preset scope: sends only, or also bus EQ/master level?
- Whether configuration editing belongs in an operator-only Setup area.
- Service startup/stop behaviour when mixer controls are in use.
- Where mixer snapshots/presets live; they should not be disposable import cache
  or solely device-local browser storage.

## Starting instruction for the next Codex session

Read CLAUDE.md and docs/X32_CONTROL_RESEARCH_AND_PLAN.md. We are now working
on the jam-room PC: verify the local environment before proceeding. Inspect
the actual deployment and propose the first read-only X32 connection/inspection
milestone. Preserve the working project and mixer configuration. The X32 feature
is not implemented yet; do not assume an endpoint or bridge already exists.

## Research references

Accessed 27 September 2026. Documentation research, not hardware acceptance.

1. [Behringer X32 Rack user manual — manufacturer document, distributor-hosted](https://warehousesound.com/r/behringerX32RACKmanual.pdf).
   Remote control §5.12, routing, FX and MIDI sections. Older manual: use the
   firmware-specific protocol reference for newer routing features.
2. [Patrick-Gilles Maillot — unofficial X32/M32 OSC reference](https://x32ram.com/wp-content/uploads/download-files/X32-OSC.pdf).
   Transport, queries/subscriptions, User routing, preamps, FX, meters, MIDI SysEx.
3. [Author's channel parameter implementation](https://github.com/pmaillot/X32-Behringer/blob/master/X32Channel.h).
4. [Author's bus parameter implementation](https://github.com/pmaillot/X32-Behringer/blob/master/X32Bus.h).
5. [Author's configuration/routing implementation](https://github.com/pmaillot/X32-Behringer/blob/master/X32CfgMain.h).
6. [Author's X32 tools and descriptions](https://sites.google.com/site/patrickmaillot/x32).
   X32Reaper, scene/show/library retrieval, DeskSave/DeskRestore. Check licensing
   before reusing code; availability does not imply compatible reuse permission.
7. [Cockos ReaScript API reference](https://www.reaper.fm/sdk/reascript/reascripthelp.html).
8. [Cockos REAPER OSC documentation](https://www.reaper.fm/sdk/osc/osc.php).
9. [Mixing Station API documentation](https://mixingstation.app/ms-docs/use-cases/apis/).
10. [Cockos OSCII-bot](https://www.cockos.com/oscii-bot/).
11. [OpenAI Codex IDE documentation](https://learn.chatgpt.com/docs/codex/ide)
    and [native Windows execution](https://learn.chatgpt.com/docs/windows/windows-sandbox).
