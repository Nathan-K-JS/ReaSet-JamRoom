# Jam Room — Operator Setup Guide

This guide is for the person who prepares REAPER projects (the operator).
Musicians never need any of this: they just open ReaSet on the tablet, pick a
song, and use the **TRACKS** tab to see and mute/unmute backing parts by name.

For the technical design, see `JAMROOM_DESIGN.md`.

---

## 1. One-time installation

1. **REAPER web interface** (once per PC): Options → Preferences → Control/OSC/web
   → Add → *Web browser interface*. Default port 8080. Copy `ReaSet.html` and
   `Sortable.min.js` into REAPER's web root folder
   (`%APPDATA%\REAPER\reaper_www_root`). Tablets browse to
   `http://<pc-name-or-ip>:8080/ReaSet.html`.
2. **The Jam Room bridge** (once per PC):
   - Actions → Show action list → *Load ReaScript…* →
     `Requirements/ReaSet_JamRoom.lua`.
   - Recommended: add it to **Options → Startup actions** so it always runs.
     (If it isn't running, the Tracks tab says so and shows nothing — it never
     guesses.)

## 2. Project template — the 10 permanent PB buses

Create these ten tracks once per project (a saved project template is the easy
way). Each is a **folder track**, never contains media itself, has its
**hardware output** set to the channels below, and **master/parent send OFF**
(routing dialog → untick "Master send"; then add the hardware output).

| PB bus (track name) | REAPER hardware outs | X32 return channels | Format |
| ------------------- | -------------------- | ------------------- | ------ |
| `PB DRUMS`    | 1–2   | 17–18 | stereo |
| `PB PERC/FX`  | 3     | 19    | mono   |
| `PB BASS`     | 4     | 20    | mono   |
| `PB GTR 1`    | 5–6   | 21–22 | stereo |
| `PB GTR 2`    | 7–8   | 23–24 | stereo |
| `PB KEYS`     | 9–10  | 25–26 | stereo |
| `PB BVs`      | 11–12 | 27–28 | stereo |
| `PB LEAD VOX` | 13    | 29    | mono   |
| `PB CLICK`    | 14    | 30    | mono — keep out of room speakers on the X32; route to IEM mixes only |
| `PB EXTRA`    | 15–16 | 31–32 | stereo |

Names are matched ignoring case and surrounding spaces, but keep them exactly
as above for sanity. Never create two tracks with the same PB name — the
Tracks tab will disable those controls and report it.

## 3. Adding a song

1. Create the song's **region** (top-level, not nested inside another region).
   This is how ReaSet discovers songs — no change from before.
2. Import the song's stems.
3. For each instrument group, make a **folder track named**:

   ```
   [JR:SLOT_ID] Whatever label the musicians should see
   ```

   e.g. `[JR:GTR1] Guitar 1 / Acoustic` for one song and `[JR:GTR1] Rhythm
   Guitar` for another — same slot, different label per song. Valid slot IDs:
   `DRUMS, PERC_FX, BASS, GTR1, GTR2, KEYS, BVS, LEAD_VOX, CLICK, EXTRA`.
4. Put the stems **inside** that `[JR:...]` folder.
5. Drag the whole `[JR:...]` folder **inside the matching PB folder**
   (`[JR:GTR1] ...` goes under `PB GTR 1`). This is what actually routes the
   audio — the Tracks tab checks it and reports a mismatch if you forget.
6. Make sure the stems' media items sit within the song's region. A `[JR:...]`
   bus only appears for songs where at least one of its items overlaps the
   region; one bus can serve several songs (e.g. one `[JR:DRUMS] Drums` with
   items under every song).

Rules per song: at most one active `[JR:...]` bus per slot. Slots you don't
use simply don't appear on the tablet.

## 4. How the Tracks tab behaves (what musicians see)

- Only the current song's groups, labelled as you named them, in fixed slot
  order, each showing **AUDIBLE** or **MUTED** — always REAPER's real state.
- Tap a row to mute/unmute. **ALL BACKING ON** restores every group except the
  click. The click is its own control in a separate section.
- Muting works on the PB bus, so it sticks across songs by slot: mute GTR1 in
  one song and the next song's GTR1 group is muted too, whatever it's called.
- If the bridge script isn't running, the tab says so instead of showing
  anything stale.

## 5. Troubleshooting — the "Setup issues" panel

Collapsed at the bottom of the Tracks tab; musicians can ignore it.

| Message contains | Meaning / fix |
| ---------------- | ------------- |
| *bridge is not running* | Run `ReaSet_JamRoom.lua` (see §1), or add to startup actions. |
| *looks like a JR tag but could not be parsed* | Fix the track name to `[JR:SLOT_ID] Label`. |
| *Unknown slot ID* | Use one of the ten valid slot IDs. |
| *Missing display label* | Add a label after the `]`. |
| *claimed by multiple active buses* | Two `[JR:same-slot]` buses have items in the same song; remove/move one. Neither is shown until fixed. |
| *Missing permanent PB bus* | Create the PB track (see §2). |
| *Duplicate permanent PB bus* | Two tracks share a PB name; remove one. |
| *is not inside the … folder* | Drag the `[JR:...]` folder under its PB folder. |
| Row shows *UNAVAILABLE* | The PB track vanished while the tab was open — check the project. |

## 6. Test/demo project

`Requirements/ReaSet_JamRoom_TestProject.lua` builds a complete working
example (plus four deliberate mistakes so you can see the diagnostics) in an
**empty project tab**: File → New project tab, run the script, run the bridge,
open the Tracks tab. One Undo removes everything.
