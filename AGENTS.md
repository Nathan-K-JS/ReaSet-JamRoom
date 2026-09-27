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
- X32 firmware changes, factory resets and boot/service operations are excluded.
  The user explicitly ruled out firmware work. Mixer workflow tests must use
  captured, bounded resources with readback and verified restoration; phantom
  tests require an operator-confirmed physically unplugged input.
- Audit test scripts before execution: localhost ports, command-line launches,
  action registration, paths and cleanup can still target the live installation.
  Do not run a verifier that cannot be directed entirely at the isolated setup.
- Do not deploy, update dependencies in the live runtime, restart live services,
  operate live transport or modify mixer settings as a side effect of development.
  Live deployment or hardware operations require an explicit user request for
  that scope; carry out already-authorized work without asking repeatedly.
- Use a separate development checkout for executable changes. Documentation-only
  edits here are permitted. Never reset, clean or overwrite the live installation
  to prepare tests. Keep historical test evidence distinct from current acceptance.

The linked workflow is mandatory even when an older guide suggests using a
stopped live project, saving it before testing, or restoring it afterward.
