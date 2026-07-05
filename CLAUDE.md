# Project Context: ReaSet — Jam Room Feature

Read this file at the start of every session. It contains durable facts about this
project so they don't need to be re-explained in every prompt.

## What this repo is

**ReaSet** is an existing, working, open-source browser-based control surface for the
**REAPER** DAW. This repo is a fork/customisation of it. We are adding a new feature
to it — we are not building a new app from scratch.

Current branch: `feature/jamroom-claude` — a clean branch off `main`, created
specifically to design and build this feature without inheriting a prior AI-assisted
attempt's implementation (which lives untouched on `feature/jamroom-stem-controls`
and should not be merged, referenced as required behavior, or copied from).

## Hard constraints — these are real, not stylistic choices

- **Single-file browser app.** `ReaSet.html` is HTML/CSS/vanilla JavaScript. No React,
  Vue, Angular, TypeScript, Node build system, or package manager is in use here.
  Don't introduce one without discussing it first — it would be a significant
  departure from the existing codebase's conventions.
- **No backend server, no database.** The browser talks to REAPER exclusively through
  REAPER's built-in Web Interface JS globals (`wwr_req`, `wwr_req_recur`,
  `wwr_onreply`, `wwr_start`). This is a platform limitation of REAPER's web
  interface, not a design preference — there is no REST API alternative available.
- **Lua ↔ browser communication** happens via REAPER's project extstate (a simple
  key/value store scoped to the project file), polled from the browser. This is
  effectively the only two-way channel available.
- **Hardware:** Windows PC running REAPER, Behringer X32 Rack over USB (32 physical
  channels). Convention so far: channels 1–16 = live inputs, 17–32 = REAPER playback
  returns. Treat as a strong default; flag clearly if you think it should change.
- **Licensing:** repo is GPL v3. `Sortable.min.js` is vendored MIT code — do not
  modify it. X-Raym-derived Lua scripts are GPL v3 — preserve attribution. Don't do
  unrelated encoding/formatting cleanup on existing files (repo has some legacy
  mojibake — leave it alone unless it's directly in your way).
- **Files that should stay untouched unless the task specifically requires it:**
  `Sortable.min.js`, `LICENSE`, `Requirements/ReaSet_NativeLoop.lua`, the two
  X-Raym scripts in `Requirements/`. `main.js` isn't in this repo at all — REAPER
  provides it at deployment time.
- **No cloud services, external databases, CDNs beyond what's already in use, or
  internet dependency.** This runs entirely on a local network.

## Existing features that must keep working

Setlist management, REAPER region-based song discovery, transport controls (play/
pause/stop/cue/seek), song chaining/looping/auto-stop, Lyrics view, Chords view, Live
view, Canvas view, MIDI mappings, and all existing browser localStorage-based
persistence. Don't redesign these — the new feature needs to coexist alongside them.

## The feature being built: "Jam Room" backing-track control

Musicians rehearsing need to see and (eventually) mute/unmute backing-track instrument
groups per song, from a tablet, using plain song-specific labels — without knowing
anything about REAPER routing, bus names, or X32 channel numbers.

Full problem context, requirements, and constraints: this will be provided directly at
the start of the design conversation.

**Reference material:** `docs/PRIOR_ATTEMPT_REFERENCE.md` describes a previous attempt
at this exact feature, built by a different AI coding assistant. It reached a
partially-implemented, never-live-tested state. **Treat it as reference material, not
a specification.** It explicitly separates genuine hard constraints from that
attempt's own design choices — read that framing before drawing on it. You are
expected to form your own view on architecture and are free to agree or disagree with
what's there.

## Working style expectations

- **Plan before you build.** For any non-trivial design step, write out your proposed
  approach and reasoning first and wait for explicit approval before writing or
  editing code. Don't implement speculatively.
- **Read before you assume.** Explore actual repo files (`ReaSet.html`, the Lua
  scripts in `Requirements/`, existing `docs/`) to understand real conventions rather
  than guessing at patterns.
- **Flag constraint vs. choice explicitly.** When you're about to do something a
  particular way, say whether that's because of a genuine constraint above or because
  it's your own design judgment — especially when it differs from
  `PRIOR_ATTEMPT_REFERENCE.md`.
- **No stale/optimistic UI.** Any state shown to a musician must reflect confirmed
  REAPER state, not a guess or cached value — this project is used live during
  rehearsal, and wrong displayed state is a worse failure than a slower UI.
- **Commit at natural checkpoints** (plan approved, data model in place, UI built,
  bridge built, etc.) rather than one large commit at the end, so we can roll back
  cleanly if a step goes wrong.
- **Be direct about tradeoffs and risks**, including anything you're unsure REAPER's
  API can actually support — don't paper over uncertainty.
