# Mandatory workflow on the active JamRoom PC

Effective 27 September 2026. This records Nathan's explicit working constraint.
It takes precedence over older development, setup, release and test instructions
in this repository. It describes this installation; future checkouts must verify
their own environment rather than assume they are a test machine.

## Current environment

- `C:\JamRoom` is the working installation on the active JamRoom PC, connected
  to the X32 and the live REAPER library. Development now happens on this PC.
- The inspected baseline is v3.21, commit `ee51aac`, on
  `feature/jamroom-claude`. The deployed and HTTP-served ReaSet HTML matched it.
- Live REAPER serves port **8080**; the live Python importer serves **8765**.
  Neither is a test endpoint. Other loopback addresses do not provide isolation.
- REAPER's configuration identifies the library at
  `C:\Users\natha\OneDrive\Documents\Jam room files\Full song library.rpp`.
  Do not open, save, reload or switch the live project to verify this path.
- X32 USB audio connectivity does not establish Ethernet control connectivity.
  Mixer IP, firmware and actual routing still need separate read-only inspection.
  The proposed X32 control bridge is not implemented.

These are inspection facts, not instructions to reinstall or reconfigure the rig.
Earlier reports from the separate workstation remain historical evidence. Their
test counts, screenshots and artifact paths do not prove acceptance on this PC.

## Preserve the live system

Development, documentation and testing tasks do not authorize changing the live
system. Do not save, migrate, rebuild, import into, convert, repair, rename,
delete or otherwise edit the live library or its media. Do not operate live
transport, change project tabs, arm tracks, record, render, change routing or
launch actions in the performance REAPER instance to run a test.

Preserve recordings and their journals/recovery data, including `.RPP.recordings`
storage, exported recordings and source takes. Preserve all of `imports/`,
including source caches, queue journals, `.updates/`, `.listening/`, model caches
and runtime state. These are not a disposable development directory. Also
preserve local importer configuration/credentials, REAPER settings and action
registrations, deployed web files, and browser setlists/preferences.

Leave the X32's names, levels, mutes, IEM mixes, buses, routing, preamps, phantom
power, effects and scenes unchanged. Do not send mixer writes, recall scenes or
use PC-to-console synchronization during inspection. An explicit read-only mixer
inspection task may query it without changing audio configuration.

Saving a project first, taking a backup, muting a scratch master, promising Undo,
or restoring state afterward does not make a live-system test acceptable.

## Separate development and test setup

1. Make executable changes in a separate checkout/worktree and development
   branch outside `C:\JamRoom`. Never use Git cleanup/reset or a reinstall to
   turn this working installation into a sandbox. Documentation-only changes
   in the installation are permitted.
2. Use a separate Python virtual environment and install test dependencies there.
   Do not run setup, dependency-repair or updater scripts against the live runtime.
   At initial inspection, the live Python had neither `lupa` nor `playwright`;
   that is a development setup task, not a reason to modify live Python.
3. Give tests their own configuration, job/cache roots, journals, recordings,
   exports and browser profile. Use synthetic media and fixtures by default.
   When representative data is needed, use separately prepared copies whose
   writable paths and project identities cannot resolve to live storage. Never
   move originals or let test cleanup traverse live files, symlinks or junctions.
4. Native integration tests require a separate REAPER instance with its own
   resource/configuration directory, test web root and test action registrations.
   Use Dummy Audio, no X32 device/hardware outputs, and only dummy projects. A new
   tab in the performance instance is **not** a separate test setup.
5. Run a separate test importer and REAPER web interface on verified unused ports
   distinct from 8080/8765. Point the test browser, Lua bridges and helpers only
   at those endpoints. Verify process identity, project identity and storage
   paths before any command that can change state.
6. Inspect each test harness before execution. Existing `tools/verify_*.py`,
   REAPER test-project builders and browser tests are not automatically safe:
   they may use fixed ports, the default REAPER executable/resource path, live
   configuration, the last-saved project or production `imports/` paths. A
   command-line REAPER launch may forward work to the already-running instance.
   If full isolation is not supported, adapt the harness in development first;
   do not try it against the live instance to find out.
7. Run offline/unit/browser tests only after verifying their files and network
   targets are isolated. Run native verifiers sequentially in the test instance.
   Keep evidence outside the live installation and close only test-owned
   processes. If isolation is uncertain, report the specific blocked check and
   continue safe offline work; never fall back to the live library.

The previous guides' `python tools/verify_...` commands describe test coverage,
not commands approved for execution against this PC's default endpoints. No
isolated native test environment or isolation support in those scripts is
claimed to have been established by this documentation change.

## Hardware acceptance and live delivery

Routine development tests use the dummy setup. A hardware acceptance task needs
an explicit user request covering the intended live interaction, a separate test
project/setup and an agreed audio path. It must not use or modify the live song
library. Prepare the concrete test and recovery plan before any requested mixer
write or audio-device change; preserve the existing configuration and recordings.
Having the X32 connected is not authorization to test it by changing settings.

Committing/pushing source is distinct from deploying it. Deliver tested releases
through `feature/jamroom-claude` using the established fast-forward-only process.
Do not run `JamRoom Update.bat`, `JamRoom Setup.bat`, deployment/recovery helpers,
restart live REAPER/importer, change live dependencies or refresh performance
clients as a development test. Perform live deployment only when explicitly
requested for that scope; keep library migrations separate and explicit too.

Fresh-install and operator guides remain useful for their named tasks. They are
not instructions to rebuild this existing installation or exercise its controls
during development. Historical release checks remain historical, even where
their text says “live”, “this workstation” or “original project unchanged”.
