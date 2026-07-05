# Jam Room "Tracks" Feature — Design & Verified Facts

Status: design approved; M0 live verification complete (2026-07-05).
This document is the working architecture reference for the Jam Room feature
built on branch `feature/jamroom-claude`. For the prior attempt's design (a
different architecture, never live-tested) see `PRIOR_ATTEMPT_REFERENCE.md`.

## Architecture

Split of responsibilities — **Lua discovers structure; REAPER's native web API
carries live state and commands**:

```
REAPER project
│
├── Permanent PB buses (10, fixed hardware outputs 1–16)   ← mute targets
├── Per-song [JR:SLOT] Label folder buses + stems          ← discovered by Lua
│
├── Lua bridge (Requirements/ReaSet_JamRoom.lua, defer loop)
│     scans tracks/items → per-song controls + setup issues
│     publishes chunked JSON to NON-PERSISTENT global extstate (ReaSetJR/*)
│     bumps heartbeat ~1/s
│
└── ReaSet.html
      recurring poll: GET/EXTSTATE ReaSetJR/heartbeat + ReaSetJR/meta (500 ms)
      burst fetch:    ReaSetJR/d0..dN when meta generation changes
      recurring poll: TRACK (500 ms) → per-track name + mute flag
      commands:       SET/TRACK/<idx>/MUTE/<0|1>   (Milestone 2)
      join: active song (browser's own logic) × Lua controls × TRACK mutes
```

Key properties:

- **No stale state possible.** All Jam Room extstate is global + non-persistent
  (`SetExtState(..., false)`) — it cannot survive a REAPER restart. The browser
  additionally requires the heartbeat to advance; if it stalls ~3 s the panel
  shows "bridge offline". Mute state shown to musicians comes only from the
  live TRACK poll, never from a cache and never optimistically.
- **No active-song heuristic in Lua.** Lua publishes controls for all song
  regions keyed by region ID; the browser picks using its existing
  displayList/currentPos logic.
- **Mute source of truth is the PB bus mute in REAPER.** No browser-side or
  Lua-side mute maps anywhere.

## M0 — facts verified against a live REAPER (Windows, web interface port 8080)

1. `TRACK` reply: `TRACK \t idx \t name \t flags \t vol \t pan \t ...`.
   Master = idx 0, flags 512. **Mute bit = flags & 8** (verified by toggling).
   No `TRACK_LIST`/`_END` framing markers.
2. `SET/TRACK/<idx>/MUTE/<0|1>` works; `SET/TRACK/8/MUTE/1;TRACK/8` batches a
   command with a confirmed read-back in one request.
3. Global extstate round-trips through `GET/EXTSTATE`; raw JSON values survive
   verbatim. Values must be single-line (reply framing is `\t`/`\n` delimited).
4. **~1 KB per-value limit** observed through the HTTP path (1,500-char value
   truncated to 998). Multi-key batched GET replies are NOT capped overall
   (1.8 KB across two keys returned fully). Hence the chunked payload below.
5. Region-ID equivalence CONFIRMED at M1: web `REGION` id field == Lua
   `EnumProjectMarkers` markrgnindexnumber. (The browser joins the active song
   by time range anyway, so nothing depends on this.)
6. **Reply escaping:** the web interface escapes EXTSTATE values in replies:
   `\` → `\\`, TAB → `\t`, LF → `\n`; quotes pass through. The browser must
   unescape (`jrUnescape()` in ReaSet.html) or JSON payloads containing
   escaped quotes fail to parse. Found via live M1 test.
7. TRACK flags: bit 1 = folder (PB folder bus showed 137 = 128+8+1 muted).

## Extstate contract (namespace `ReaSetJR`, all non-persistent global)

| Key         | Written by | Content |
| ----------- | ---------- | ------- |
| `heartbeat` | Lua, ~1/s  | incrementing integer |
| `meta`      | Lua, on change | `<generation>:<chunkCount>` |
| `d0`..`dN`  | Lua, on change | JSON payload split into ≤800-char chunks; each chunk prefixed `<generation>:` |

Write order on change: chunks first, `meta` last. The browser fetches chunks
after seeing a new generation in `meta`; if any chunk's generation prefix
mismatches, it refetches (a rescan raced the read). Payload changes only when
project structure changes (tracked via `reaper.GetProjectStateChangeCount()`),
so bursts are rare.

Assembled payload JSON:

```json
{ "schema": 1,
  "songs": { "<regionId>": {
      "name": "Song A",
      "controls": [ {"slot":"GTR1","order":4,"label":"Guitar 1 / Acoustic",
                     "pb":"PB GTR 1","click":false} ],
      "issues":  [ {"type":"duplicate_slot","msg":"..."} ] } },
  "globalIssues": [ {"type":"missing_pb","msg":"Missing permanent PB bus: PB KEYS"} ] }
```

Mute state is deliberately absent — it comes from the TRACK poll.

## Slot table (single source of truth: table in ReaSet_JamRoom.lua)

| Slot | PB bus | REAPER outs | X32 returns | Format |
| ---- | ------ | ----------- | ----------- | ------ |
| DRUMS | PB DRUMS | 1–2 | 17–18 | stereo |
| PERC_FX | PB PERC/FX | 3 | 19 | mono |
| BASS | PB BASS | 4 | 20 | mono |
| GTR1 | PB GTR 1 | 5–6 | 21–22 | stereo |
| GTR2 | PB GTR 2 | 7–8 | 23–24 | stereo |
| KEYS | PB KEYS | 9–10 | 25–26 | stereo |
| BVS | PB BVs | 11–12 | 27–28 | stereo |
| LEAD_VOX | PB LEAD VOX | 13 | 29 | mono |
| CLICK | PB CLICK | 14 | 30 | mono, IEM-only |
| EXTRA | PB EXTRA | 15–16 | 31–32 | stereo |

Encodes the physical X32 wiring (channels 1–16 live inputs, 17–32 playback
returns). Fixed for v1.

## Routing convention

Each `[JR:SLOT] Label` bus must be a **child of its PB folder bus** (REAPER
folders route children automatically; audio cannot bypass the PB mute).
Discovery matches by name, but the bridge validates descent and reports
`routing_mismatch` when the tag and the actual audio path disagree.

Tag parsing: `^\s*\[\s*JR\s*:\s*([A-Za-z0-9_]+)\s*\]\s*(.*)$`, slot ID
case-insensitive → uppercase, label trimmed/preserved, empty label = issue.

A JR bus is active for a song iff ≥1 descendant media item overlaps the song
region. Inactive JR buses are ignored, not errors. Validation performed:
malformed/labelless tag, unknown slot, duplicate active slot claim per song,
missing PB bus, duplicate PB bus names, routing mismatch.

## Milestones

- **M0** ✅ live web-API verification (this document).
- **M1** ✅ Lua bridge + read-only Tracks tab, live-verified end-to-end
  (real bridge in REAPER + headless browser against the deployed page):
  discovery/validation payload exactly as designed for a 20-track test
  project (built by `Requirements/ReaSet_JamRoom_TestProject.lua`), live
  mute join, per-song labels switching on the same slot with mute state
  persisting across songs, offline detection on heartbeat stall, all four
  deliberate misconfigurations reported, zero JS console errors.
- **M2** ✅ Interactive: tap-to-toggle mute (confirmed-state display only,
  pending dot until the TRACK poll confirms), `ALL BACKING ON` (never touches
  PB CLICK), separate CLICK control. Live-verified: in-page tap muted
  PB DRUMS in REAPER; ALL BACKING ON restored it with the click left muted.
- **M3** ✅ Operator guide `docs/JAMROOM_SETUP.md`.

Remaining before rehearsal use: a human pass on a real tablet (touch feel,
sizes), the real project template with actual stems, and X32-side routing
(fixed channel plan above; nothing in this feature talks to the X32).
