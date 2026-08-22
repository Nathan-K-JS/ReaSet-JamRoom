# ReaSet + Jam Room — install from scratch

Everything needed to take a PC with nothing on it to a working jam room rig.
Follow the stages in order: later stages genuinely depend on earlier ones.

Once this is done, adding songs is [JAMROOM_IMPORT.md](JAMROOM_IMPORT.md), and
day-to-day operating is [JAMROOM_SETUP.md](JAMROOM_SETUP.md).

---

## Stage 1 — REAPER and its extension

1. **Install REAPER** (v6 or newer; developed against 7.75).

2. **Install the SWS extension** from <https://www.sws-extension.org>, then
   restart REAPER. This is the **only** extension needed, and it is not
   optional: the lyrics and chords views read item notes through SWS's `ULT_`
   API, and the song importer writes them the same way. Without SWS, lyrics
   and chords silently never appear.
   *(Older README text suggests "Ultraschall API" — that is wrong. Install SWS.)*

3. **Enable the web interface**: Options → Preferences → Control/OSC/web →
   **Add** → *Web browser interface* → port **8080**.
   **Write down the web root path shown in that dialog** — it varies between
   installs, and stage 2 needs it.

4. **Audio device**: Preferences → Audio → Device. Enable at least **16 output
   channels** on the X32's USB interface. The playback buses route to outputs
   1–16; if fewer are enabled you cannot assign them in stage 4.

---

## Stage 2 — Get the files onto the PC

5. Install Git, then **close PowerShell and open a new window** (the PATH only
   updates in new windows — `git : the term 'git' is not recognized` means you
   skipped this):
   ```
   winget install --id Git.Git -e
   ```
6. In the **new** window:
   ```
   git clone -b feature/jamroom-claude https://github.com/Nathan-K-JS/ReaSet-JamRoom.git C:\JamRoom
   ```
   *No-Git alternative:* download the branch as a ZIP from GitHub and extract to
   `C:\JamRoom`. Everything works except `JamRoom Update.bat`.

7. Double-click **`C:\JamRoom\JamRoom Setup.bat`**. It installs Python, yt-dlp
   and ffmpeg, prepares the importer config, and copies `ReaSet.html` +
   `Sortable.min.js` into REAPER's web root. It prints which folder it used —
   **check that against the path from step 3.** If it says it *created* a new
   folder, it guessed; copy those two files into the real web root instead.

   > `main.js` is **not** copied and must not be — REAPER serves it itself.

---

## Stage 3 — Load the scripts into REAPER

8. Actions → Show action list → **ReaScript: Load…**, and load these five from
   `C:\JamRoom\Requirements\`:

   | Script | What it powers |
   |---|---|
   | `ReaSet_JamRoom.lua` | TRACKS tab — per-song backing-group mute controls |
   | `ReaSet_NativeLoop.lua` | REAPER-native looping (silently degrades to a JS timer if absent) |
   | `X-Raym_Convert Lyrics …lua` | Lyrics view |
   | `X-Raym_Convert Chords …lua` | Chords view |
   | `ReaSet_ChordsLyrics.lua` | Chord chart / lookahead views + lead-time slider |
   | `ReaSet_TempoKey.lua` | Per-song tempo (playrate) and key (transpose) controls |
   | `ReaSet_Startup.lua` | Starts all the background scripts in one go |
   | `ReaSet_JamRoom_BuildBuses.lua` | Builds the project's track layout (stage 4) |

   Loading only registers them. They are started in stage 5 — **the order
   matters**, because the two X-Raym scripts abort with a modal error box if the
   project has no `lyrics` / `chords` track, and a modal dialog freezes REAPER.

---

## Stage 4 — Build the project

9. Open (or create) the jam room project.

10. Actions → Show action list → run **`ReaSet_JamRoom_BuildBuses.lua`**
    (`C:\JamRoom\Requirements\`). It builds the whole layout in one undo step:

    | Track | Routing | X32 returns |
    |---|---|---|
    | `PB DRUMS` + `[JR:DRUMS] Drums` | out 1–2 stereo | 17–18 |
    | `PB PERC/FX` + `[JR:PERC_FX] Perc/FX` | out 3 mono | 19 |
    | `PB BASS` + `[JR:BASS] Bass` | out 4 mono | 20 |
    | `PB GTR 1` + `[JR:GTR1] Guitar 1` | out 5–6 stereo | 21–22 |
    | `PB GTR 2` + `[JR:GTR2] Guitar 2` | out 7–8 stereo | 23–24 |
    | `PB KEYS` + `[JR:KEYS] Keys` | out 9–10 stereo | 25–26 |
    | `PB BVs` + `[JR:BVS] Backing Vocals` | out 11–12 stereo | 27–28 |
    | `PB LEAD VOX` + `[JR:LEAD_VOX] Lead Vocals` | out 13 mono | 29 |
    | `PB CLICK` + `[JR:CLICK] Click` | out 14 mono | 30 |
    | `PB EXTRA` + `[JR:EXTRA] Extras` | out 15–16 stereo | 31–32 |

    …plus the **`lyrics`** and **`chords`** tracks the views need. Every PB bus
    is a folder with **master send off**, so it feeds only the X32.

    It is safe to re-run: anything already present is left untouched and
    reported, so it will never clobber routing you have adjusted by hand. It
    also tells you if your audio device has fewer than 16 outputs.

11. **Check the routing** in REAPER's routing matrix against your X32 before
    trusting it live — the script sets hardware outputs exactly as if you had
    added them by hand, so a mono bus takes the source's channel 1. On the X32,
    keep `PB CLICK` (channel 30) out of the room speakers; in-ear mixes only.

12. **Save the project**, and save it as a project template while you are at it
    (File → Project templates → Save as template). Saving matters for more than
    your work: ReaSet stamps a hidden ID into the project to keep setlists
    attached to it, and that ID only persists once the project has been saved.

> The `[JR:…]` sub-buses start empty, which is normal — a group only appears on
> the tablet for songs that actually have audio on it. The importer reuses these
> buses by name, and creates its own only when you give a stem a custom
> per-song name in the review screen.

---

## Stage 5 — Start the background scripts, and keep them started

13. Actions → Show action list → run **`ReaSet_Startup.lua`**. It starts all
    four background scripts and reports what it did in the ReaScript console.
    Running it again later is safe — it skips anything already running.

14. **Make it automatic**, or everything stops working after the next REAPER
    restart. Either:
    - Preferences → General → set `ReaSet_Startup.lua` as the startup action, or
    - copy `Requirements\ReaSet_Startup.lua` to
      `%APPDATA%\REAPER\Scripts\__startup.lua` — REAPER auto-runs a script with
      that exact name.

    REAPER's startup slot holds only **one** action, which is the whole reason
    `ReaSet_Startup.lua` exists.

---

## Stage 6 — Open ReaSet

15. On the PC: <http://localhost:8080/ReaSet.html>.
    On a tablet: `http://<pc-ip>:8080/ReaSet.html` (same network).

16. Sanity checks: the setlist lists your song regions; the **TRACKS** tab shows
    backing groups rather than "bridge is not running"; during playback the
    Lyrics and Chords views show text once those tracks have items.

17. Build your setlist. Setlists live in the **browser**, per device — configure
    on the tablet you will actually use, and back up with
    Data → Backup → Export Settings JSON.

---

## Stage 7 — The song importer

18. Get a **Fadr API key**: fadr.com (Plus subscription, $10/mo) → account page
    → API tab → *Create New API Key*.

19. Double-click **`JamRoom Importer.bat`**, paste the key into the page when it
    asks, and confirm all four preflight checks are green.

20. Import a song: [JAMROOM_IMPORT.md](JAMROOM_IMPORT.md).

---

## Things that surprise people

**MIDI Learn only works on the PC, not the tablet.** Browsers gate the Web MIDI
API behind a secure context, so it works at `http://localhost:8080` but is
blocked over `http://<ip>:8080`. There is no workaround short of browser flags.

**"MIDI Init" is ON by default** and sends a brief play→stop pulse to REAPER
every time you cue a song. If the transport twitches on song selection, that is
this setting — turn it off in the sidebar's Show Options.

**Setlists are per browser, per device.** They are not stored in the project.
Moving to a new tablet means exporting and importing the settings JSON.

**Modal dialogs in REAPER freeze everything**, including the importer's ability
to talk to REAPER. If an import reports no confirmation, look for a dialog
waiting for a click — including REAPER's own evaluation-licence nag on startup.

**Keep the `imports\` folder.** The stem audio lives there and the project
references it. To make a project self-contained, use REAPER's *Save project* with
"Copy all media into project directory".

---

## Quick verification checklist

| Check | Where |
|---|---|
| SWS installed | REAPER: Extensions menu exists |
| Web interface up | <http://localhost:8080/ReaSet.html> loads |
| Bridge running | TRACKS tab shows groups, not a warning |
| Native loop running | loop indicator appears when a song is set to loop |
| Lyrics/chords running | views show text during playback |
| Survives restart | restart REAPER, re-check the above without touching anything |
| Importer ready | `JamRoom Importer.bat` → four green checks |
