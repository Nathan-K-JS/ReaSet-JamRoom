# Updating an existing install

For a machine that already works. Setting one up from scratch is
[FRESH_INSTALL.md](FRESH_INSTALL.md) — you never need to redo that.

## The whole procedure

1. Double-click **`JamRoom Update.bat`**.
2. Do whatever it tells you at the end.

That's it. It pulls the new version, redeploys `ReaSet.html`, updates yt-dlp,
and then prints a checklist of what actually needs restarting based on which
files changed — so you neither restart everything for a typo fix nor forget the
restart that matters.

## Delete nothing

**There is nothing to delete, ever.** `git pull` overwrites the files that
changed and leaves everything else alone. Specifically these are never touched
by an update, and deleting any of them causes real damage:

| Never delete | Why |
|---|---|
| `tools\jamroom_import.config.json` | your Fadr API key |
| `imports\` | the stem audio your REAPER project plays — deleting silences imported songs |
| your `.RPP` project | your whole rig |
| browser data on the tablets | setlists and MIDI mappings live in the browser, not the project |

A "clean re-install" is never the answer here, and would cost you the key, the
songs and the setlists.

## Why some things need restarting

This is the part that bites if you guess, so the update script works it out for
you. The rules it applies:

| What changed | What must restart | Why |
|---|---|---|
| `ReaSet.html`, `Sortable.min.js` | **Refresh browsers: Ctrl+F5** | The page is served from REAPER's web folder. A plain refresh can serve the cached old copy |
| Background scripts — `ReaSet_JamRoom.lua`, `ReaSet_NativeLoop.lua`, the two X-Raym scripts | **Restart REAPER** | These run continuously. REAPER loaded the code into memory when the script started, so a running script keeps using the OLD version no matter what is on disk |
| Anything in `tools\` (importer server, its page, the apply script) | **Restart the importer** — close its window and run `JamRoom Importer.bat` again | The server is a running program holding the old code |
| `ReaSet_JamRoom_BuildBuses.lua` | Nothing | One-shot; re-run it by hand only if you want the newer behaviour on a project |
| Docs, README | Nothing | |

**Why restarting REAPER is the way to reload background scripts:** there is no
tidy "reload" for a running ReaScript. Re-running its action while it is live
makes REAPER pop its *ReaScript task control* dialog, and a modal dialog freezes
REAPER — including the importer's link to it. Restarting REAPER is clean, and if
you set the startup action during install, all four scripts come back
automatically with the new code.

## Verifying an update landed

- ReaSet: the page loads and the **TRACKS** tab shows your groups (not "bridge
  is not running").
- Background scripts: `http://localhost:8080/_/GET/EXTSTATE/ReaSetJR/heartbeat`
  shows a number that changes when you reload it.
- Importer: its four preflight checks are green.

## If `git pull` fails

The update stops and changes nothing, so your rig keeps working. The usual cause
is a file in `C:\JamRoom` having been edited by hand. Either undo that edit, or
from a PowerShell window in `C:\JamRoom`:

```
git stash
```

…which sets your local edits aside so the update can proceed. Never delete the
folder and re-clone — you would lose `imports\` and your Fadr key with it.

## Before a rehearsal

Update *after* a rehearsal rather than an hour before one. If an update ever
misbehaves, this puts you back on the previous version:

```
git log --oneline -5
git checkout <the-previous-hash>
```

then restart REAPER and the importer.
