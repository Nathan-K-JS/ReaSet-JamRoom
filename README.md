##### 🇬🇧 ENGLISH

## 📌 Table of Contents
- [💛 Support this project](#-support-this-project)
- [1) What is ReaSet?](#1-what-is-reaset)
- [2) Main features](#2-main-features)
- [3) Credits and acknowledgements](#3-credits-and-acknowledgements)
- [4) Requirements](#4-requirements)
- [5) Tools](#5-tools)
- [6) Installation](#6-installation)
- [7) Usage setup](#7-usage-setup)
- [8) Usage Manual](#8-interactive-usage-manual)
  - [Lyrics & Chords Track Naming](#lyrics--chords-track-naming)
  - [Display Filters](#display-filters)
  - [MIDI Learn](#-midi-learn)
  - [Region Name Command Reference](#region-name-command-reference)
- [9) Keyboard Shortcuts](#9-keyboard-shortcuts)
- [10) Quick troubleshooting](#10-quick-troubleshooting)

---

## 💛 Support this project
If this project helps you, you can support development here:

<a href="https://ko-fi.com/W7W81VLW05" target="_blank">
  <img src="https://storage.ko-fi.com/cdn/kofi3.png?v=6" alt="Buy Me a Coffee at ko-fi.com" height="36" style="border:0px;height:36px;" />
</a>

📜 [Changelog](./CHANGELOG.md) · 🗺️ [Roadmap](./ROADMAP.md)

---

## 1) What is ReaSet?
**ReaSet** is a web interface for **REAPER**, designed for live setlist management.

Project foundation:
- Inspired by **ReaSetlistManager** by `suckyble`.
- Extended with **lyrics and chords** display based on **X-Raym** scripts/logic.

Main goals:
- Organize and run songs (regions) during live shows.
- Control transport (play/stop/cue/next).
- Manage multiple setlists with local persistence.
- Display synced lyrics/chords from dedicated tracks.

---

## 2) Main features
- ✅ Setlist management (create/delete/switch).
- 🔀 Drag & drop song reordering.
- 🎯 Song states: active, queued, skipped, loop, chain.
- ⏯️ On-screen transport controls.
- 💾 JSON export/import.
- 🧠 Local persistence via `localStorage`, isolated per REAPER project.
- 🎤 Lyrics panel + 🎸 chords panel.
- 🎨 Visual customization (themes/fonts/sizes/chord color/display filters).
- 🗂️ Nested sub-regions with individual loop, skip, color and notes overrides.
- 🏷️ Inline command system — control behavior directly from REAPER region names.
- 🔢 Fractional loop counter badge (e.g. `2/4`) shown live on the active section.
- 🖥️ Live View with sub-region progress bar, next section indicator and loop counter.
- 🌗 Real-time display filters: brightness, contrast and saturation via sidebar sliders.
- 🎬🎧 Director/Player mode — read-only instances for musicians that can never send REAPER
  a command, with a shared setlist synced from the Director.

Main file:
- `ReaSet.html`

Included dependencies:
- `Sortable.min.js`
- Legacy Lua bridge scripts under `Legacy/` (optional/advanced — see [Requirements](#4-requirements))

---

## 3) Credits and acknowledgements
### Base project
- **suckyble / ReaSetlistManager**  
- https://github.com/suckyble/ReaSetlistManager

### Lyrics/chords integration
- **X-Raym / REAPER-ReaScripts**  
- https://github.com/X-Raym/REAPER-ReaScripts/tree/master/Web%20Interfaces
- Reference script:  
  `Convert Lyrics track items notes for the dedicated web browser interface.lua`

### Sorting library
- **SortableJS** (`Sortable.min.js`)

### AI-assisted development process
This project was iterated, debugged, and tested with:
- **Claude (cowork)**
- **Google (Antigravity)**

Final functional validation was performed in REAPER with real setlist usage tests.

> ⚖️ Legal note: keep and respect original licenses of reused components (e.g., GPL v3 where applicable).

---

## 4) Requirements
### Software
1. **REAPER** (v5+ recommended; latest preferred).
2. A web browser (desktop/tablet/mobile).
3. A REAPER project with regions (typically one region per song).

### Minimum files
- `ReaSet.html`
- `Sortable.min.js`
- `Reaset.lua` — **single unified companion script** (loop engine + lyrics + chords).

> **Legacy / advanced:** the three original scripts are still bundled under
> `Legacy/` (`ReaSet_NativeLoop.lua` and the two X-Raym Lyrics/Chords
> converters). You only need them if you prefer running the subsystems
> separately. For a normal setup, `Reaset.lua` replaces all three.
> Note that the legacy scripts require the **exact** track names `lyrics` / `chords` —
> prefix support (`*Lyrics`) exists only in `Reaset.lua`.

### Required tracks for lyrics/chords
- A track whose name is `lyrics` — feeds the 🎤 Lyrics panel.
- A track whose name is `chords` — feeds the 🎸 Chords panel.
- Each item must contain text in **Item Notes**.

Name matching is **case-insensitive** and tolerates prefixes/suffixes such as
`*Lyrics`, `#Chords` or `01 Lyrics`. Both tracks are **optional**.
See [Lyrics & Chords Track Naming](#lyrics--chords-track-naming) for the full rules.

### Script compatibility
Scripts use `reaper.ULT_GetMediaItemNote`.
- If your REAPER build does not recognize it, install a compatible scripting/API environment (e.g., Ultraschall API) or adapt note reading.

---

## 5) Tools
Optional standalone scripts under `Tools/`. Neither is required to run ReaSet
itself — the always-on setup is just `Reaset.lua` + `ReaSet.html` — these are
conveniences you reach for occasionally: one for authoring content, one for
diagnosing the lyrics/chords bridge when a panel stays empty.

### 🎤 Lyrics Tapper — `Tools/Lyrics_Tapper.lua`
A standalone REAPER/ReaImGui tool for **building** the `lyrics`/`chords`/`notes`
items ReaSet reads. Paste a block of text, press **ARM**, then tap along
(mouse or **Space**) as the song plays: each tap closes the previous line's
item and opens the next one at the current position, teleprompter-style.
For N lines, that's N taps to place all of them, plus **one more tap** to close
the last item and finish the take right there — no separate Stop needed for a
clean finish, though Stop is still available any time to end early.
It auto-detects the target track with the same flexible naming rules as
`Reaset.lua`, creates the track if missing, and filters out section headers
("Chorus", "Verse 2", "[Coro]", …) so they don't become lyric items.

- Requires the **ReaImGui** extension (separate from SWS).
- Load via Actions → ReaScript: Load… → `Tools/Lyrics_Tapper.lua` → Run.

### 🔍 ReaSet Diagnose — `Tools/ReaSet_Diagnose.lua`
A read-only, one-shot diagnostic report for the lyrics/chords bridge — reach
for it when the [in-app status message](#10-quick-troubleshooting) isn't
enough on its own. It prints every track with its normalised name and item
count, which track each bridge would pick, whether SWS is present, the cursor
position, and a per-item dump of the Notes field, pinpointing shadowed tracks
(two tracks matching the same keyword) and empty Notes immediately. It also
self-tests the lookup pipeline at a known-good position, so a badly
positioned playhead can never look like a broken bridge.

- Load via Actions → ReaScript: Load… → `Tools/ReaSet_Diagnose.lua` → Run.

---

## 6) Installation
### Step 1 — Copy web interface files
Copy to REAPER web folder (where `main.js` is located):
- `ReaSet.html`
- `Sortable.min.js`

#### Default paths (REAPER Resource Path)
> In REAPER: **Options > Show REAPER resource path in explorer/finder**.

**macOS**
- Resource Path: `~/Library/Application Support/REAPER/`
- Web root (typical): `~/Library/Application Support/REAPER/Plugins/reaper_www_root/`

**Windows**
- Resource Path: `%APPDATA%\REAPER\`
- Web root (typical): `%APPDATA%\REAPER\Plugins\reaper_www_root\`

**Linux**
- Resource Path: `~/.config/REAPER/`
- Web root (typical): `~/.config/REAPER/Plugins/reaper_www_root/`

> `main.js` is provided by REAPER Web Interface (not included in this project).

### Step 2 — Install the Lua script (one script only)
1. Open REAPER.
2. Go to **Actions > Show action list**.
3. Use **ReaScript: Load...** and load **`Reaset.lua`**.
4. Find **"Reaset"** in the action list and **Run** it once.
5. (Recommended) Add it to **Options > Preferences > General > Startup actions**
   (or an SWS *Global startup action*) so it launches with REAPER automatically.

> `Reaset.lua` is a single persistent background script that runs the native
> loop engine and the lyrics/chords bridges together. There is **no Action ID
> to paste** into `ReaSet.html` — the web interface auto-detects the script.
>
> Lyrics/chords tracks are optional: if a `lyrics` or `chords` track is missing,
> that panel simply stays idle and transport/loop control keeps working.

#### Default script paths
- **macOS:** `~/Library/Application Support/REAPER/Scripts/`
- **Windows:** `%APPDATA%\REAPER\Scripts\`
- **Linux:** `~/.config/REAPER/Scripts/`

### Step 3 — Prepare project
1. Create/rename track `lyrics`.
2. Create/rename track `chords`.
3. Add lyrics/chords into item notes.
4. Verify song regions in timeline.

### Step 4 — Launch interface
1. Open REAPER + project.
2. Open web interface and load `ReaSet.html`.
3. Run Lyrics and Chords Lua scripts.

---

## 7) Usage setup
### Recommended live workflow
1. Verify regions.
2. Run Lyrics/Chords scripts.
3. Open `ReaSet.html`.
4. Create/select setlist.
5. Reorder songs and set states (skip/loop/chain).
6. Test transport before showtime.
7. Export `.json` backup.

### Persistence and backups
- Browser-local state (`localStorage`).
- Use Export/Import JSON for backup/migration.
- Recommended: dated backups before major edits.

### Best practices
- Keep consistent region naming.
- Keep a dedicated “Show-Ready” project.
- Test on the same device/browser used on stage.

---

## 8) Usage Manual
### Top Bar & Visualization
- **Grid View**: Toggles between a detailed hierarchical list or large card blocks for touch-friendly usage.
- **Hide Skipped**: Visually removes currently "skipped" songs from the view (great for decluttering during a show).
- **Auto-Scroll**: Automatically locks and scrolls the viewport to the currently playing active region/song.
- **Edit Sets**: Opens the administrative management panel for creating, renaming, cloning, or deleting Setlists.

### Display Modes & Canvas
- **Live View**: Triggers a performance-focused layout showing a gigantic track name, progress bar, time remaining, the next queued song, and localized transport controls.
- **Lyrics & Chords (Floating Widgets)**: You can overlay floating widgets dynamically synced to the `Lyrics` and `Chords` text tracks on REAPER. They contain a contextual toolbar to adjust font sizes, typeface, and colors mapping locally on your screen.

#### Lyrics panel — three-line view
The lyrics panel shows the **previous verse above** and the **next verse below** the
current one, both smaller and dimmed so the active line stays dominant. Missing
neighbours (start of a song, or a gap between items) keep their space reserved, so the
current line never jumps around while you are reading it.

Context lines are **clamped to the song currently playing**: a verse from the previous
or next song never bleeds into this one's context lines. At the start of a song the
"previous" slot stays blank rather than showing the last line of whatever played before
it; at the end of a song the "next" slot shows **"Siguiente: <song name>"** instead of
the next song's first lyric — a heads-up, not a spoiler. This needs `Reaset.lua` to
publish each neighbour's position (added alongside its text); an older `Reaset.lua`
simply doesn't clamp, matching the behaviour before this feature existed.

A discreet **⚙ gear** in the panel header opens a small popover to adjust:

| Setting | Options |
|---|---|
| **Tamaño global** | 16–120 px slider — the base size everything else scales from |
| **Línea principal** | 50–150% of the global size, current line only |
| **Letras secundarias** | 10–100% of the global size, previous/next lines only |
| **Grosor** | Fino · Medio · Negrita · Black |
| **Color** | 5 presets + a custom colour picker |
| **Context lines** | Toggle the previous/next verses off entirely |

**Tamaño global**, **Línea principal** and **Letras secundarias** are three independent
sliders: the global size sets the overall scale everything is measured against, while
principal/secundario each control their own line(s) as a percentage of it — e.g. you can
shrink the context lines down to 10% for a near-invisible hint, or bring them up to 100%
to match the current line exactly, without moving the current line's own size at all.
Defaults (100% / 44%) reproduce the original look.

All six persist in `localStorage`, so your reading setup survives a reload.

#### Chords panel — three-across view
The chords panel uses the same neighbour logic, laid out **horizontally**: the previous
chord sits to the **left** and the next chord to the **right** of the current one, both
smaller and dimmed. Equal space is reserved on both sides, so the current chord stays
optically centred no matter how long the neighbouring chord names are.

> **One item = no neighbours.** The sides read the *previous* and *next* **items** on the
> `chords` track. If a single item spans the whole song, there are no neighbours to show
> and the sides stay blank — that is correct, not a fault. Split the chords into one item
> per change to get the left/right context.

#### Transitions and the status strip
Verses live on a **vertical 3D carousel**, like iOS Cover Flow turned 90°. The three lines
are positions on a drum: they follow its **curved path** and **recede into the distance**,
but are **never tilted** — the text always stays square to the viewer so it reads at a
glance.

Advancing a verse turns the drum by **exactly one position**:

| Line | Travel |
|---|---|
| Current | Slot `0` → `-1`: arcs up and back, shrinking |
| Previous | `-1` → `-2`: continues past the top edge and is gone |
| Next | `+1` → `0`: arcs up to neutral depth, growing |
| New verse | `+2` → `+1`: arcs into view from below |

**Wrap-aware spacing.** Slot positions are computed assuming a single-line current
verse; a verse that wraps onto two lines would otherwise crowd — or nearly touch —
the smaller context lines above and below it, since their fixed offset doesn't grow
with it. ReaSet measures the current line's actual rendered height on every change
and pushes prev/next further away by half a line's height for each extra wrapped
line, so the clearance stays constant whether the current verse is one line or several.

Expressing it as "every line moves one slot" is what makes it read as **a single rotation**
rather than four separate animations. The drum radius is in `em`, so the carousel scales
with the font size you pick in the gear popover.

Chords use **the same drum laid on its side**: previous chord to the left, next to the
right, following the same curve and receding the same way, likewise never tilted. Changing
chord turns the drum by one position exactly as the lyrics one does.

The turn is **deliberately quick — 100 ms**, covering 90% of the distance in the first
~40 ms and then decelerating hard into place. On stage you should register that the line
changed without having to watch it move: sustained motion in the reading area is tiring,
so the animation is there to keep you oriented, not to be looked at.

Only a genuine one-step move earns the turn. A seek, a song change or an edit is not a step
around the drum, so those **crossfade** instead — turning would imply a continuity that did
not happen. `prefers-reduced-motion` is honoured: if your system asks for less motion,
nothing animates at all.

Diagnostics never occupy the reading area — they live in a very faint strip at the bottom
of the panel, with two visibility levels:

| Situation | Visibility |
|---|---|
| Working, but no lyric/chord at this point | Barely visible (16%) — a **normal** state, not a fault |
| Something needs fixing (script stopped, frozen, no track, no SWS) | Readable (55%), still unobtrusive |

While content is on screen the strip stays empty. An instrumental gap still shows the
previous and next verse, which is exactly what is useful at that moment.

### Lyrics & Chords Track Naming
ReaSet reads lyrics and chords from **two dedicated REAPER tracks**, identified by their
name. `Reaset.lua` scans the project and looks for these two keywords:

| Panel | Track keyword |
|---|---|
| 🎤 Lyrics | `lyrics` |
| 🎸 Chords | `chords` |

**The rule:** matching is case-insensitive, and any *symbol* decoration or *numbering*
around the keyword is ignored. Strip the leading symbols/numbers and the trailing
symbols — whatever remains must be **exactly** the word `lyrics` or `chords`.

| Track name | Detected | Why |
|---|---|---|
| `lyrics` · `Lyrics` · `LYRICS` | ✅ | case is ignored |
| `*Lyrics` · `**Chords**` | ✅ | asterisk decoration stripped |
| `#Chords` · `-- Lyrics` · `[Chords]` · `>Lyrics` | ✅ | any leading/trailing symbols stripped |
| `01 Lyrics` · `3 - Chords` | ✅ | leading numbering stripped |
| `* 01 - Lyrics` | ✅ | mixed prefixes unwind in any order |
| `Backing Lyrics` · `Lyrics Bus` · `Chords Gtr` | ❌ | an extra **word** remains |

Extra words never match — that is deliberate, so ordinary audio tracks that happen to
contain the word "lyrics"/"chords" are left alone. If two tracks match the same keyword,
the **topmost** one in the track list wins.

The text itself lives in **Item Notes** (double-click an item → *Notes*), one item per
lyric/chord block; the item's position on the timeline is what syncs it to playback.

Both tracks are **optional**: if `lyrics` or `chords` is missing, that panel simply stays
idle and everything else (transport, loops, setlist) keeps working.

### Track List Interaction
- Tracks containing sub-sections will display a dropdown button (Chevron). Expanding it allows individual targeting of nested sub-regions (e.g. Intro, Chorus, Outro).
- The progress bar backing each track will dynamically map to the closest UI-color assigned to its native REAPER Region.
- **PLAY NEXT**: Actively loads the specified song under the REAPER playhead cue and stops playback, eagerly awaiting you to hit Play.

### Action Commands
- **&#9632; / &#8677; (Follow Action)**: Toggles whether playback stops at the end of the song or flows seamlessly into the next un-skipped track.
- **&#8635; (Loop)**: Activates infinite looping over the bounded region or currently selected sub-section segment.
- **&#10005; (Skip)**: Strikethroughs the track, completely ignoring it from linear continuous playback chains.

### Phone layout — view tabs move to the sidebar
On a phone, the five view tabs (SHOW / LYRICS / CHORDS / LIVE / CANVAS) move out of the top
bar and into a **Views** grid at the top of the sidebar. This isn't only about saving space:
five tabs at their minimum width plus the menu button plus the timer readout add up to
438px of content in a 375px-wide screen, so the timer and song count were being pushed
**63px off the right edge** — invisible on a phone. With the tabs relocated everything fits,
and the bar itself slims from 56px to 46px since it no longer has to house stacked
icon-over-label tabs.

The swap is driven purely by screen size, not by Director/Player mode — a Director on a
phone has the same screen. **Tablets and desktops keep the tabs on top**, unchanged. The
rule covers phones in portrait *and* landscape (`max-width: 600px` or `max-height: 520px`);
an iPad is at least 744px in both directions either way round, so it never matches. An iPad
in a narrow Split View pane does get the phone layout, which is correct — the pane really is
phone-sized.

Both sets of tabs always exist in the DOM and stay in sync, so rotating a phone or resizing
a window switches between the two layouts instantly with no stale highlight.

### Display Filters
Located under **Settings — Appearance** in the sidebar. Three independent real-time sliders apply a CSS filter to the setlist body:
- **Luminance** — 50% to 150% (default 100%)
- **Contrast** — 50% to 150% (default 100%)
- **Saturation** — 0% to 200% (default 100%)

Values persist across sessions. A "Reset" button restores all three to default.

### 🎹 MIDI Learn
Located in the sidebar (**MIDI Learn** button). Maps notes/CC messages from a
connected MIDI controller to Play, Stop, Play/Pause, next/previous song,
next/previous section, toggle loop, restart song, and toggle skip. Click
**Escuchar siguiente nota / CC…**, send the message from your controller,
and the mapping is saved; multiple mappings can be active at once, and can
be cleared individually or all at once.

> ⚠️ **Not currently supported: Safari (macOS, iPadOS, iOS).** MIDI Learn
> is built on the **Web MIDI API** (`navigator.requestMIDIAccess`), which
> Safari has never implemented, on any Apple platform. The MIDI Learn panel
> will show no available devices there — this isn't a bug to report, it's a
> missing browser API. Use a Chromium-based browser (Chrome, Edge) instead,
> or route the controller through REAPER itself rather than the browser
> (REAPER's own MIDI mapping isn't affected by this at all). See the
> [Roadmap](./ROADMAP.md) for the longer-term plan here.

### Smooth Seek
**Smooth Seek** is enabled by default under **Show Options** and is saved separately for each REAPER project. When playback is already running, selecting a song or section manually — including MIDI **Next/Previous Section** and **Restart Song** — sends only the new position to REAPER. This lets REAPER honour its own *Do not change playback position immediately when seeking (smooth seek)* preference.

Turn Smooth Seek off when a controller needs an immediate, hard jump instead. Selecting a song while stopped still starts playback either way. Queue Mode, Cue, loops, and automatic transitions retain their existing behaviour.

### Region Name Command Reference
ReaSet parses special inline commands written directly in REAPER region and marker names. Multiple commands can be combined freely. The remaining text after parsing is the display name.

**Example:**
```
Chorus {pre-chorus} +LOOP:4 [green] [.bold] [1:20]
```

#### `+` Commands — Playback behavior

| Command | Description |
|---|---|
| `+PAUSE` | Pauses playback at the end of the section. |
| `+SKIP` | Marks the section as skipped by default. Appears struck through. |
| `+LOOP` | Enables infinite looping for the section. |
| `+LOOP:N` | Repeats the section exactly **N** times, then continues. Shows a live `X/N` badge. |
| `+LOOPFULL` | Loop with absolute priority — any queued region waits until the loop finishes. |

#### `[]` Square brackets — Appearance & duration

| Command | Description |
|---|---|
| `[colorname]` | Assigns a palette color to the card. |
| `[mm:ss]` | Overrides the displayed duration of the section. |
| `[nosong]` | Excludes the item from song count and numbering. Shown dimmed. |
| `[.classname]` | Applies a CSS style class to the name. |

Available colors: `gray` · `red` · `orange` · `amber` · `yellow` · `lime` · `green` · `emerald` · `teal` · `cyan` · `sky` · `blue` · `indigo` · `violet` · `purple` · `fuchsia` · `pink` · `rose`

Available classes: `.bold` · `.dim` · `.italic` · `.loud`

#### `{}` Curly braces — Informational text

| Command | Description |
|---|---|
| `{text}` | Displays auxiliary italic text next to the section name. Not shown in Live View or Canvas. |

#### Special prefixes — Markers only

| Command | Description |
|---|---|
| `>` | Converts the marker into a sub-section of the active song. |
| `*` | Ignores the marker entirely — it will not appear in the app. |
| `>>> TargetName` | Auto-jumps to the region whose name matches `TargetName` when this section ends. |

#### Reserved names

| Name | Description |
|---|---|
| `STOP` | Stop playback marker. |
| `SONG END` | Alias for `STOP`. |

---

### Director / Player Mode
Every ReaSet instance talks to REAPER directly through the same Web Interface — there is
no server of ReaSet's own, so control and display share one channel. That means two
devices open at once can genuinely fight over REAPER (both auto-advancing at a song's end,
for instance). Director/Player mode exists to make that impossible for a device that
isn't supposed to be controlling the show in the first place — a musician's tablet, say.

**On first load (or after clearing `localStorage`), ReaSet forces a choice:**

| Mode | What it can do |
|---|---|
| 🎬 **Director** | Everything ReaSet already does: transport, cue/queue, loops, skip/chain, MIDI, reordering. |
| 🎧 **Player (Músico)** | Read-only: live song/section/progress, lyrics, chords. Local display prefs (canvas, colours, fonts, filters) are still yours to change — none of that reaches REAPER. |

The choice is **remembered** (`localStorage`, not per-session) — a refresh, an app restart or
a device reboot does not re-ask. This is deliberate: recalling a stored mode grants no new
privilege (the device already chose Director once, on purpose), and re-forcing the picker on
every accidental refresh would just strand a Director mid-show behind a modal at the worst
possible moment. A small badge in the top-right corner always shows the current mode; click
it any time to switch (no confirmation needed going Director → Player, since that only
narrows what the device can do).

**How it's enforced:** every command this page could ever send to REAPER passes through one
function (`wwr_req`). In Player mode that function drops anything that isn't a plain read —
so even a stray click, a leftover keyboard shortcut, or a reconnect racing the mode check
cannot move REAPER's transport. Buttons and shortcuts are *additionally* dimmed/disabled in
Player mode for honesty (so a tap doesn't look like it silently failed), but that's a
courtesy layer — the network-level block is what actually holds.

**The setlist looks different in Player mode**, because a musician's screen has a different
job than a Director's. Controls that a Player can never use are *removed* rather than
dimmed — the drag handle, the ⋮ edit menus, the "Play Song" button — which on a phone hands
roughly 217px of a 347px-wide row back to the song name (it was getting 18px, about one
letter of a title). The skip/loop/chain toggles collapse to compact badges that appear only
when the flag is set: a Player can't press them, but *does* need to know a song loops or
chains into the next. Skipped songs stay clearly greyed out, the currently-playing row
renders at full strength, and the rest of the rows are only lightly dimmed so the names,
times and progress stay easy to read on stage.

**The sidebar is filtered the same way.** A Player keeps everything that only changes their
own screen — Display Filters, Theme, lyrics/chords fonts, sizes and colours, plus
**Auto-Scroll, Hide Skips and Grid View**, which are view toggles that never reach REAPER
(Auto-Scroll is a plain `scrollIntoView()`; the other two only re-render the list). What
goes is what steers the *show*: Queue Mode and Smooth Seek change how a click seeks, and a
Player can't click; Auto-Stop and Init Song MIDI send REAPER commands outright; Stop Hold
tunes a transport button that isn't there in Player mode; and MIDI Learn maps a controller
onto those same blocked commands, so a Player could bind a pedal and then watch it do
nothing. The three view toggles stay on purpose — they're the same ones Player mode already
leaves working on the keyboard, so hiding their switches would contradict shortcuts that
still respond.

The footer transport follows the same rule. PLAY / STOP / Loop are gone in Player mode —
they do nothing, and PLAY was the worst of them, since its label is the *action* rather
than the state, so it read "PAUSE" while playing on a screen where nothing can be paused.
Transport state is already on screen and clearer: the active row's progress fill moves and
its time counts down. **SYNC stays** — it restarts the polling connection, which is a read,
and it's the one recovery a musician has if a venue's wifi drops mid-show and auto-reconnect
doesn't catch it. (It used to be blocked by the bar's own click-through guard, so a Player's
only working button down there was unreachable; it works now.)

> **Not a security boundary.** REAPER's own Web Interface has no authentication — anyone on
> the same network who knows the endpoint can already control it directly, with or without
> ReaSet. Player mode stops *ReaSet* from being a way in; it does not lock the network down.

#### Director PIN (optional)
By default, choosing **Director** in the picker (or switching a badge from Músico to
Director) needs nothing but a tap — fine for a solo user, less fine once a band shares one
REAPER session and you don't want a curious tap on someone's phone to hand them the
transport. A Director can set a PIN from the sidebar (**Setlist Sync → Set/Change Director
PIN**); once set, *any* device actively choosing Director — not one recalling its already-
stored choice on a refresh — is asked for it first.

- The PIN itself is never sent anywhere as plain text: only a small hash is stored, in
  REAPER's own persisted ExtState (survives a REAPER restart, same mechanism the native-loop
  feature already relies on), so every device checks against the same value with no server.
- Leave the prompt empty when setting it to remove the PIN entirely.
- Like Player mode's own write-block, **this is a deterrent, not real security** — the hash
  algorithm is intentionally simple, and REAPER's Web Interface still has no authentication
  underneath any of this (see the box above). It stops an idle tap, not a determined person
  with network access.

#### Two Directors at once
ReaSet now watches for this instead of staying silent about it: each Director quietly
re-announces "I'm active" every few seconds while it holds the mode. If a second device
actively *chooses* Director while another one is already announcing itself, it's warned
before the switch completes and can back out. If a second Director appears later — mid-show,
on an already-stored device that skipped that prompt on boot — a red banner says so for as
long as the conflict lasts, then clears itself the moment the other Director closes its tab
or its own heartbeat goes stale. Nothing is blocked either way; REAPER is still yours to
choose to share on purpose (a fill-in Director covering a song, for instance) — you just
can't end up in that state *by accident* without knowing it.

The warning names the other device — *"El dispositivo 'X' ya está activo como
Director"* — instead of just "another one". Every device has a name: a rough
OS+browser guess (*"iPad · Safari"*) by default, or a custom one you set from
the sidebar (**This device: ... → Rename this device**), which is worth doing
once per tablet before a show so a conflict warning is actually useful.

#### Shared setlist sync (Director → Players)
Order, and each song's skip/loop/chain flags, live in the browser's own `localStorage` —
normally private to that one device. So that Players see the *Director's actual* setlist
instead of their own stale/default one, a Director can push a snapshot that Reaset.lua
writes to a file (`reaset_setlist_sync.json`) next to `ReaSet.html`; Players read it.

- **Push is automatic**, debounced ~1s after any edit (reorder, skip/loop/chain toggle,
  import). You don't need to remember to sync before a show.
- **Pull is manual** for a Director (sidebar → *Pull setlist from shared*) — adopting
  another device's shared setlist overwrites local, unsynced edits, so it asks first.
  Players pull automatically every few seconds in the background; nothing to click.
- A pulled setlist that doesn't match the **currently open REAPER project** (checked via
  the same project fingerprint used for per-project storage) is rejected rather than
  applied — you'll see a warning instead of a garbled setlist.
- **Known limits, by design, for this first pass:** only the active setlist's order and
  flags sync — not the full named-setlist library, and not the live queue/cue target
  (that's transient UI state; the actually-playing song already reaches Players for free
  via REAPER's own transport). Two Directors pushing at nearly the same moment still means
  last push wins — the conflict banner above warns you it's happening, but doesn't merge
  the two pushes. A dropped chunk (rare, needs a mid-push network hiccup) self-heals within
  about a second as the next tick retries — worst case, that one push is silently skipped
  and the next edit's push supersedes it.

---

## 9) Keyboard Shortcuts
ReaSet inherently supports the following global keyboard bindings to streamline command operations in rigid setups:

| Key | Action |
| --- | --- |
| **`Space`** | Play / Pause (Global transport toggle) |
| **`Enter`** | Smart Stop (Puts playhead at the beginning of the current active region) |
| **`Escape`** | Closes Live View overlay. If already closed, it immediately aborts an active 'Loop' state. |
| **`V`** | Toggles Live View overlay open/close |
| **`L`** | Toggles Lyrics floating widget visibility |
| **`C`** | Toggles Chords floating widget visibility |
| **`G`** | Toggles between List View and Grid View |
| **`O`** | Toggles Loop state over the currently playing Region/Sub-Region |
| **`Right Arrow`** | Cues the next valid (unskipped) track in the list |
| **`Left Arrow`** | Jumps playhead to the direct start locus of the currently playing track |
| **`Up Arrow`** | Cues the previous valid track in the list |
| **`Down Arrow`** | Resets cue to the very first song in the setlist |

---

## 10) Quick troubleshooting
### ❌ Lyrics or chords not showing
The panel's empty-state message tells you the **actual** cause — read it before
changing anything. `Reaset.lua` reports its status live:

| Message | Meaning | Fix |
|---|---|---|
| *"Reaset.lua is not running"* | The script isn't loaded, or you're on the legacy `Legacy/` scripts | Actions → ReaScript: Load… → `Reaset.lua` → Run |
| *"No track named lyrics/chords found"* | Script alive, but no track matched | Check the name against [the naming rules](#lyrics--chords-track-naming) |
| *"SWS extension missing"* | `ULT_GetMediaItemNote` unavailable | Install [SWS](https://www.sws-extension.org/) |
| *"Track X detected — no item under the cursor"* | Everything works | Move the playhead over an item that has **Item Notes** |

The last one is the most common false alarm: the track is found, but the playhead
is not over an item, or the item's **Notes** field is empty.

#### 🔍 Diagnostic script
If the message is not enough, run **`Tools/ReaSet_Diagnose.lua`** — see
[Tools](#5-tools) for what it reports.

### ❌ `ULT_GetMediaItemNote` error
- Missing compatible scripting/API environment; install dependency or adapt script.

### ❌ No interface data/control
- Verify Web Interface is enabled and reachable.
- Verify `main.js` loads from the same folder.

### ❌ MIDI Learn shows no devices / doesn't respond
**Not currently supported in Safari — macOS, iPadOS, or iOS**, on any Apple
device. This is not a bug: Safari has never implemented the Web MIDI API
that the feature is built on, so there is no in-browser MIDI to detect.
Use a Chromium-based browser (Chrome, Edge), or map the controller directly
in REAPER instead of through ReaSet. See the [Roadmap](./ROADMAP.md).

---

# 🇪🇸 SECCIÓN EN ESPAÑOL (INICIO)

## 📌 Índice (ES)
- [💛 Apoya el proyecto](#-apoya-el-proyecto)
- [1) ¿Qué es ReaSet?](#1-qué-es-reaset)
- [2) Funcionalidades principales](#2-funcionalidades-principales)
- [3) Créditos y agradecimientos](#3-créditos-y-agradecimientos)
- [4) Requisitos](#4-requisitos)
- [5) Herramientas](#5-herramientas)
- [6) Instalación](#6-instalación)
- [7) Configuración de uso](#7-configuración-de-uso)
- [8) Manual de uso](#8-manual-de-uso-interactivo)
  - [Nombres de las pistas de Letras y Acordes](#nombres-de-las-pistas-de-letras-y-acordes)
  - [Filtros de pantalla](#filtros-de-pantalla)
  - [MIDI Learn](#-midi-learn-1)
  - [Referencia de comandos en nombres de región](#referencia-de-comandos-en-nombres-de-región)
- [9) Atajos de teclado](#9-atajos-de-teclado)
- [10) Solución rápida de problemas](#10-solución-rápida-de-problemas)

---

## 💛 Apoya el proyecto
Si este proyecto te sirve, puedes apoyar su desarrollo aquí:

<a href="https://ko-fi.com/W7W81VLW05" target="_blank">
  <img src="https://storage.ko-fi.com/cdn/kofi3.png?v=6" alt="Invítame un café en Ko-fi" height="36" style="border:0px;height:36px;" />
</a>

📜 [Changelog](./CHANGELOG.md) · 🗺️ [Roadmap](./ROADMAP.md)

---

## 1) ¿Qué es ReaSet?
**ReaSet** es una interfaz web para **REAPER** orientada a shows en vivo y gestión de setlists.

Base del proyecto:
- Inspirado en **ReaSetlistManager** de `suckyble`.
- Extendido con visualización de **letras y acordes** usando lógica/script de **X-Raym**.

Objetivo principal:
- Ordenar y ejecutar canciones (regiones) durante un show.
- Controlar transporte (play/stop/cue/next).
- Administrar múltiples setlists con persistencia local.
- Mostrar letras y acordes sincronizados desde pistas dedicadas.

---

## 2) Funcionalidades principales
- ✅ Gestión de setlists (crear/eliminar/cambiar).
- 🔀 Drag & drop para reordenar canciones.
- 🎯 Estado por canción: activa, en cola, omitida, loop, chain.
- ⏯️ Controles de transporte en pantalla.
- 💾 Exportación/importación de setlists en JSON.
- 🧠 Persistencia local vía `localStorage`, aislada por proyecto de REAPER.
- 🎤 Panel de letras + 🎸 panel de acordes.
- 🎨 Personalización visual (temas, tipografías, tamaños, color de acordes, filtros de pantalla).
- 🗂️ Regiones anidadas con loop, skip, color y notas individuales por sección.
- 🏷️ Sistema de comandos inline — controla comportamiento directamente desde los nombres de región en REAPER.
- 🔢 Badge de loop fraccionario (ej. `2/4`) visible en tiempo real sobre la sección activa.
- 🖥️ Live View con barra de progreso de sub-región, indicador de sección siguiente y contador de loops.
- 🌗 Filtros de pantalla en tiempo real: luminancia, contraste y saturación desde la sidebar.
- 🎬🎧 Modo Director/Player — instancias de solo lectura para músicos que nunca pueden
  mandarle un comando a REAPER, con setlist compartido sincronizado desde el Director.

Archivo principal:
- `ReaSet.html`

Dependencias incluidas:
- `Sortable.min.js`
- Scripts Lua de puente legacy en `Legacy/` (opcional/avanzado — ver [Requisitos](#4-requisitos))

---

## 3) Créditos y agradecimientos
### Proyecto base
- **suckyble / ReaSetlistManager**  
- https://github.com/suckyble/ReaSetlistManager

### Integración de letras y acordes
- **X-Raym / REAPER-ReaScripts**  
- https://github.com/X-Raym/REAPER-ReaScripts/tree/master/Web%20Interfaces
- Script de referencia:  
  `Convert Lyrics track items notes for the dedicated web browser interface.lua`

### Librería de ordenamiento
- **SortableJS** (`Sortable.min.js`)

### Proceso de desarrollo asistido por IA
Este proyecto fue iterado, depurado y testeado con apoyo de:
- **Claude (cowork)**
- **Google (Antigravity)**

La validación funcional final se hizo en REAPER con pruebas reales de uso en setlist.

> ⚖️ Nota legal: mantener y respetar licencias originales de los componentes reutilizados (por ejemplo, GPL v3 donde aplique).

---

## 4) Requisitos
### Software
1. **REAPER** (v5+ recomendado; ideal versión reciente).
2. Navegador web (desktop/tablet/móvil).
3. Proyecto REAPER con regiones (normalmente una región por canción).

### Archivos mínimos
- `ReaSet.html`
- `Sortable.min.js`
- `Reaset.lua` — **script único unificado** (motor de loop + letras + acordes).

> **Legacy / avanzado:** los tres scripts originales siguen incluidos en
> `Legacy/` (`ReaSet_NativeLoop.lua` y los dos convertidores de X-Raym).
> Solo los necesitas si prefieres ejecutar los subsistemas por separado. Para
> una instalación normal, `Reaset.lua` reemplaza a los tres.
> Ten en cuenta que los scripts legacy exigen los nombres **exactos** `lyrics` / `chords`:
> el soporte de prefijos (`*Lyrics`) existe únicamente en `Reaset.lua`.

### Pistas requeridas para letras/acordes
- Una pista cuyo nombre sea `lyrics` — alimenta el panel 🎤 Letras.
- Una pista cuyo nombre sea `chords` — alimenta el panel 🎸 Acordes.
- Cada item debe tener texto en **Item Notes**.

El nombre se compara **sin distinguir mayúsculas** y admite prefijos/sufijos como
`*Lyrics`, `#Chords` o `01 Lyrics`. Ambas pistas son **opcionales**.
Ver [Nombres de las pistas de Letras y Acordes](#nombres-de-las-pistas-de-letras-y-acordes)
para las reglas completas.

### Compatibilidad de scripting
Los scripts usan `reaper.ULT_GetMediaItemNote`.
- Si tu REAPER no reconoce esa función, instala entorno/API compatible (ej. Ultraschall API) o adapta el método de lectura de notas.

---

## 5) Herramientas
Scripts independientes opcionales en `Tools/`. Ninguno hace falta para que
ReaSet funcione — la instalación siempre activa es solo `Reaset.lua` +
`ReaSet.html` — son utilidades a las que recurrís de vez en cuando: una para
crear contenido, otra para diagnosticar el puente de letras/acordes.

### 🎤 Lyrics Tapper — `Tools/Lyrics_Tapper.lua`
Herramienta independiente para REAPER/ReaImGui que sirve para **construir**
los items de `lyrics`/`chords`/`notes` que ReaSet lee. Pega un bloque de
texto, presioná **ARM** y luego marcá el ritmo (mouse o **Space**) mientras
suena la canción: cada tap cierra el item de la línea anterior y abre el
siguiente en la posición actual, al estilo teleprompter. Con N líneas, son N
taps para colocarlas todas, más **un tap más** para cerrar el último item y
terminar ahí mismo — no hace falta un Stop aparte para terminar limpio,
aunque Stop sigue disponible en cualquier momento para acabar antes de tiempo.
Detecta la pista destino con las mismas reglas de nombre flexibles que
`Reaset.lua`, la crea si no existe, y filtra encabezados de sección ("Coro",
"Verso 2", "[Chorus]", …) para que no terminen como items de letra.

- Requiere la extensión **ReaImGui** (aparte de SWS).
- Cárgalo con Actions → ReaScript: Load… → `Tools/Lyrics_Tapper.lua` → Run.

### 🔍 ReaSet Diagnose — `Tools/ReaSet_Diagnose.lua`
Informe de diagnóstico de solo lectura, de una sola pasada, para el puente de
letras/acordes — recurrí a él cuando el
[mensaje de estado in-app](#10-solución-rápida-de-problemas) no alcanza por
sí solo. Imprime cada pista con su nombre normalizado y cantidad de items,
qué pista elegiría cada puente, si SWS está presente, la posición del cursor,
y un volcado de las notas item por item — detectando al instante pistas que
se pisan entre sí (dos coincidiendo con la misma palabra clave) y notas
vacías. También se autotestea en una posición conocida como válida, así un
playhead mal ubicado nunca puede parecer un puente roto.

- Cárgalo con Actions → ReaScript: Load… → `Tools/ReaSet_Diagnose.lua` → Run.

---

## 6) Instalación
### Paso 1 — Copiar interfaz web
Copiar en la carpeta web de REAPER (donde existe `main.js`):
- `ReaSet.html`
- `Sortable.min.js`

#### Rutas por defecto (REAPER Resource Path)
> En REAPER: **Options > Show REAPER resource path in explorer/finder**.

**macOS**
- Resource Path: `~/Library/Application Support/REAPER/`
- Web root (habitual): `~/Library/Application Support/REAPER/Plugins/reaper_www_root/`

**Windows**
- Resource Path: `%APPDATA%\REAPER\`
- Web root (habitual): `%APPDATA%\REAPER\Plugins\reaper_www_root\`

**Linux**
- Resource Path: `~/.config/REAPER/`
- Web root (habitual): `~/.config/REAPER/Plugins/reaper_www_root/`

> `main.js` lo provee REAPER Web Interface (no viene en este proyecto).

### Paso 2 — Instalar el script Lua (un solo script)
1. Abrir REAPER.
2. Ir a **Actions > Show action list**.
3. Usar **ReaScript: Load...** y cargar **`Reaset.lua`**.
4. Buscar **"Reaset"** en la lista de acciones y **ejecutarlo** una vez.
5. (Recomendado) Añadirlo en **Options > Preferences > General > Startup actions**
   (o como *Global startup action* de SWS) para que arranque solo con REAPER.

> `Reaset.lua` es un único script de fondo persistente que corre el motor de
> loop nativo y los puentes de letras/acordes a la vez. **No hay Action ID que
> pegar** en `ReaSet.html` — la interfaz web lo detecta automáticamente.
>
> Las pistas de letras/acordes son opcionales: si falta la pista `lyrics` o
> `chords`, ese panel queda inactivo y el control de transporte/loop sigue
> funcionando.

#### Rutas por defecto para scripts
- **macOS:** `~/Library/Application Support/REAPER/Scripts/`
- **Windows:** `%APPDATA%\REAPER\Scripts\`
- **Linux:** `~/.config/REAPER/Scripts/`

### Paso 3 — Preparar proyecto
1. Crear/renombrar pista `lyrics`.
2. Crear/renombrar pista `chords`.
3. Escribir letras/acordes en notas de items.
4. Verificar regiones de canciones en timeline.

### Paso 4 — Abrir interfaz
1. Abrir REAPER + proyecto.
2. Abrir interfaz web y cargar `ReaSet.html`.
3. Ejecutar scripts Lua de Lyrics y Chords.

---

## 7) Configuración de uso
### Flujo recomendado (en vivo)
1. Verificar regiones.
2. Ejecutar scripts Lyrics/Chords.
3. Abrir `ReaSet.html`.
4. Crear/seleccionar setlist.
5. Reordenar canciones y definir estados (skip/loop/chain).
6. Probar transporte antes del show.
7. Exportar `.json` de respaldo.

### Persistencia y backups
- Estado local en navegador (`localStorage`).
- Respaldos/migración vía Export/Import JSON.
- Recomendado: backup por fecha antes de cambios grandes.

### Buenas prácticas
- Nombres consistentes de regiones.
- Proyecto “Show-Ready” separado del de producción.
- Testear en el mismo dispositivo/navegador que usarás en vivo.

---

## 8) Manual de uso
### Barra superior y visualización
- **Grid View (Cuadrícula)**: Alterna entre diseño de lista detallada o tarjetas grandes para uso rápido.
- **Hide Skipped**: Oculta visualmente las canciones marcadas para "saltar" (útil en vivo para no confundirse).
- **Auto-Scroll**: Centra automáticamente la región/canción activa a medida que avanza la reproducción.
- **Edit Sets**: Abre el panel de administración donde puedes crear, renombrar, duplicar y eliminar Setlists.

### Modos y herramientas (Canvas)
- **Live View (Modo Directo)**: Activa una interfaz enfocada para performance con nombre gigante de la canción actual, progreso, siguiente canción y botones de transporte.
- **Letras y Acordes (Widgets fltantes)**: Puedes activar la visión superpuesta de pistas de Letras (`Lyrics`) y Acordes (`Chords`). En la esquina superior derecha del widget dispones de un selector de fuentes, tamaño, y personalización de color para adaptarlo a tu pantalla. 

#### Panel de letras — vista de tres líneas
El panel de letras muestra el **verso anterior arriba** y el **verso siguiente abajo** del
actual, ambos más pequeños y atenuados para que la línea activa siga siendo la dominante.
Cuando falta un vecino (inicio de la canción, o un hueco entre items) su espacio se
reserva igualmente, así la línea actual **no salta** mientras la estás leyendo.

Las líneas de contexto quedan **limitadas a la canción que suena en ese momento**: un
verso de la canción anterior o siguiente nunca se cuela en el contexto de la actual. Al
empezar una canción, el hueco "anterior" queda en blanco en vez de mostrar la última línea
de lo que sonaba antes; al terminar, el hueco "siguiente" muestra **"Siguiente: <nombre de
la canción>"** en vez del primer verso de la próxima — un aviso, no un spoiler. Esto
necesita que `Reaset.lua` publique la posición de cada vecino (se agregó junto a su texto);
con una versión anterior de `Reaset.lua` simplemente no se limita, igual que antes de
existir esta función.

Un **⚙ engranaje** discreto en la cabecera del panel abre un popover para ajustar:

| Ajuste | Opciones |
|---|---|
| **Tamaño global** | Slider de 16–120 px — el tamaño base sobre el que escala todo lo demás |
| **Línea principal** | 50–150% del tamaño global, solo la línea actual |
| **Letras secundarias** | 10–100% del tamaño global, solo las líneas anterior/siguiente |
| **Grosor** | Fino · Medio · Negrita · Black |
| **Color** | 5 presets + selector de color personalizado |
| **Versos de contexto** | Interruptor para ocultar el anterior/siguiente |

**Tamaño global**, **Línea principal** y **Letras secundarias** son tres sliders
independientes: el tamaño global fija la escala base sobre la que se mide todo, mientras
que principal/secundario controlan cada uno su(s) propia(s) línea(s) como porcentaje de
esa base — por ejemplo, puedes achicar las líneas de contexto hasta un 10% para que sean
apenas una pista, o subirlas a 100% para que igualen a la línea actual, sin mover el
tamaño de la línea actual en absoluto. Los valores por defecto (100% / 44%) reproducen el
aspecto original.

Los seis ajustes se guardan en `localStorage`, así que tu configuración de lectura
sobrevive a una recarga.

#### Panel de acordes — vista de tres en línea
El panel de acordes usa la misma lógica de vecinos, pero en **horizontal**: el acorde
anterior a la **izquierda** y el siguiente a la **derecha** del actual, ambos más pequeños
y atenuados. Se reserva el mismo espacio a ambos lados, así el acorde actual queda
ópticamente centrado por largos que sean los nombres de los acordes vecinos.

> **Un solo item = sin vecinos.** Los laterales leen el item *anterior* y *siguiente* de la
> pista `chords`. Si un único item abarca toda la canción, no hay vecinos que mostrar y los
> laterales quedan en blanco — eso es correcto, no un fallo. Divide los acordes en un item
> por cambio para tener el contexto izquierda/derecha.

#### Transiciones y franja de estado
Los versos viven en un **carrusel 3D vertical**, al estilo del Cover Flow de iOS girado 90°.
Las tres líneas son posiciones sobre un tambor: recorren su **trayectoria curva** y
**retroceden en profundidad**, pero **nunca se inclinan** — el texto siempre queda de frente
para que se lea de un vistazo.

Al avanzar un verso, el tambor **gira exactamente una posición**:

| Línea | Recorrido |
|---|---|
| Actual | Posición `0` → `-1`: asciende y retrocede, encogiendo |
| Anterior | `-1` → `-2`: continúa más allá del borde superior y desaparece |
| Siguiente | `+1` → `0`: asciende a profundidad neutra, creciendo |
| Nuevo verso | `+2` → `+1`: entra en escena desde abajo |

**Espaciado consciente del salto de línea.** La posición de cada slot se calcula
asumiendo que el verso actual ocupa una sola línea; uno que salta a dos líneas, sin
más, terminaría apretando —o casi tocando— las líneas de contexto más pequeñas
arriba y abajo, porque su desplazamiento fijo no crece con él. ReaSet mide la altura
real renderizada de la línea actual en cada cambio y aleja el anterior/siguiente medio
alto de línea por cada línea extra que salte, así el espacio se mantiene constante sin
importar si el verso actual ocupa una línea o varias.

Que todo se exprese como "cada línea avanza una posición" es lo que hace que se lea como
**una sola rotación** y no como cuatro animaciones sueltas. El radio del tambor está en
`em`, así que el carrusel escala con el tamaño de letra que elijas en el engranaje.

Los acordes usan **el mismo tambor tumbado de lado**: el acorde anterior a la izquierda y el
siguiente a la derecha, recorriendo la misma curva y retrocediendo igual, también sin
inclinarse. Al cambiar de acorde, el tambor gira una posición exactamente igual que el de
las letras.

El giro es **deliberadamente rápido — 100 ms**, cubriendo el 90% del recorrido en los
primeros ~40 ms y frenando con fuerza al final. En el escenario debes notar que la línea
cambió sin tener que verla moverse: el movimiento sostenido en el área de lectura cansa, así
que la animación está para mantenerte ubicado, no para ser observada.

Solo un avance real de un paso merece el giro. Un salto de posición, un cambio de canción o
una edición no son un paso en el tambor, así que esos hacen **fundido** — girar implicaría
una continuidad que no ocurrió. Se respeta `prefers-reduced-motion`: si tu sistema pide
menos movimiento, no se anima nada en absoluto.

Los mensajes de diagnóstico **no ocupan el área de lectura**: viven en una franja muy
tenue al pie del panel, con dos niveles de visibilidad.

| Situación | Visibilidad |
|---|---|
| Todo bien, pero no hay letra/acorde en ese punto | Apenas visible (16%) — es un estado **normal**, no un fallo |
| Algo hay que arreglar (script parado, congelado, sin track, sin SWS) | Legible (55%), sigue siendo discreto |

Cuando sí hay contenido en pantalla, la franja queda vacía. Un hueco instrumental sigue
mostrando el verso anterior y el siguiente, que es justo lo útil en ese momento.

### Nombres de las pistas de Letras y Acordes
ReaSet lee las letras y los acordes desde **dos pistas dedicadas de REAPER**, identificadas
por su nombre. `Reaset.lua` recorre el proyecto buscando estas dos palabras clave:

| Panel | Palabra clave |
|---|---|
| 🎤 Letras | `lyrics` |
| 🎸 Acordes | `chords` |

**La regla:** no distingue mayúsculas de minúsculas, e ignora cualquier decoración de
*símbolos* o *numeración* alrededor de la palabra clave. Se quitan los símbolos/números
del inicio y los símbolos del final — lo que quede debe ser **exactamente** la palabra
`lyrics` o `chords`.

| Nombre de pista | ¿Detectada? | Por qué |
|---|---|---|
| `lyrics` · `Lyrics` · `LYRICS` | ✅ | las mayúsculas se ignoran |
| `*Lyrics` · `**Chords**` | ✅ | se quitan los asteriscos |
| `#Chords` · `-- Lyrics` · `[Chords]` · `>Lyrics` | ✅ | se quita cualquier símbolo inicial/final |
| `01 Lyrics` · `3 - Chords` | ✅ | se quita la numeración inicial |
| `* 01 - Lyrics` | ✅ | los prefijos mixtos se resuelven en cualquier orden |
| `Backing Lyrics` · `Lyrics Bus` · `Chords Gtr` | ❌ | queda una **palabra** extra |

Las palabras extra nunca coinciden: es intencional, para que las pistas de audio normales
que contienen la palabra "lyrics"/"chords" no sean capturadas por error. Si dos pistas
coinciden con la misma palabra clave, gana la que esté **más arriba** en la lista de pistas.

El texto va en las **notas del item** (doble clic en el item → *Notes*), un item por bloque
de letra/acorde; la posición del item en la línea de tiempo es lo que lo sincroniza con la
reproducción.

Ambas pistas son **opcionales**: si falta `lyrics` o `chords`, ese panel simplemente queda
inactivo y todo lo demás (transporte, loops, setlist) sigue funcionando.

### Interacción de Canciones (Filas)
- Canciones con sub-secciones mostrarán un botón desplegable (Chevrón). Expándelo para ver/operar sobre las sub-regiones individualmente (Intro, Coro, etc.).
- La barra de progreso de cada canción heredará dinámicamente el color configurado a esa Región dentro del archivo de REAPER.
- **PLAY NEXT**: Activa una canción específica en la cola de REAPER y detiene la reproducción allí, esperando a que presiones Play.

### Comandos de región
- **&#9632; / &#8677; (Follow Action)**: Alterna si la canción se detiene al final o continúa sin pausas hacia la siguiente en la lista.
- **&#8635; (Loop)**: Bloquea un ciclo infinito sobre la región actual o la sub-sección seleccionada.
- **&#10005; (Skip)**: Marca la canción con una línea tachada y se la saltará de la lista de reproducción continua.

### Layout en teléfono — las pestañas se van a la sidebar
En un teléfono, las cinco pestañas de vista (SHOW / LYRICS / CHORDS / LIVE / CANVAS) salen
de la barra superior y pasan a una grilla **Views** al tope de la sidebar. No es solo por
ganar espacio: cinco pestañas en su ancho mínimo, más el botón de menú, más el bloque de
timer suman 438px de contenido en una pantalla de 375px, así que el timer y el contador de
canciones quedaban empujados **63px fuera del borde derecho** — invisibles en un teléfono.
Con las pestañas reubicadas entra todo, y la barra baja de 56px a 46px porque ya no tiene
que alojar pestañas con ícono sobre etiqueta.

El cambio lo dispara el tamaño de pantalla, no el modo Director/Player — un Director en
teléfono tiene la misma pantalla. **Tablets y escritorio conservan las pestañas arriba**,
sin cambios. La regla cubre teléfonos en vertical *y* en horizontal (`max-width: 600px` o
`max-height: 520px`); un iPad mide al menos 744px en ambas direcciones en cualquier
orientación, así que nunca entra. Un iPad en un panel angosto de Split View sí recibe el
layout de teléfono, que es lo correcto — ese panel realmente tiene tamaño de teléfono.

Los dos juegos de pestañas siempre existen en el DOM y se mantienen sincronizados, así que
rotar el teléfono o redimensionar la ventana cambia entre layouts al instante y sin dejar un
resaltado viejo.

### Filtros de pantalla
Disponibles en **Settings — Appearance** dentro de la sidebar. Tres sliders independientes aplican un filtro CSS en tiempo real al cuerpo del setlist:
- **Luminancia** — 50% a 150% (por defecto 100%)
- **Contraste** — 50% a 150% (por defecto 100%)
- **Saturación** — 0% a 200% (por defecto 100%)

Los valores persisten entre sesiones. El botón "Restablecer valores" devuelve todo al 100%.

### 🎹 MIDI Learn
Está en la sidebar (botón **MIDI Learn**). Mapea notas/mensajes CC de un
controlador MIDI conectado a Play, Stop, Play/Pause, canción siguiente/anterior,
sección siguiente/anterior, toggle loop, reiniciar canción y toggle skip.
Hacé click en **Escuchar siguiente nota / CC…**, mandá el mensaje desde tu
controlador, y la asignación queda guardada; podés tener varias activas a la
vez, y borrarlas de a una o todas juntas.

> ⚠️ **No soportado actualmente en Safari — macOS, iPadOS o iOS**, en
> ningún dispositivo de Apple. MIDI Learn está construido sobre la **Web
> MIDI API** (`navigator.requestMIDIAccess`), que Safari nunca implementó,
> en ninguna plataforma de Apple. El panel de MIDI Learn no va a mostrar
> dispositivos ahí — no es un bug para reportar, es una API de navegador
> que falta. Usá un navegador basado en Chromium (Chrome, Edge), o mapeá el
> controlador directamente en REAPER en vez de por el navegador (el mapeo
> MIDI nativo de REAPER no se ve afectado por esto para nada). Ver el
> [Roadmap](./ROADMAP.md) para el plan a más largo plazo.

### Smooth Seek
**Smooth Seek** está activado por defecto en **Show Options** y se guarda de forma independiente para cada proyecto de REAPER. Cuando la reproducción ya está en curso, al seleccionar manualmente una canción o sección —incluidos los controles MIDI **Siguiente/Anterior sección** y **Reiniciar canción**— ReaSet envía a REAPER solo la nueva posición. Así REAPER puede respetar su propia preferencia *No cambiar inmediatamente la posición de reproducción al buscar (smooth seek)*.

Desactiva Smooth Seek cuando un controlador necesite un salto inmediato. Al seleccionar una canción mientras REAPER está detenido, la reproducción sigue iniciándose en ambos casos. Queue Mode, Cue, los loops y las transiciones automáticas conservan su comportamiento actual.

### Referencia de comandos en nombres de región
ReaSet interpreta comandos especiales escritos directamente en los nombres de región y marcadores de REAPER. Se pueden combinar libremente. El texto que queda tras parsear todos los comandos es el nombre que se muestra en la app.

**Ejemplo:**
```
Chorus {pre-coro} +LOOP:4 [green] [.bold] [1:20]
```

#### Comandos `+` — Comportamiento de reproducción

| Comando | Descripción |
|---|---|
| `+PAUSE` | Pausa la reproducción al llegar al final de la sección. |
| `+SKIP` | Marca la sección como omitida por defecto. Aparece tachada. |
| `+LOOP` | Activa el loop infinito de la sección. |
| `+LOOP:N` | Repite la sección exactamente **N** veces y luego continúa. Muestra un badge `X/N` en vivo. |
| `+LOOPFULL` | Loop con prioridad absoluta — si hay una canción en cola, espera a que el loop termine. |

#### `[]` Corchetes — Apariencia y duración

| Comando | Descripción |
|---|---|
| `[color]` | Asigna un color de la paleta a la tarjeta. |
| `[mm:ss]` | Sobreescribe la duración mostrada de la sección. |
| `[nosong]` | Excluye el elemento del conteo y numeración de canciones. Aparece en opacidad reducida. |
| `[.clase]` | Aplica una clase CSS de estilo al nombre. |

Colores disponibles: `gray` · `red` · `orange` · `amber` · `yellow` · `lime` · `green` · `emerald` · `teal` · `cyan` · `sky` · `blue` · `indigo` · `violet` · `purple` · `fuchsia` · `pink` · `rose`

Clases disponibles: `.bold` · `.dim` · `.italic` · `.loud`

#### `{}` Llaves — Texto informativo

| Comando | Descripción |
|---|---|
| `{texto}` | Muestra texto auxiliar en cursiva junto al nombre de la sección. No aparece en Live View ni Canvas. |

#### Prefijos especiales — Solo marcadores

| Comando | Descripción |
|---|---|
| `>` | Convierte el marcador en una sub-sección de la canción activa. |
| `*` | Ignora completamente el marcador — no aparece en la app. |
| `>>> NombreDestino` | Salta automáticamente a la región cuyo nombre coincida con `NombreDestino` al terminar esta sección. |

#### Palabras reservadas

| Nombre | Descripción |
|---|---|
| `STOP` | Marcador de parada de reproducción. |
| `SONG END` | Alias de `STOP`. |

---

### Modo Director / Player
Toda instancia de ReaSet habla directo con REAPER a través del mismo Web Interface — no hay
servidor propio de ReaSet, así que control y visualización comparten un solo canal. Eso
significa que dos dispositivos abiertos a la vez pueden pelearse de verdad por REAPER (los
dos auto-avanzando al terminar una canción, por ejemplo). El modo Director/Player existe
para hacer eso imposible en un dispositivo que no debería estar controlando el show — la
tablet de un músico, por ejemplo.

**Al cargar por primera vez (o después de limpiar `localStorage`), ReaSet exige elegir:**

| Modo | Qué puede hacer |
|---|---|
| 🎬 **Director** | Todo lo que ReaSet ya hace: transporte, cola, loops, skip/chain, MIDI, reordenar. |
| 🎧 **Player (Músico)** | Solo lectura: canción/sección/progreso en vivo, letras, acordes. Las preferencias de pantalla locales (canvas, colores, fuentes, filtros) siguen siendo tuyas para cambiar — nada de eso llega a REAPER. |

La elección se **recuerda** (`localStorage`, no por sesión) — un refresco, un reinicio de la
app o del dispositivo no vuelve a preguntar. Es deliberado: recordar un modo guardado no
otorga ningún privilegio nuevo (ese dispositivo ya eligió Director una vez, a propósito), y
volver a forzar el selector en cada refresco accidental dejaría a un Director trabado detrás
de un modal justo en el peor momento. Un pequeño badge en la esquina superior derecha
siempre muestra el modo actual; hacé click en cualquier momento para cambiarlo (sin
confirmación al pasar de Director a Player, ya que eso solo reduce lo que el dispositivo
puede hacer).

**Cómo se hace cumplir:** todo comando que esta página pueda llegar a mandarle a REAPER pasa
por una sola función (`wwr_req`). En modo Player, esa función descarta cualquier cosa que no
sea una lectura simple — así que ni un click perdido, ni un atajo de teclado que quedó
activo, ni una reconexión que gane la carrera contra la verificación de modo pueden mover el
transporte de REAPER. Los botones y atajos además se ven atenuados/deshabilitados en modo
Player por honestidad (para que un tap no parezca que falló en silencio), pero esa es una
capa de cortesía — el bloqueo a nivel de red es lo que realmente sostiene la garantía.

**El setlist se ve distinto en modo Player**, porque la pantalla de un músico tiene otro
trabajo que la de un Director. Los controles que un Player nunca va a poder usar se
*eliminan* en vez de atenuarse — el drag handle, los menús ⋮ de edición, el botón "Play
Song" — lo que en un teléfono le devuelve unos 217px de una fila de 347px al nombre de la
canción (venía recibiendo 18px, más o menos una letra del título). Los toggles de
skip/loop/chain se colapsan a badges compactos que aparecen solo cuando el flag está
activo: un Player no puede presionarlos, pero *sí* necesita saber que una canción loopea o
engancha con la siguiente. Las canciones skipeadas quedan claramente grises, la fila que
está sonando se muestra a intensidad plena, y el resto se atenúa apenas para que los
nombres, tiempos y progreso se lean bien en escena.

**La sidebar se filtra con el mismo criterio.** Un Player conserva todo lo que solo cambia
su propia pantalla — Display Filters, Theme, fuentes/tamaños/colores de letras y acordes,
más **Auto-Scroll, Hide Skips y Grid View**, que son toggles de vista que nunca llegan a
REAPER (Auto-Scroll es un `scrollIntoView()` pelado; los otros dos solo re-renderizan la
lista). Lo que se va es lo que dirige el *show*: Queue Mode y Smooth Seek cambian cómo
busca un click, y un Player no puede clickear; Auto-Stop e Init Song MIDI mandan comandos a
REAPER directamente; Stop Hold ajusta un botón de transporte que en modo Player ni existe;
y MIDI Learn mapea un controlador contra esos mismos comandos bloqueados, así que un Player
podría asignar un pedal y después verlo no hacer nada. Los tres toggles de vista se quedan a
propósito — son los mismos que el modo Player ya deja funcionando por teclado, así que
esconder sus switches contradiría atajos que sí responden.

La barra de transporte inferior sigue la misma regla. PLAY / STOP / Loop desaparecen en
modo Player — no hacen nada, y PLAY era el peor de los tres, porque su etiqueta es la
*acción* y no el estado: mientras REAPER reproducía decía "PAUSE" en una pantalla donde
nada se puede pausar. El estado del transporte ya está en pantalla y más claro: la fila
activa tiene el relleno de progreso avanzando y su tiempo en cuenta regresiva. **SYNC se
queda** — reinicia la conexión de sondeo, que es una lectura, y es la única recuperación
que tiene un músico si el wifi del lugar se cae en medio del show y la reconexión
automática no alcanza. (Antes quedaba bloqueado por el propio guard de clicks de la barra,
así que el único botón que le servía a un Player ahí abajo era inalcanzable; ahora funciona.)

> **No es un límite de seguridad.** El propio Web Interface de REAPER no tiene autenticación
> — cualquiera en la misma red que conozca el endpoint ya puede controlarlo directamente, con
> o sin ReaSet. El modo Player evita que *ReaSet* sea una puerta de entrada; no cierra la red.

#### PIN de Director (opcional)
Por defecto, elegir **Director** en el selector (o pasar el badge de Músico a Director) no
pide nada más que un tap — está bien para un solo usuario, menos bien cuando una banda
comparte una sesión de REAPER y no querés que un tap curioso en el teléfono de alguien le
entregue el transporte. Un Director puede poner un PIN desde el sidebar (**Setlist Sync →
Set/Change Director PIN**); una vez configurado, cualquier dispositivo que elija Director
activamente — no uno que recuerda su elección ya guardada en un refresco — lo pide primero.

- El PIN en sí nunca viaja en texto plano: solo se guarda un hash pequeño, en el ExtState
  persistido del propio REAPER (sobrevive un reinicio de REAPER, el mismo mecanismo que ya
  usa la función de loop nativo), así que cada dispositivo verifica contra el mismo valor sin
  necesidad de servidor.
- Dejá el prompt vacío al configurarlo para quitar el PIN por completo.
- Igual que el bloqueo de escritura del modo Player, **esto es un disuasivo, no seguridad
  real** — el algoritmo de hash es deliberadamente simple, y el Web Interface de REAPER
  sigue sin tener autenticación debajo de todo esto (ver el recuadro de arriba). Frena un tap
  distraído, no a alguien decidido con acceso a la red.

#### Dos Directores a la vez
ReaSet ahora vigila esto en vez de quedarse callado al respecto: cada Director se
reanuncia "estoy activo" cada pocos segundos mientras sostiene el modo. Si un segundo
dispositivo *elige* Director mientras otro ya se está anunciando, se le avisa antes de
completar el cambio y puede dar marcha atrás. Si un segundo Director aparece más tarde —
en medio de un show, en un dispositivo que ya tenía el modo guardado y se saltó ese aviso al
arrancar — un banner rojo lo indica mientras dure el conflicto, y se limpia solo en el
momento en que el otro Director cierra su pestaña o su propio heartbeat queda obsoleto.
Nada se bloquea en ningún caso — REAPER sigue siendo tuyo para compartir a propósito si
querés (un Director de reemplazo cubriendo una canción, por ejemplo) — solo que ya no podés
terminar en ese estado *por accidente* sin saberlo.

El aviso nombra al otro dispositivo — *"El dispositivo 'X' ya está activo como
Director"* — en vez de solo "otro dispositivo". Todo dispositivo tiene un
nombre: por defecto una estimación de OS+navegador (*"iPad · Safari"*), o uno
propio que definís desde el sidebar (**This device: ... → Rename this
device**), algo que conviene hacer una vez por tablet antes de un show para
que el aviso de conflicto sirva de algo.

#### Sincronización de setlist compartido (Director → Players)
El orden y las banderas de skip/loop/chain de cada canción viven en el `localStorage` del
propio navegador — normalmente privado a ese dispositivo. Para que los Players vean el
setlist *real del Director* en vez del suyo propio (viejo o por defecto), un Director puede
empujar una foto que `Reaset.lua` escribe en un archivo (`reaset_setlist_sync.json`) al lado
de `ReaSet.html`; los Players lo leen.

- **El push es automático**, con debounce de ~1s después de cualquier edición (reordenar,
  toggle de skip/loop/chain, importar). No hace falta acordarse de sincronizar antes de un show.
- **El pull es manual** para un Director (sidebar → *Pull setlist from shared*) — adoptar el
  setlist compartido de otro dispositivo sobreescribe ediciones locales no sincronizadas, así
  que primero pregunta. Los Players hacen pull automático cada pocos segundos en segundo
  plano; no hay nada que clickear.
- Un setlist compartido que no coincide con el **proyecto de REAPER actualmente abierto**
  (verificado con el mismo fingerprint de proyecto que usa el almacenamiento por proyecto) se
  rechaza en vez de aplicarse — vas a ver una advertencia en vez de un setlist mezclado.
- **Límites conocidos, a propósito, para esta primera versión:** solo sincronizan el orden y
  las banderas del setlist activo — no toda la biblioteca de setlists nombrados, ni el
  objetivo de cola en vivo (es estado de UI transitorio; la canción realmente sonando ya le
  llega gratis a los Players vía el transporte de REAPER). Dos Directores empujando casi al
  mismo tiempo sigue significando que gana el último push — el banner de conflicto de arriba
  te avisa que está pasando, pero no combina los dos pushes. Un chunk perdido (raro, necesita
  un corte de red justo en medio de un push) se autorepara en aproximadamente un segundo
  cuando el siguiente tick reintenta — en el peor caso, ese push se salta en silencio y el
  push de la siguiente edición lo reemplaza.

---

## 9) Atajos de teclado
ReaSet soporta los siguientes comandos de teclado globales para mejorar el control en entornos rígidos:

| Tecla | Acción |
| --- | --- |
| **`Space`** | Play / Pause (Alternar estado general) |
| **`Enter`** | Smart Stop (Detiene en el inicio de la región activa actual) |
| **`Escape`** | Cierra la vista Live View. Si ya está cerrada, desactiva un "Loop" activo temporalmente. |
| **`V`** | Alterna abrir/cerrar la vista "Live View" |
| **`L`** | Alterna abrir/cerrar el widget flotante de Letras (Lyrics) |
| **`C`** | Alterna abrir/cerrar el widget flotante de Acordes (Chords) |
| **`G`** | Alterna entre vista de Lista (List View) y Cuadrícula (Grid View) |
| **`O`** | Activa/Desactiva Loop en la Región/Sub-región en curso en vivo |
| **`Flecha Derecha`** | Carga la siguiente canción válida en la cola (Cue) |
| **`Flecha Izquierda`** | Salta directamente al punto de reproducción de la canción actual en curso |
| **`Flecha Arriba`** | Carga la canción válida anterior en la cola |
| **`Flecha Abajo`** | Reinicia la cola a la primera canción del Setlist completo |

---

## 10) Solución rápida de problemas
### ❌ No aparecen letras o acordes
El mensaje del panel vacío te dice la causa **real** — léelo antes de cambiar nada.
`Reaset.lua` publica su estado en vivo:

| Mensaje | Significado | Solución |
|---|---|---|
| *"Reaset.lua no está corriendo"* | El script no está cargado, o estás usando los scripts legacy de `Legacy/` | Actions → ReaScript: Load… → `Reaset.lua` → Run |
| *"No se encontró ningún track llamado lyrics/chords"* | El script vive, pero ninguna pista coincidió | Revisa el nombre según [las reglas](#nombres-de-las-pistas-de-letras-y-acordes) |
| *"Falta la extensión SWS"* | `ULT_GetMediaItemNote` no está disponible | Instala [SWS](https://www.sws-extension.org/) |
| *"Track X detectado — no hay item bajo el cursor"* | Todo funciona | Mueve el playhead sobre un item que tenga **notas** |

El último es la falsa alarma más común: la pista se encontró, pero el playhead no
está sobre ningún item, o el campo **Notes** del item está vacío.

#### 🔍 Script de diagnóstico
Si el mensaje no basta, ejecutá **`Tools/ReaSet_Diagnose.lua`** — ver
[Herramientas](#5-herramientas) para saber qué informa.

### ❌ Error `ULT_GetMediaItemNote`
- Falta entorno/API compatible; instalar dependencia o adaptar script.

### ❌ Interfaz sin datos/control
- Verificar Web Interface habilitada y accesible.
- Verificar carga correcta de `main.js` en la misma carpeta.

### ❌ MIDI Learn no muestra dispositivos / no responde
**No soportado actualmente en Safari — macOS, iPadOS o iOS**, en ningún
dispositivo de Apple. Esto no es un bug: Safari nunca implementó la Web
MIDI API sobre la que está construida la función, así que no hay MIDI
disponible en el navegador para detectar. Usá un navegador basado en
Chromium (Chrome, Edge), o mapeá el controlador directamente en REAPER en
vez de por ReaSet. Ver el [Roadmap](./ROADMAP.md).
