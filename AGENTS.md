# Mandatory live JamRoom workflow

Read `CLAUDE.md` and `docs/LIVE_JAMROOM_WORKFLOW.md` before doing work here.

This checkout is on the active JamRoom PC, connected to the X32 and the live
REAPER song library. It is not the former testing workstation.

- Preserve the live project, library media, recordings, importer state, browser
  data, REAPER configuration and X32 settings. Development/testing requests do
  not authorize changes to any of them.
- Run tests only with separate dummy data and isolated services. Native tests
  require a separate REAPER instance with its own resource/configuration folder,
  Dummy Audio and test projects. A scratch tab in live REAPER is not isolation.
- X32 firmware changes, factory resets and X32 boot/service operations are excluded.
  The user explicitly ruled out firmware work. Mixer workflow tests must use
  captured, bounded resources with readback and verified restoration; phantom
  tests require an operator-confirmed physically unplugged input.
- Audit test scripts before execution: localhost ports, command-line launches,
  action registration, paths and cleanup can still target the live installation.
  Do not run a verifier that cannot be directed entirely at the isolated setup.
- Standing release authorization (23 October 2026): once the requested
  requirements are complete and all required tests/checks pass for the release,
  commit and push the work, fast-forward the standard update branch, and deploy
  it to this PC without asking for another approval. Follow the release gate
  and safe deployment procedure in `docs/LIVE_JAMROOM_WORKFLOW.md`.
- Required service restarts and runtime dependency changes are authorized as
  part of a qualifying release. Preserve unsaved work and checkpoint importer
  jobs; never interrupt playback, recording, rendering or an unsafe import.
  Live library changes and hardware operations still require their own explicit
  scope. Tests remain isolated; deployment is not permission to test on the rig.
- Use a separate development checkout for executable changes. Documentation-only
  edits here are permitted. Never reset, clean or overwrite the live installation
  to prepare tests. Keep historical test evidence distinct from current acceptance.

The linked workflow is mandatory even when an older guide suggests using a
stopped live project, saving it before testing, or restoring it afterward.
