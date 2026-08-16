#!/usr/bin/env python3
"""Jam Room one-shot song import — orchestrator.

Takes a YouTube URL (or search terms, confirmed interactively), then:
  1. downloads best-quality audio via yt-dlp and converts to WAV
  2. sends it to Fadr (API, requires Fadr Plus key) for stem separation,
     chord detection, and key/tempo detection
  3. fetches time-synced lyrics from LRCLIB (free, no key)
  4. writes a self-contained "job folder" (stems + job.json) which
     tools/jamroom_import_apply.lua consumes to mutate the REAPER project.

Stages are resumable: re-running with the same job folder skips completed
stages (use --force-<stage> to redo one).

Part of ReaSet Jam Room. GPL v3, same as the repo.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = Path(__file__).resolve().parent / "jamroom_import.config.json"
FADR_API = "https://api.fadr.com"
LRCLIB_API = "https://lrclib.net/api"
USER_AGENT = "ReaSet-JamRoom-Import/0.1 (https://github.com/; rehearsal tooling)"

# Default Fadr stem name -> Jam Room slot mapping. Overridable in config.
# Slots: DRUMS PERC_FX BASS GTR1 GTR2 KEYS BVS LEAD_VOX CLICK EXTRA
DEFAULT_SLOT_MAP = {
    "drums": "DRUMS",
    "bass": "BASS",
    "vocals": "LEAD_VOX",          # used when vocal sub-split is off
    "melodies": "KEYS",            # used when melodic sub-split is off
    "lead vocals": "LEAD_VOX",
    "background vocals": "BVS",
    "electric guitar": "GTR1",
    "acoustic guitar": "GTR2",
    "piano": "KEYS",
    "strings": "EXTRA",
    "wind": "EXTRA",
    "other melodies": "EXTRA",
    # never imported: "instrumental" (it's just the sum of the others)
}
IGNORED_STEMS = {"instrumental"}


def log(msg):
    print(f"[jamroom-import] {msg}", flush=True)


def die(msg, code=1):
    print(f"[jamroom-import] ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def load_config(path):
    p = Path(path) if path else DEFAULT_CONFIG
    if not p.exists():
        die(
            f"Config not found: {p}\n"
            f"Copy jamroom_import.config.example.json to {p.name} and fill in "
            f"your Fadr API key (fadr.com account page -> API tab)."
        )
    with open(p, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.setdefault("slot_map", DEFAULT_SLOT_MAP)
    cfg.setdefault("vocal_split", True)
    cfg.setdefault("melodic_split", True)
    cfg.setdefault("jobs_dir", str(REPO_ROOT / "imports"))
    return cfg


def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")


def sanitize_region_name(name):
    """Strip characters ReaSet's region-name mini-DSL would interpret
    (+FLAG, [color]/[.class], {info}, >>> chain-target)."""
    name = re.sub(r"[\[\]{}+]", " ", name)
    name = name.replace(">>>", " ")
    return re.sub(r"\s+", " ", name).strip()


# ---------------------------------------------------------------- job state

def load_job(job_dir):
    f = job_dir / "job.json"
    if f.exists():
        with open(f, encoding="utf-8") as fh:
            return json.load(fh)
    return {"schema": 1, "stages": {}}


def save_job(job_dir, job):
    job_dir.mkdir(parents=True, exist_ok=True)
    tmp = job_dir / "job.json.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(job, fh, indent=2)
    tmp.replace(job_dir / "job.json")


# ---------------------------------------------------------------- resolve

def run_ytdlp(args, **kw):
    exe = shutil.which("yt-dlp") or die("yt-dlp not found on PATH")
    return subprocess.run([exe] + args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def resolve_input(query, assume_yes):
    """Return (url, video_title, uploader). Interactive pick for search terms."""
    if re.match(r"https?://", query):
        r = run_ytdlp(["--no-playlist", "--skip-download", "--print",
                       "%(title)s\t%(channel,uploader)s\t%(duration_string)s", query])
        if r.returncode != 0:
            die(f"yt-dlp could not read {query}:\n{r.stderr[-800:]}")
        title, uploader, dur = (r.stdout.strip().split("\t") + ["", ""])[:3]
        log(f'Video: "{title}" by {uploader} [{dur}]')
        if not assume_yes:
            if input("Proceed with this video? [Y/n] ").strip().lower() in ("n", "no"):
                die("Aborted by user.", 0)
        return query, title, uploader

    log(f'Searching YouTube for: "{query}"')
    r = run_ytdlp(["--flat-playlist", "--skip-download", "--print",
                   "%(id)s\t%(title)s\t%(channel,uploader)s\t%(duration_string)s",
                   f"ytsearch5:{query}"])
    if r.returncode != 0:
        die(f"YouTube search failed:\n{r.stderr[-800:]}")
    rows = [line.split("\t") for line in r.stdout.strip().splitlines() if line.strip()]
    if not rows:
        die("No search results.")
    print("\nTop matches:")
    for i, row in enumerate(rows, 1):
        vid, title, uploader, dur = (row + ["", "", ""])[:4]
        print(f"  {i}. {title}  —  {uploader}  [{dur}]")
    choice = input(f"\nWhich one? [1-{len(rows)}, or q to abort] ").strip().lower()
    if choice in ("q", "quit", ""):
        die("Aborted by user.", 0)
    idx = int(choice) - 1
    if not 0 <= idx < len(rows):
        die("Invalid selection.")
    vid, title, uploader = rows[idx][0], rows[idx][1], rows[idx][2]
    return f"https://www.youtube.com/watch?v={vid}", title, uploader


def guess_band_title(video_title, uploader):
    """Best-effort 'Band - Title' guess from a YouTube video title."""
    t = re.sub(r"[\(\[][^)\]]*[\)\]]", "", video_title)  # drop (Official Video) etc.
    t = re.sub(r"\s+", " ", t).strip(" -–—")
    for sep in (" - ", " – ", " — ", ": "):
        if sep in t:
            band, title = t.split(sep, 1)
            return band.strip(), title.strip()
    return uploader.replace(" - Topic", "").strip(), t


# ---------------------------------------------------------------- download

def stage_download(job, job_dir, url, force):
    if job["stages"].get("download") and not force:
        log("Download stage already done — skipping.")
        return
    log("Downloading best-quality audio (yt-dlp -> WAV)...")
    out = job_dir / "source.%(ext)s"
    r = run_ytdlp(["--no-playlist", "-f", "bestaudio", "-x", "--audio-format", "wav",
                   # android client fallback avoids HTTP 403 on some videos
                   "--extractor-args", "youtube:player_client=default,android",
                   "--write-info-json", "-o", str(out), url])
    if r.returncode != 0:
        die(f"Download failed:\n{r.stderr[-1500:]}")
    wav = job_dir / "source.wav"
    if not wav.exists():
        die("yt-dlp finished but source.wav is missing.")
    ffprobe = shutil.which("ffprobe") or die("ffprobe not found on PATH")
    pr = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(wav)], capture_output=True, text=True)
    duration = round(float(pr.stdout.strip()), 3)
    job["duration"] = duration
    job["source"]["audio_file"] = "source.wav"
    job["stages"]["download"] = True
    save_job(job_dir, job)
    log(f"Downloaded: {wav.name} ({duration:.1f}s)")


# ---------------------------------------------------------------- fadr

class Fadr:
    def __init__(self, api_key):
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {api_key}",
                               "User-Agent": USER_AGENT})

    def _check(self, r, what):
        if r.status_code >= 400:
            die(f"Fadr {what} failed (HTTP {r.status_code}): {r.text[:800]}")
        return r.json()

    def upload(self, path):
        name = path.name
        j = self._check(self.s.post(f"{FADR_API}/assets/upload2",
                                    json={"name": name, "extension": "wav"},
                                    timeout=60), "create upload URL")
        url, s3path = j["url"], j["s3Path"]
        log(f"Uploading {name} ({path.stat().st_size / 1e6:.1f} MB) to Fadr...")
        with open(path, "rb") as f:
            r = requests.put(url, data=f, headers={"Content-Type": "audio/wav"},
                             timeout=600)
        if r.status_code >= 400:
            die(f"Fadr file upload failed (HTTP {r.status_code})")
        j = self._check(self.s.post(f"{FADR_API}/assets",
                                    json={"name": name, "extension": "wav",
                                          "group": f"{name}-group", "s3Path": s3path},
                                    timeout=60), "create asset")
        return j["asset"]

    def stem_task(self, asset_id, stem_type=None):
        body = {"_id": asset_id}
        if stem_type:
            body["stemType"] = stem_type
        j = self._check(self.s.post(f"{FADR_API}/assets/analyze/stem", json=body,
                                    timeout=60), f"create stem task ({stem_type or 'main'})")
        return j["task"]

    def wait_task(self, task_id, label):
        log(f"Waiting for Fadr task: {label} (polling every 5s)...")
        t0 = time.time()
        while True:
            j = self._check(self.s.post(f"{FADR_API}/tasks/query",
                                        json={"_ids": [task_id]}, timeout=60),
                            "poll task")
            tasks = j.get("tasks") or []
            task = tasks[0] if tasks else None
            if task:
                status = (task.get("status") or {})
                if isinstance(status, dict):
                    prog, msg = status.get("progress"), status.get("msg", "")
                else:
                    prog, msg = None, str(status)
                asset = task.get("asset") or {}
                if asset.get("stems"):
                    log(f"Task done: {label} ({time.time() - t0:.0f}s)")
                    return task
                if time.time() - t0 > 60 and int(time.time() - t0) % 30 < 5:
                    log(f"  ...still working ({msg or prog}) {time.time() - t0:.0f}s")
            if time.time() - t0 > 1800:
                die(f"Fadr task '{label}' timed out after 30 minutes.")
            time.sleep(5)

    def asset(self, asset_id):
        return self._check(self.s.get(f"{FADR_API}/assets/{asset_id}", timeout=60),
                           "get asset")["asset"]

    def download(self, asset_id, dest):
        j = self._check(self.s.get(f"{FADR_API}/assets/download/{asset_id}/hq",
                                   timeout=60), "presign download")
        with requests.get(j["url"], stream=True, timeout=600) as r:
            if r.status_code >= 400:
                die(f"Asset download failed (HTTP {r.status_code})")
            with open(dest, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        return dest


def stem_display_name(asset):
    """Fadr's name for what instrument a stem asset is. Field name may vary;
    check the likely spots and fall back to the file name."""
    md = asset.get("metadata") or {}
    for key in ("stemType", "stem", "type", "instrument"):
        v = md.get(key) or asset.get(key)
        if isinstance(v, str) and v and v not in ("stem",):
            return v.lower()
    return (asset.get("name") or "unknown").rsplit(".", 1)[0].lower()


def stage_fadr(job, job_dir, cfg, force):
    if job["stages"].get("fadr") and not force:
        log("Fadr stage already done — skipping.")
        return
    key = cfg.get("fadr_api_key", "")
    if not key or key.startswith("PASTE"):
        die("No Fadr API key in config. Create one at fadr.com (account -> API tab) "
            "and put it in tools/jamroom_import.config.json.")
    fadr = Fadr(key)
    stems_dir = job_dir / "stems"
    stems_dir.mkdir(exist_ok=True)
    raw_dump = {}

    src_asset = fadr.upload(job_dir / "source.wav")
    task = fadr.wait_task(fadr.stem_task(src_asset["_id"])["_id"], "main stem split")
    main_asset = fadr.asset(task["asset"]["_id"]) if task.get("asset") else None
    raw_dump["main_task"] = task
    raw_dump["main_asset"] = main_asset

    # Key / tempo / chords metadata lives on the analyzed asset.
    md = (main_asset or {}).get("metadata") or {}
    job["fadr"] = {"key": md.get("key"), "tempo": md.get("tempo"),
                   "asset_id": (main_asset or {}).get("_id")}

    # Collect first-level stems.
    stem_assets = []
    for sid in (main_asset or {}).get("stems", []):
        a = fadr.asset(sid)
        stem_assets.append(a)
    raw_dump["stem_assets"] = stem_assets

    # Optional sub-splits: vocals -> lead/bg, melodies -> instruments.
    final_stems = []
    for a in stem_assets:
        name = stem_display_name(a)
        if name in IGNORED_STEMS:
            continue
        split_type = None
        if name == "vocals" and cfg["vocal_split"]:
            split_type = "vocal-stem"
        elif name == "melodies" and cfg["melodic_split"]:
            split_type = "melodic-stem"
        if split_type:
            t = fadr.wait_task(fadr.stem_task(a["_id"], split_type)["_id"],
                               f"{name} sub-split")
            parent = fadr.asset(t["asset"]["_id"])
            raw_dump[f"{name}_split_asset"] = parent
            for sid in parent.get("stems", []):
                final_stems.append(fadr.asset(sid))
        else:
            final_stems.append(a)

    # Download stems and map to slots.
    slot_map = {k.lower(): v for k, v in cfg["slot_map"].items()}
    job["stems"], unmapped = [], []
    for a in final_stems:
        name = stem_display_name(a)
        if name in IGNORED_STEMS:
            continue
        fname = sanitize_filename(f"{name}.wav")
        log(f"Downloading stem: {name}")
        fadr.download(a["_id"], stems_dir / fname)
        slot = slot_map.get(name)
        entry = {"fadr_name": name, "file": f"stems/{fname}", "slot": slot}
        job["stems"].append(entry)
        if not slot:
            unmapped.append(name)
    if unmapped:
        log(f"WARNING: no slot mapping for stems: {unmapped} — they were "
            f"downloaded but will be skipped by the apply step until you add "
            f"them to slot_map in the config or job.json.")

    # Chords / MIDI: download everything the asset offers; parsing happens in
    # stage_chords once we know the real format (dumped to fadr_raw.json).
    midi_dir = job_dir / "fadr_midi"
    midi_dir.mkdir(exist_ok=True)
    for mid_id in (main_asset or {}).get("midi", []):
        try:
            a = fadr.asset(mid_id)
            fname = sanitize_filename(a.get("name") or f"{mid_id}.mid")
            fadr.download(mid_id, midi_dir / fname)
            log(f"Downloaded Fadr extra: {fname}")
        except SystemExit:
            raise
        except Exception as e:  # non-fatal: chords/midi are best-effort
            log(f"WARNING: could not download midi asset {mid_id}: {e}")

    with open(job_dir / "fadr_raw.json", "w", encoding="utf-8") as f:
        json.dump(raw_dump, f, indent=2, default=str)
    job["stages"]["fadr"] = True
    save_job(job_dir, job)
    log(f"Fadr stage complete: {len(job['stems'])} stems, "
        f"key={job['fadr']['key']} tempo={job['fadr']['tempo']}")


def stage_chords(job, job_dir, force):
    """Parse whatever chord data Fadr returned into job['chords'].
    Format is undocumented; we look for a chords .txt/.csv in fadr_midi/ and
    parse `start,end,chord`-ish lines. If nothing parses, leave empty and warn
    (fadr_raw.json + downloaded files remain for manual inspection)."""
    if job["stages"].get("chords") and not force:
        return
    chords = []
    for f in sorted((job_dir / "fadr_midi").glob("*")) if (job_dir / "fadr_midi").exists() else []:
        if "chord" not in f.name.lower() or f.suffix.lower() not in (".txt", ".csv"):
            continue
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\s*([\d.]+)\s*[,;\t]\s*([\d.]+)\s*[,;\t]\s*(\S+)", line)
            if m:
                chords.append({"start": float(m.group(1)), "end": float(m.group(2)),
                               "chord": m.group(3)})
        if chords:
            log(f"Parsed {len(chords)} chords from {f.name}")
            break
    if not chords:
        log("NOTE: no parseable chord file found from Fadr — check fadr_midi/ and "
            "fadr_raw.json; the chords track will be skipped by apply.")
    job["chords"] = chords
    job["stages"]["chords"] = True
    save_job(job_dir, job)


# ---------------------------------------------------------------- lyrics

def parse_lrc(lrc):
    """LRC text -> [{'time': seconds, 'text': str}], sorted, repeated-timestamp
    lines expanded."""
    out = []
    for line in lrc.splitlines():
        stamps = re.findall(r"\[(\d+):(\d+(?:\.\d+)?)\]", line)
        text = re.sub(r"\[[^\]]*\]", "", line).strip()
        for mm, ss in stamps:
            out.append({"time": round(int(mm) * 60 + float(ss), 3), "text": text})
    out.sort(key=lambda x: x["time"])
    return out


def stage_lyrics(job, job_dir, force):
    if job["stages"].get("lyrics") and not force:
        log("Lyrics stage already done — skipping.")
        return
    band, title, dur = job["band"], job["title"], round(job.get("duration") or 0)
    hdr = {"User-Agent": USER_AGENT}
    lyr = {"synced": False, "lines": [], "plain": "", "source": None}

    def try_get(params, what):
        try:
            r = requests.get(f"{LRCLIB_API}/get", params=params, headers=hdr, timeout=30)
            if r.status_code == 200:
                return r.json()
        except requests.RequestException as e:
            log(f"LRCLIB {what} request failed: {e}")
        return None

    log(f'Looking up synced lyrics on LRCLIB: "{band}" / "{title}" ({dur}s)')
    j = try_get({"artist_name": band, "track_name": title, "duration": dur},
                "exact") or None
    if not j:
        # search fallback: pick best duration match within ±4s
        try:
            r = requests.get(f"{LRCLIB_API}/search",
                             params={"artist_name": band, "track_name": title},
                             headers=hdr, timeout=30)
            cands = r.json() if r.status_code == 200 else []
        except requests.RequestException:
            cands = []
        cands = [c for c in cands
                 if abs((c.get("duration") or 0) - dur) <= 4 and
                 (c.get("syncedLyrics") or c.get("plainLyrics"))]
        cands.sort(key=lambda c: (not c.get("syncedLyrics"),
                                  abs((c.get("duration") or 0) - dur)))
        j = cands[0] if cands else None
    if j:
        if j.get("syncedLyrics"):
            lyr["synced"] = True
            lyr["lines"] = parse_lrc(j["syncedLyrics"])
            lyr["source"] = f"lrclib:{j.get('id')}"
            log(f"Found SYNCED lyrics ({len(lyr['lines'])} lines, "
                f"duration match {j.get('duration')}s vs ours {dur}s).")
        elif j.get("plainLyrics"):
            lyr["plain"] = j["plainLyrics"]
            lyr["source"] = f"lrclib:{j.get('id')}(plain)"
            log("Only PLAIN (unsynced) lyrics found — will import as one block; "
                "timing alignment is a later milestone.")
    else:
        log("No lyrics found on LRCLIB — lyrics track will be skipped by apply.")
    job["lyrics"] = lyr
    job["stages"]["lyrics"] = True
    save_job(job_dir, job)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Jam Room one-shot song import")
    ap.add_argument("query", help="YouTube URL, or search terms")
    ap.add_argument("--band", help="Band name (else guessed from video title)")
    ap.add_argument("--title", help="Song title (else guessed from video title)")
    ap.add_argument("--config", help="Path to config JSON")
    ap.add_argument("--yes", action="store_true",
                    help="Non-interactive: accept video + guessed names")
    ap.add_argument("--skip-fadr", action="store_true",
                    help="Skip stem separation (testing)")
    ap.add_argument("--skip-lyrics", action="store_true",
                    help="Skip lyrics lookup (testing)")
    for st in ("download", "fadr", "chords", "lyrics"):
        ap.add_argument(f"--force-{st}", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    url, video_title, uploader = resolve_input(args.query, args.yes)
    g_band, g_title = guess_band_title(video_title, uploader)
    band = args.band or g_band
    title = args.title or g_title
    if not args.yes and (not args.band or not args.title):
        print(f'\nGuessed:  Band = "{band}"   Song = "{title}"')
        b = input(f'Band  [{band}]: ').strip()
        t = input(f'Title [{title}]: ').strip()
        band, title = b or band, t or title
    band = sanitize_region_name(band)
    title = sanitize_region_name(title)

    job_dir = Path(cfg["jobs_dir"]) / sanitize_filename(f"{band} - {title}")
    job = load_job(job_dir)
    job.update({"band": band, "title": title,
                "region_name": f"{band} - {title}"})
    job.setdefault("source", {})
    job["source"].update({"youtube_url": url, "video_title": video_title})
    save_job(job_dir, job)
    log(f"Job folder: {job_dir}")

    stage_download(job, job_dir, url, args.force_download)
    if not args.skip_fadr:
        stage_fadr(job, job_dir, cfg, args.force_fadr)
        stage_chords(job, job_dir, args.force_chords)
    if not args.skip_lyrics:
        stage_lyrics(job, job_dir, args.force_lyrics)

    log("")
    log(f"DONE. Job ready: {job_dir / 'job.json'}")
    log(f"  region: {job['region_name']}")
    log(f"  stems:  {len(job.get('stems', []))} "
        f"({', '.join(s['fadr_name'] for s in job.get('stems', []))})")
    log(f"  chords: {len(job.get('chords', []))} segments")
    ly = job.get("lyrics", {})
    log(f"  lyrics: {'synced, ' + str(len(ly.get('lines', []))) + ' lines' if ly.get('synced') else ('plain only' if ly.get('plain') else 'none')}")
    log("Next: run tools/jamroom_import_apply.lua in REAPER (or let this tool "
        "trigger it once M4b lands).")


if __name__ == "__main__":
    main()
