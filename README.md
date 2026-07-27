##### 🇬🇧 ENGLISH

## 📌 Table of Contents
- [💛 Support this project](#-support-this-project)
- [1) What is ReaSet?](#1-what-is-reaset)
- [2) Main features](#2-main-features)
- [3) Credits and acknowledgements](#3-credits-and-acknowledgements)
- [4) Requirements](#4-requirements)
- [5) Installation](#5-installation)
- [6) Usage setup](#6-usage-setup)
- [7) Usage Manual](#7-interactive-usage-manual)
  - [Lyrics & Chords Track Naming](#lyrics--chords-track-naming)
  - [Display Filters](#display-filters)
  - [Region Name Command Reference](#region-name-command-reference)
- [8) Keyboard Shortcuts](#8-keyboard-shortcuts)
- [9) Quick troubleshooting](#9-quick-troubleshooting)

---

## 💛 Support this project
If this project helps you, you can support development here:

<a href="https://ko-fi.com/W7W81VLW05" target="_blank">
  <img src="https://storage.ko-fi.com/cdn/kofi3.png?v=6" alt="Buy Me a Coffee at ko-fi.com" height="36" style="border:0px;height:36px;" />
</a>


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

Main file:
- `ReaSet.html`

Included dependencies:
- `Sortable.min.js`
- Lua bridge scripts under `Requirements/`

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
> `Requirements/` (`ReaSet_NativeLoop.lua` and the two X-Raym Lyrics/Chords
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

## 5) Installation
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

## 6) Usage setup
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

## 7) Usage Manual
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

A discreet **⚙ gear** in the panel header opens a small popover to adjust:

| Setting | Options |
|---|---|
| **Tamaño** | 16–120 px slider (scales all three lines together) |
| **Grosor** | Fino · Medio · Negrita · Black |
| **Color** | 5 presets + a custom colour picker |
| **Context lines** | Toggle the previous/next verses off entirely |

All four persist in `localStorage`, so your reading setup survives a reload.

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

Expressing it as "every line moves one slot" is what makes it read as **a single rotation**
rather than four separate animations. The drum radius is in `em`, so the carousel scales
with the font size you pick in the gear popover.

Chords use **the same drum laid on its side**: previous chord to the left, next to the
right, following the same curve and receding the same way, likewise never tilted. Changing
chord turns the drum by one position exactly as the lyrics one does.

The turn is **deliberately quick — 190 ms**, covering 90% of the distance in the first
~70 ms and then decelerating hard into place. On stage you should register that the line
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

### Display Filters
Located under **Settings — Appearance** in the sidebar. Three independent real-time sliders apply a CSS filter to the setlist body:
- **Luminance** — 50% to 150% (default 100%)
- **Contrast** — 50% to 150% (default 100%)
- **Saturation** — 0% to 200% (default 100%)

Values persist across sessions. A "Reset" button restores all three to default.

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

## 8) Keyboard Shortcuts
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

## 9) Quick troubleshooting
### ❌ Lyrics or chords not showing
The panel's empty-state message tells you the **actual** cause — read it before
changing anything. `Reaset.lua` reports its status live:

| Message | Meaning | Fix |
|---|---|---|
| *"Reaset.lua is not running"* | The script isn't loaded, or you're on the legacy `Requirements/` scripts | Actions → ReaScript: Load… → `Reaset.lua` → Run |
| *"No track named lyrics/chords found"* | Script alive, but no track matched | Check the name against [the naming rules](#lyrics--chords-track-naming) |
| *"SWS extension missing"* | `ULT_GetMediaItemNote` unavailable | Install [SWS](https://www.sws-extension.org/) |
| *"Track X detected — no item under the cursor"* | Everything works | Move the playhead over an item that has **Item Notes** |

The last one is the most common false alarm: the track is found, but the playhead
is not over an item, or the item's **Notes** field is empty.

#### 🔍 Diagnostic script
If the message is not enough, run **`ReaSet_Diagnose.lua`** (Actions → ReaScript:
Load… → Run). It is read-only and prints a full report: every track with its
normalised name and item count, which track each bridge would pick, whether SWS is
present, the cursor position, and a per-item dump of the Notes field. It pinpoints
shadowed tracks (two tracks matching the same keyword) and empty Notes immediately.

### ❌ `ULT_GetMediaItemNote` error
- Missing compatible scripting/API environment; install dependency or adapt script.

### ❌ No interface data/control
- Verify Web Interface is enabled and reachable.
- Verify `main.js` loads from the same folder.

---

# 🇪🇸 SECCIÓN EN ESPAÑOL (INICIO)

## 📌 Índice (ES)
- [💛 Apoya el proyecto](#-apoya-el-proyecto)
- [1) ¿Qué es ReaSet?](#1-qué-es-reaset)
- [2) Funcionalidades principales](#2-funcionalidades-principales)
- [3) Créditos y agradecimientos](#3-créditos-y-agradecimientos)
- [4) Requisitos](#4-requisitos)
- [5) Instalación](#5-instalación)
- [6) Configuración de uso](#6-configuración-de-uso)
- [7) Manual de uso](#7-manual-de-uso-interactivo)
  - [Nombres de las pistas de Letras y Acordes](#nombres-de-las-pistas-de-letras-y-acordes)
  - [Filtros de pantalla](#filtros-de-pantalla)
  - [Referencia de comandos en nombres de región](#referencia-de-comandos-en-nombres-de-región)
- [8) Atajos de teclado](#8-atajos-de-teclado)
- [9) Solución rápida de problemas](#9-solución-rápida-de-problemas)

---

## 💛 Apoya el proyecto
Si este proyecto te sirve, puedes apoyar su desarrollo aquí:

<a href="https://ko-fi.com/W7W81VLW05" target="_blank">
  <img src="https://storage.ko-fi.com/cdn/kofi3.png?v=6" alt="Invítame un café en Ko-fi" height="36" style="border:0px;height:36px;" />
</a>


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

Archivo principal:
- `ReaSet.html`

Dependencias incluidas:
- `Sortable.min.js`
- Scripts Lua de puente en `Requirements/`

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
> `Requirements/` (`ReaSet_NativeLoop.lua` y los dos convertidores de X-Raym).
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

## 5) Instalación
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

## 6) Configuración de uso
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

## 7) Manual de uso
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

Un **⚙ engranaje** discreto en la cabecera del panel abre un popover para ajustar:

| Ajuste | Opciones |
|---|---|
| **Tamaño** | Slider de 16–120 px (escala las tres líneas a la vez) |
| **Grosor** | Fino · Medio · Negrita · Black |
| **Color** | 5 presets + selector de color personalizado |
| **Versos de contexto** | Interruptor para ocultar el anterior/siguiente |

Los cuatro ajustes se guardan en `localStorage`, así que tu configuración de lectura
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

Que todo se exprese como "cada línea avanza una posición" es lo que hace que se lea como
**una sola rotación** y no como cuatro animaciones sueltas. El radio del tambor está en
`em`, así que el carrusel escala con el tamaño de letra que elijas en el engranaje.

Los acordes usan **el mismo tambor tumbado de lado**: el acorde anterior a la izquierda y el
siguiente a la derecha, recorriendo la misma curva y retrocediendo igual, también sin
inclinarse. Al cambiar de acorde, el tambor gira una posición exactamente igual que el de
las letras.

El giro es **deliberadamente rápido — 190 ms**, cubriendo el 90% del recorrido en los
primeros ~70 ms y frenando con fuerza al final. En el escenario debes notar que la línea
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

### Filtros de pantalla
Disponibles en **Settings — Appearance** dentro de la sidebar. Tres sliders independientes aplican un filtro CSS en tiempo real al cuerpo del setlist:
- **Luminancia** — 50% a 150% (por defecto 100%)
- **Contraste** — 50% a 150% (por defecto 100%)
- **Saturación** — 0% a 200% (por defecto 100%)

Los valores persisten entre sesiones. El botón "Restablecer valores" devuelve todo al 100%.

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

## 8) Atajos de teclado
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

## 9) Solución rápida de problemas
### ❌ No aparecen letras o acordes
El mensaje del panel vacío te dice la causa **real** — léelo antes de cambiar nada.
`Reaset.lua` publica su estado en vivo:

| Mensaje | Significado | Solución |
|---|---|---|
| *"Reaset.lua no está corriendo"* | El script no está cargado, o estás usando los scripts legacy de `Requirements/` | Actions → ReaScript: Load… → `Reaset.lua` → Run |
| *"No se encontró ningún track llamado lyrics/chords"* | El script vive, pero ninguna pista coincidió | Revisa el nombre según [las reglas](#nombres-de-las-pistas-de-letras-y-acordes) |
| *"Falta la extensión SWS"* | `ULT_GetMediaItemNote` no está disponible | Instala [SWS](https://www.sws-extension.org/) |
| *"Track X detectado — no hay item bajo el cursor"* | Todo funciona | Mueve el playhead sobre un item que tenga **notas** |

El último es la falsa alarma más común: la pista se encontró, pero el playhead no
está sobre ningún item, o el campo **Notes** del item está vacío.

#### 🔍 Script de diagnóstico
Si el mensaje no basta, ejecuta **`ReaSet_Diagnose.lua`** (Actions → ReaScript:
Load… → Run). Es de solo lectura e imprime un informe completo: todas las pistas con
su nombre normalizado y cantidad de items, qué pista elegiría cada puente, si SWS
está presente, la posición del cursor y un volcado de las notas item por item.
Detecta al instante pistas que se pisan entre sí (dos coincidiendo con la misma
palabra clave) y notas vacías.

### ❌ Error `ULT_GetMediaItemNote`
- Falta entorno/API compatible; instalar dependencia o adaptar script.

### ❌ Interfaz sin datos/control
- Verificar Web Interface habilitada y accesible.
- Verificar carga correcta de `main.js` en la misma carpeta.
