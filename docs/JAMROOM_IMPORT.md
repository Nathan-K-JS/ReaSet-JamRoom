# Jam Room — One-Shot Song Import (operator guide)

Give the tool a YouTube link (or a song name to search); it downloads the
audio, splits it into stems with Fadr, places everything in the open REAPER
project on the standard Jam Room PB/`[JR:…]` layout, adds the
`Band - Song` region, and creates timed **lyrics** and **chords** items for
ReaSet's Lyrics/Chords views. One command per song, then a short review pass.

## One-time setup (on whichever PC runs imports)

0. **Get this repo onto the PC** (copy the whole folder or `git clone`,
   e.g. to `C:\JamRoom\ReaSet-JamRoom`) and deploy the current `ReaSet.html`
   into REAPER's web root (`%APPDATA%\REAPER\reaper_www_root`). Everything
   the importer needs lives in `tools/`; songs it downloads land in
   `imports/` next to it.
1. **Install the free tools** (PowerShell, then close & reopen the terminal):
   ```
   winget install Python.Python.3.12
   winget install yt-dlp.yt-dlp
   winget install Gyan.FFmpeg
   pip install requests numpy
   ```
2. **Fadr API key** (needs the Fadr Plus subscription, $10/mo):
   log in at fadr.com → account page → **API tab** → *Create New API Key*.
3. **Config**: copy `tools/jamroom_import.config.example.json` to
   `tools/jamroom_import.config.json` (this file is gitignored — the key
   stays local) and paste the API key into `fadr_api_key`.
4. REAPER must have the **SWS extension** (already required by ReaSet's
   lyrics/chords setup) and the project should contain the ten permanent
   **PB buses** (see `docs/JAMROOM_SETUP.md`).
5. The REAPER **web interface** must be enabled (it already is for ReaSet).
   On the first import the tool registers `jamroom_import_apply.lua` as a
   REAPER action (persisted), then triggers every apply through the web API
   of the running instance — if auto-registration fails, run
   `tools/jamroom_register_apply.lua` once from the Action list.

## Importing a song

With the target project open in REAPER:

```
python tools\jamroom_import.py "https://www.youtube.com/watch?v=..." 
python tools\jamroom_import.py "fleetwood mac dreams"        # search mode
```

- Search mode lists the top five YouTube matches; you pick one.
- The tool guesses `Band` / `Title` from the video title and asks you to
  confirm or correct them (`--band`/`--title` to pre-set, `--yes` for fully
  non-interactive with a direct URL).
- It then runs unattended: download → Fadr stems (≈2–5 min) → lyrics →
  hand-off to REAPER → **waits for REAPER's confirmation receipt** and prints
  the result. Nothing is reported as done unless REAPER confirmed it.

Each song lives in `imports/Band - Title/` (audio, stems, `job.json`) —
re-running the command resumes/skips completed steps, and a song that's
already applied is refused until you delete its region (protects against
double-imports).

**Keep the `imports/` folder.** The REAPER items reference the stem files
inside it — deleting or moving a song's folder silences that song's tracks.
(Alternatively, after importing use REAPER's *File → Save project* with
"Copy all media into project directory" to make the project self-contained.)
And **save the project** after a successful import — the importer edits the
open project; nothing is saved to disk until you save.

## What lands in the project

- Stem items on `[JR:SLOT] <label>` buses under the matching PB folders
  (existing import-labeled buses are reused; missing ones are created,
  correctly nested; **PB buses are never created** — they're wiring).
- A top-level `Band - Song` region straight after the current project end
  (+30 s gap). Region-name DSL characters are stripped from names.
- `lyrics` track: one item per synced lyric line (item notes carry the text —
  exactly what the X-Raym publisher scripts read).
- `chords` track: one item per detected chord segment.
- The whole import is **one undo step**.

## Fadr mapping (defaults, editable in the config)

Verified live stem names: drums→DRUMS, bass→BASS, electric→GTR1,
acoustic→GTR2, piano→KEYS, strings/wind/"melodics other"→EXTRA (summed),
"vocals lead"→LEAD VOX, "vocals background"→BVs.
Sub-splits (`vocal_split`, `melodic_split`) can be turned off for a cheaper,
simpler 4-stem import (vocals/bass/drums/other).

**Chords** come from Fadr's own analysis of the uploaded audio
(`chord,start,end` CSV in seconds), so their timing is measured from the
actual recording; notation is converted to musician form (F:maj→F, A:min→Am).
**Lyric timing** is auto-checked: the tool cross-correlates singing activity
in the separated vocal stem against the lyric-line timeline and applies a
global shift if (and only if) they clearly disagree; a flat/ambiguous match
is reported for manual review instead of guessed at. `--lyrics-offset N.N`
overrides manually.

Cost: US$0.05 per input minute per separation task; Fadr Plus includes
$10/month of credit (≈15–50 songs/month depending on sub-splits).

## After each import — 2-minute review

1. Play the song in REAPER; check stem quality and slot placement.
2. Skim the `chords` items — automatic chord recognition is ~80–85% right;
   fix the odd wrong chord by editing the item note.
3. If lyrics came back "plain only" or "none", the song had no synced lyrics
   on LRCLIB — paste/fix by hand, or wait for the forced-alignment upgrade.

## Setlist order

ReaSet's setlist dot menu (···) has **Sort: Band A–Z** — per-setlist,
off by default. When on, songs display alphabetically by band then title
(region names without `Band - ` sort last). Dragging a song manually turns
it off again, with a notice.

## Troubleshooting

- *"no confirmation from REAPER after 90s"* — is REAPER running with the
  right project **tab active**? Check REAPER's ReaScript console; the apply
  script can also be run manually from the Action list (the job pointer
  stays set). Dismiss any modal dialog REAPER is showing first.
- *HTTP 403 from YouTube* — update yt-dlp (`yt-dlp -U`).
- *"SWS extension missing"* — install SWS on that REAPER.
- *"region already exists"* — the song was imported before; delete the old
  region and its items first (one undo step if it was the last import).
- Raw Fadr responses are kept in `imports/<song>/fadr_raw.json` for
  debugging; chord/MIDI files in `fadr_midi/`.

## Known limits (honest)

- YouTube audio is lossy (~130 kbps Opus) — fine for rehearsal backing.
  Downloading from YouTube is against YouTube's ToS; private use, your call.
- Chord accuracy ~80–85%; extensions often simplified.
- Fadr's chord-file format is parsed defensively; if a song yields
  "no parseable chord file", keep the job folder and report it — the parser
  may need a tweak once more real responses have been seen.
- CLICK track generation and lyric forced-alignment (for songs without
  synced lyrics) are planned follow-ups, not in yet.
