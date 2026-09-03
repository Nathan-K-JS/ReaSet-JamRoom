# Jam Room — One-Shot Song Import (operator guide)

Give the tool a YouTube link (or a song name to search); it downloads the
audio, splits it into stems with Fadr, places everything in the open REAPER
project on the standard Jam Room PB/`[JR:…]` layout, adds the
`Band - Song` region, and creates timed **lyrics** and **chords** items for
ReaSet's Lyrics/Chords views. One command per song, then a short review pass.

## One-time setup (on whichever PC runs imports)

> Setting up a machine from scratch? Do [FRESH_INSTALL.md](FRESH_INSTALL.md)
> first — it covers REAPER, SWS, the web interface, the scripts and the project
> layout. This section is only the importer's own requirements.

1. **Get this repo onto the PC** — `git clone` to `C:\JamRoom` (see the next
   section). Everything the importer needs lives in `tools/`; songs it
   downloads land in `imports/` beside it.
2. **Double-click `JamRoom Setup.bat`** (repo root). It installs the free
   tools (Python, yt-dlp, ffmpeg), prepares the config, and deploys
   `ReaSet.html` into REAPER's web root. (Equivalent manual route:
   `winget install Python.Python.3.12 yt-dlp.yt-dlp Gyan.FFmpeg`, then
   `pip install requests numpy`.)
3. **Fadr API key** (needs the Fadr Plus subscription, $10/mo):
   log in at fadr.com → account page → **API tab** → *Create New API Key*.
   The importer page asks for it on first launch and stores it locally
   (gitignored `tools/jamroom_import.config.json`).
4. REAPER needs the **SWS extension** and the project needs the ten permanent
   **PB buses** plus tracks named `lyrics` and `chords`
   (see [JAMROOM_SETUP.md](JAMROOM_SETUP.md)).
5. The REAPER **web interface** must be enabled. On the first import the tool
   registers `jamroom_import_apply.lua` as a REAPER action (persisted), then
   triggers every apply through the web API of the running instance — if
   auto-registration fails, run `tools/jamroom_register_apply.lua` once from
   the Action list.

## Removing a song

Importer page → **Song library**. Lists everything in the REAPER project with
its length and how much disk its local audio uses. **Delete…** requires typing
the song's name to enable the button, and asks separately whether to remove the
downloaded audio.

Deleting removes only that song's region, stems, lyrics and chords. The PB and
`[JR:…]` buses, every other song, and the paid-for split on Fadr are untouched
— and **one Ctrl+Z in REAPER puts the whole song back** (deleted audio is not
restored by undo).

### Keep the audio, or not?

- **Keep it** (default): the song appears under *"Downloaded on this PC but not
  in the project"* with a **Re-add now** button that puts it back in seconds,
  with no internet and no Fadr. Costs ~0.5 GB.
- **Delete it**: reclaims the space. Putting the song back then means
  re-importing from the Fadr library — free, but a few minutes and it needs
  Fadr to be reachable.

Either way the tiny job record is kept, which is what makes the Fadr library
show a real song name instead of "source", and what restores the groups and
custom names you chose in the review screen last time.

## How big can the project get?

Disk is the only practical limit, and it is not close. A song costs roughly
**0.5 GB** of local audio (about 430 MB of WAV stems REAPER plays, plus the
downloads). REAPER itself handles hours-long projects and thousands of regions
without complaint, and track count does not grow per song because the
`[JR:…]` buses are shared.

Roughly: **1 GB per two songs.** On a 1 TB drive with 750 GB free that is well
over a thousand songs — you will tire of scrolling the setlist long before
REAPER or the disk objects. To reclaim space, delete songs you no longer play
(re-importing from the Fadr library is free), or after a successful import the
`source.wav` and the `stems/*.wav` MP3 originals in a job folder are only
needed for the review screen and can be removed, saving ~100 MB per song.

## Getting it onto the jam room PC / updating it

First time (PowerShell — after this everything is double-click):

```
winget install --id Git.Git -e
```

**Now close PowerShell and open a new window.** Installing Git changes the
PATH, and an already-open window won't see it (`git : the term 'git' is not
recognized`). Check with `git --version`, then:

```
git clone -b feature/jamroom-claude https://github.com/Nathan-K-JS/ReaSet-JamRoom.git C:\JamRoom
```

*No-Git fallback:* on the GitHub page for this repo, switch to the
`feature/jamroom-claude` branch → **Code ▾ → Download ZIP** → extract to
`C:\JamRoom`. Everything works the same except `JamRoom Update.bat`, which
needs Git — without it, updating means downloading a fresh ZIP each time.

### Updating later — see [UPDATING.md](UPDATING.md)

Short version: double-click **`JamRoom Update.bat`**. **Delete nothing** — it
overwrites what changed and prints exactly what you need to restart.

Then run `C:\JamRoom\JamRoom Setup.bat` once (tools + config), and use the
importer as below. **Every update after that**: on the dev machine, push the
finished work to GitHub; on the jam room PC, double-click
**`JamRoom Update.bat`** — it pulls the latest version and re-deploys
`ReaSet.html` into REAPER's web folder automatically (then hard-reload
ReaSet on the tablets with Ctrl+F5). Local files that matter — the Fadr key
config and downloaded songs in `imports/` — are never touched by updates.

## Importing a song

With the target project open in REAPER, **double-click `JamRoom
Importer.bat`** (repo root). A browser page opens at
`http://localhost:8765` — it also works from the tablet at the LAN address
shown on the page (same trusted-LAN model as REAPER's own web interface):

1. Type a song name (or paste a YouTube link) → **Search**.
2. Tap the right match (title, channel, and duration are shown).
3. Confirm/correct the guessed **Band** and **Song title** — these become
   the region name — and check the estimated Fadr cost shown.
4. **Download & split** (a few minutes), then the page shows the
   **review screen**: every separated stem with a play button and a
   dropdown for which Jam Room group it goes to (pre-filled with the
   guess — listen and move e.g. a synth from Extras to Keys, or skip a
   stem entirely; stems sharing a group are mixed together), plus an
   editable **name field** — that name is what ReaSet's mute screen shows
   for the group (e.g. rename "Guitar 1" to "Lead Guitar"). Below that,
   the **lyric timing check**: "first lyric line appears at m:ss" with the
   line quoted, a lead-vocal play button to verify by ear, and a shift
   box (seconds; positive = later) pre-filled with the audio analysis's
   suggestion.
5. **Add to REAPER**, wait for the green ✔. Nothing is reported as done
   unless REAPER confirmed it — and the apply refuses to run if the
   active REAPER project tab isn't the Jam Room project (no PB buses),
   telling you to switch tabs and try again.
6. Setup problems (missing key, REAPER not running, missing tools) show as
   red ✘ checks at the top of the page with what to do.

Command-line equivalent (same pipeline, for scripting/debugging):
`python tools\jamroom_import.py "<url or search terms>"` with `--band`,
`--title`, `--yes`, `--no-apply`, `--lyrics-offset`, `--force-<stage>`.

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
That analysis is useful timing evidence, but it is not trusted as the chart:
on the review screen, choose the Ultimate Guitar chart the band actually uses
(search results are never selected automatically, and a chart URL can be
pasted directly). JamRoom takes chord names and order from that chart and
places them against matched lyric lines, with the recording analysis as the
fallback when the words cannot be matched safely.
**Lyric timing** is auto-checked: the tool cross-correlates singing activity
in the separated vocal stem against the lyric-line timeline and applies a
global shift if (and only if) they clearly disagree; a flat/ambiguous match
is reported for manual review instead of guessed at. `--lyrics-offset N.N`
overrides manually.

Cost: US$0.05 per input minute per separation task; Fadr Plus includes
$10/month of credit (≈15–50 songs/month depending on sub-splits).

## After each import — timing review

1. Play the song in REAPER; check stem quality and slot placement.
2. In ReaSet, open Lyrics or Chords and tap **Fix timing**. At a known moment,
   choose the line/chord that should begin and tap **This should start now**.
   One checkpoint moves the whole song; a later checkpoint corrects gradual
   drift; further checkpoints repair only the intervening parts. Corrections
   are saved in the REAPER project and can be removed individually or reset to
   the imported timing without rewriting the source items. If it is already
   correct, choose **Timing looks right — mark as checked** so the Song Library
   records that it was actually reviewed.
3. Exact highlighting is deliberately off by default. JamRoom shows a readable
   passage until **More controls → Highlight each change precisely** is enabled.
   Choosing the Big or Timeline chord view also enables precise following.
4. If the words or chart themselves are wrong, use importer → **Song library →
   Review or repair**. **Change the lyrics** selects another timed LRCLIB record;
   **Change the chord chart** searches or accepts a pasted chart URL. This keeps
   stems, routing and setlists intact. Replacing source timings clears their old
   correction checkpoints so a previous adjustment cannot be applied twice.

This same Song library workflow works for songs imported before this feature;
there is no need to delete and re-import a song just to repair words, chords or
timing.

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
- *Checking which version you are running* — the importer page shows a version
  badge next to its title (e.g. `v1.1 · 2026-08-22`). It reports the code
  actually running, not the files on disk, so if it is not the version you
  expect after an update, close the importer window and start it again.
- *Stem downloads slow or repeatedly reconnecting* — Fadr's storage throttles
  individual connections unpredictably. Stems download four at a time, each
  with resume and a watchdog that drops a connection stuck below 150 KB/s;
  "reconnecting..." lines are it working, not failing. Set `download_workers`
  in the config to change how many run at once.
- *YouTube download errors* (HTTP 403, "SABR-only streaming experiment",
  "formats have been skipped as they are missing a URL") — YouTube changes
  something every few weeks and yt-dlp ships a fix within days. The importer
  already tries four extraction methods and then updates yt-dlp and retries
  automatically, so this should self-heal; `JamRoom Update.bat` also refreshes
  yt-dlp. If it still fails, try again later or choose a different upload of
  the song.
- *"SWS extension missing"* — install SWS on that REAPER.
- *"region already exists"* — the song was imported before; delete the old
  region and its items first (one undo step if it was the last import).
- Raw Fadr responses are kept in `imports/<song>/fadr_raw.json` for
  debugging; chord/MIDI files in `fadr_midi/`.

## Known limits (honest)

- YouTube audio is lossy (~130 kbps Opus) — fine for rehearsal backing.
  Downloading from YouTube is against YouTube's ToS; private use, your call.
- Fadr chord detection is timing evidence, not a dependable final chart.
  Correctness depends on selecting a suitable published chart and reviewing the
  result against the actual recording; unusual arrangements can still require
  local timing checkpoints.
- Fadr's chord-file format is parsed defensively; if a song yields
  "no parseable chord file", keep the job folder and report it — the parser
  may need a tweak once more real responses have been seen.
- CLICK track generation and lyric forced-alignment (for songs without
  synced lyrics) are planned follow-ups, not in yet.
