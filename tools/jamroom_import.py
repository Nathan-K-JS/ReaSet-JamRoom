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
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

# Stamped into the CODE, so it reports what is actually running rather than
# what is on disk — the importer server holds its modules in memory, so this is
# how you tell "did the update take effect?" from "is the old process still up?"
# BUMP THIS whenever the importer changes, and quote it when handing over.
BUILD = "v1.7"
BUILD_DATE = "2026-08-22"

# Fadr's S3 throttles each connection independently, so several transfers at
# once finish far sooner than one at a time. Overridable via config.
DOWNLOAD_WORKERS = 4

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = Path(__file__).resolve().parent / "jamroom_import.config.json"
FADR_API = "https://api.fadr.com"
LRCLIB_API = "https://lrclib.net/api"
USER_AGENT = "ReaSet-JamRoom-Import/0.1 (https://github.com/; rehearsal tooling)"

# Default Fadr stemType -> Jam Room slot mapping (keys normalized: lowercase,
# '-'/'_' become spaces). Verified against real API responses 2026-08-16:
# main split yields stemTypes vocals/drums/bass/other (+instrumental).
# Slots: DRUMS PERC_FX BASS GTR1 GTR2 KEYS BVS LEAD_VOX CLICK EXTRA
DEFAULT_SLOT_MAP = {
    "drums": "DRUMS",
    "bass": "BASS",
    "vocals": "LEAD_VOX",          # used when vocal sub-split is off
    "other": "KEYS",               # melodic remainder, when melodic split off
    # sub-split outputs (real stemTypes verified live 2026-08-16):
    "vocals lead": "LEAD_VOX",
    "vocals background": "BVS",
    "electric": "GTR1",
    "acoustic": "GTR2",
    "piano": "KEYS",
    "strings": "EXTRA",
    "wind": "EXTRA",
    "melodics other": "EXTRA",
    # never imported: "instrumental" (it's just the sum of the others)
}
IGNORED_STEMS = {"instrumental"}


def norm_stem_type(s):
    return re.sub(r"\s+", " ", str(s).lower().replace("-", " ").replace("_", " ")).strip()

# Label musicians see on auto-created "[JR:SLOT] Label" buses. Overridable.
DEFAULT_SLOT_LABELS = {
    "DRUMS": "Drums", "PERC_FX": "Perc/FX", "BASS": "Bass",
    "GTR1": "Guitar 1", "GTR2": "Guitar 2", "KEYS": "Keys",
    "BVS": "Backing Vocals", "LEAD_VOX": "Lead Vocals",
    "CLICK": "Click", "EXTRA": "Extras",
}


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
    cfg.setdefault("slot_labels", DEFAULT_SLOT_LABELS)
    cfg.setdefault("vocal_split", True)
    cfg.setdefault("melodic_split", True)
    cfg.setdefault("jobs_dir", str(REPO_ROOT / "imports"))
    cfg.setdefault("reaper_exe", "C:/Program Files/REAPER (x64)/reaper.exe")
    cfg.setdefault("reaper_web", "http://localhost:8080")
    cfg.setdefault("auto_apply", True)
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

# YouTube breaks extraction periodically (403s, the SABR rollout, ...), and the
# fix moves around: an explicit player client that rescues one video can be the
# very thing that breaks the next. yt-dlp's own defaults are the best-maintained
# path, so try those first and fall back to specific clients only if needed.
YTDLP_CLIENTS = [
    None,                                        # yt-dlp defaults
    "youtube:player_client=default,web_safari",
    "youtube:player_client=default,android",
    "youtube:player_client=ios",
]


def _ytdlp_download(out, url, extractor_args):
    args = ["--no-playlist", "-f", "bestaudio", "-x", "--audio-format", "wav",
            "--write-info-json", "-o", str(out)]
    if extractor_args:
        args += ["--extractor-args", extractor_args]
    args.append(url)
    return run_ytdlp(args)


def _download_any_client(out, url, wav):
    """Try each client config until one produces the WAV."""
    last = None
    for cfg in YTDLP_CLIENTS:
        wav.unlink(missing_ok=True)
        r = _ytdlp_download(out, url, cfg)
        if r.returncode == 0 and wav.exists():
            return True, r
        last = r
        log(f"  ...no luck with {cfg or 'yt-dlp defaults'}, trying the next method")
    return False, last


def job_from_existing_asset(cfg, asset_id, band, title, duration):
    """Prepare a job that reuses an already-split Fadr asset: no YouTube
    download, no upload, no split task — and therefore no charge."""
    band = sanitize_region_name(band)
    title = sanitize_region_name(title)
    if not band or not title:
        die("Band and song title are both required.")
    job_dir = Path(cfg["jobs_dir"]) / sanitize_filename(f"{band} - {title}")
    job = load_job(job_dir)
    job.update({"band": band, "title": title,
                "region_name": f"{band} - {title}",
                "duration": float(duration or 0)})
    job.setdefault("source", {})["from_fadr_library"] = asset_id
    job.setdefault("fadr", {})["asset_id"] = asset_id
    job["stages"]["download"] = True          # there is nothing to download
    job["stages"].pop("fadr", None)           # re-collect stems from the asset
    save_job(job_dir, job)
    return job_dir, job


def stage_download(job, job_dir, url, force):
    if job["stages"].get("download") and not force:
        log("Download stage already done — skipping.")
        return
    log("Downloading best-quality audio (yt-dlp -> WAV)...")
    out = job_dir / "source.%(ext)s"
    wav = job_dir / "source.wav"
    ok, last = _download_any_client(out, url, wav)
    if not ok:
        # Nine times out of ten the real problem is that yt-dlp itself is out of
        # date — YouTube changes something and yt-dlp ships a fix within days.
        log("Every download method failed. Updating yt-dlp and retrying once...")
        upd = run_ytdlp(["-U"])
        tail = (upd.stdout or upd.stderr or "").strip().splitlines()
        if tail:
            log("  " + tail[-1])
        ok, last = _download_any_client(out, url, wav)
    if not ok:
        die("Download failed with every method, even after updating yt-dlp.\n"
            "YouTube may have changed something yt-dlp cannot handle yet — try\n"
            "again later, or pick a different upload of the song.\n\n"
            + ((last.stderr or "")[-1200:] if last else ""))
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
        # requests.Session is not guaranteed thread-safe; downloads run in
        # parallel, so guard the shared session. The bulk transfer itself uses
        # a standalone request and needs no lock.
        self._lock = threading.Lock()

    def _check(self, r, what):
        if r.status_code >= 400:
            die(f"Fadr {what} failed (HTTP {r.status_code}): {r.text[:800]}")
        return r.json()

    def upload(self, path, display_name=None):
        # Name the upload after the song, not "source.wav" — this is what shows
        # in the Fadr library, and it is how an already-paid-for split is found
        # again later instead of being re-uploaded and re-charged.
        name = sanitize_filename(display_name or path.name)
        if not name.lower().endswith(".wav"):
            name += ".wav"
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

    def wait_asset_midi(self, asset_id, budget=600):
        """The chord/MIDI analysis finishes AFTER the stems, on the same asset.
        Returns the asset once .midi is populated, or None if it never is."""
        t0 = time.time()
        while time.time() - t0 < budget:
            a = self.asset(asset_id)
            if a.get("midi"):
                log(f"Chord/MIDI analysis ready ({time.time() - t0:.0f}s).")
                return a
            waited = time.time() - t0
            if waited > 15 and int(waited) % 30 < 5:
                log(f"  ...still waiting for chord/MIDI analysis ({waited:.0f}s)")
            time.sleep(5)
        return None

    def asset(self, asset_id):
        return self._check(self.s.get(f"{FADR_API}/assets/{asset_id}", timeout=60),
                           "get asset")["asset"]

    def download(self, asset_id, dest, label=""):
        """Download with visible progress, and RESUME after a stall.

        Fadr's S3 storage regularly stalls part-way through a stem. Restarting
        from zero could loop forever on a slow link, so each attempt resumes
        from the bytes already on disk via a Range request. Progress is logged
        so a slow transfer is visibly moving rather than looking like a hang."""
        label = label or Path(dest).name
        dest = Path(dest)
        part = dest.with_name(dest.name + ".part")
        part.unlink(missing_ok=True)          # always start a fresh transfer
        attempts, total = 8, 0
        # Fadr's S3 bucket throttles unpredictably: the same file measured
        # 1900, then 89, then 2000 KB/s minutes apart. A degraded connection
        # never trips the read timeout, it just crawls, so watch the rate and
        # reconnect — a fresh connection usually gets a healthy path, and the
        # resume logic below means nothing already transferred is lost.
        SLOW_KBPS, SLOW_WINDOW = 150, 10
        for attempt in range(1, attempts + 1):
            try:
                # Presigned URLs are short-lived, so mint a fresh one each try.
                with self._lock:
                    j = self._check(
                        self.s.get(f"{FADR_API}/assets/download/{asset_id}/hq",
                                   timeout=30), "presign download")
                have = part.stat().st_size if part.exists() else 0
                headers = {"Range": f"bytes={have}-"} if have else {}
                # (connect, read) — a stall raises after 45s instead of hanging
                with requests.get(j["url"], stream=True, timeout=(15, 45),
                                  headers=headers) as r:
                    if r.status_code == 416:          # already have all of it
                        break
                    if r.status_code >= 400:
                        raise requests.RequestException(f"HTTP {r.status_code}")
                    resuming = (r.status_code == 206 and have > 0)
                    if not resuming:
                        have = 0
                        part.unlink(missing_ok=True)
                    body = int(r.headers.get("Content-Length") or 0)
                    if body:
                        total = have + body
                    got, last = have, time.time()
                    win_t, win_b = time.time(), 0
                    with open(part, "ab" if resuming else "wb") as f:
                        for chunk in r.iter_content(1 << 16):
                            f.write(chunk)
                            got += len(chunk)
                            win_b += len(chunk)
                            now = time.time()
                            if now - last >= 3:
                                last = now
                                pct = f"{got * 100 // total}% " if total else ""
                                rate = win_b / max(now - win_t, 0.001) / 1024
                                log(f"    {label}: {pct}({got / 1e6:.1f} MB, "
                                    f"{rate:.0f} KB/s)")
                            # Chase a faster connection for the first few
                            # attempts; after that take whatever we are given,
                            # because a slow download still beats a failed one.
                            if now - win_t >= SLOW_WINDOW and attempt <= 4:
                                rate = win_b / (now - win_t) / 1024
                                if rate < SLOW_KBPS:
                                    raise requests.RequestException(
                                        f"throttled to {rate:.0f} KB/s")
                                win_t, win_b = now, 0
                if total and part.stat().st_size < total:
                    raise requests.RequestException("incomplete transfer")
                break
            except (requests.RequestException, OSError) as e:
                sofar = part.stat().st_size if part.exists() else 0
                if attempt == attempts:
                    die(f"Could not download {label} after {attempts} attempts "
                        f"({sofar / 1e6:.1f} MB of {total / 1e6:.1f} MB): {e}")
                log(f"    {label}: reconnecting at {sofar / 1e6:.1f} MB "
                    f"({e}) — attempt {attempt + 1} of {attempts}")
                time.sleep(2)
        dest.unlink(missing_ok=True)
        part.replace(dest)
        return dest


def known_asset_names(cfg):
    """asset_id -> "Band - Song", learned from jobs imported on this machine.
    Older uploads were all called "source.wav" on Fadr, so this is what makes
    them identifiable in the library list."""
    out = {}
    jobs = Path(cfg.get("jobs_dir") or (REPO_ROOT / "imports"))
    if not jobs.is_dir():
        return out
    for jf in jobs.glob("*/job.json"):
        try:
            j = json.loads(jf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        aid = (j.get("fadr") or {}).get("asset_id")
        if aid and j.get("region_name"):
            out[aid] = j["region_name"]
    return out


def fadr_library(cfg):
    """Every already-split song on the Fadr account, newest first.

    Uses GET /assets — undocumented, but it is the only way to find work you
    have already paid to split. Only 'upload' assets are songs; the rest are
    the stems and analysis hanging off them.
    """
    key = cfg.get("fadr_api_key", "")
    if not key or key.startswith("PASTE"):
        die("No Fadr API key in config.")
    fadr = Fadr(key)
    r = fadr._check(fadr.s.get(f"{FADR_API}/assets", timeout=60), "list assets")
    all_assets = r.get("assets") or []
    by_id = {a.get("_id"): a for a in all_assets}
    known = known_asset_names(cfg)
    out = []
    for a in all_assets:
        if a.get("assetType") != "upload" or a.get("deleted"):
            continue
        md = a.get("metaData") or {}
        rate = md.get("sampleRate") or 44100
        length = md.get("length") or 0
        aid = a.get("_id")
        raw = (a.get("name") or "").rsplit(".", 1)[0]
        # Are the vocal/melodic sub-splits already done? If not, importing with
        # splits enabled creates them, and THAT is billable — so the UI must not
        # promise "free". The stem children are in this same listing, so this
        # costs no extra API calls.
        subs_done = 0
        for sid in a.get("stems") or []:
            child = by_id.get(sid) or {}
            st = norm_stem_type((child.get("metaData") or {}).get("stemType") or "")
            if st in ("vocals", "other") and (child.get("stems") or []):
                subs_done += 1
        out.append({
            "id": aid,
            # Prefer the name we recorded locally: early uploads are all
            # called "source.wav" on Fadr and cannot be told apart otherwise.
            "name": known.get(aid) or raw,
            "fadr_name": raw,
            "named_locally": aid in known,
            "stems": len(a.get("stems") or []),
            "subsplits_done": subs_done,       # 2 == nothing left to pay for
            "has_chords": bool(a.get("midi")),
            "key": md.get("key"), "tempo": md.get("tempo"),
            "duration": round(length / rate, 1) if rate else 0,
            "created": (a.get("createdTimestamp") or "")[:10],
        })
    out.sort(key=lambda x: x["created"], reverse=True)
    return out


def stem_display_name(asset):
    """What instrument a stem asset is: metaData.stemType (verified real field),
    falling back to the name suffix Fadr appends ('source.wav-vocals')."""
    md = asset.get("metaData") or {}
    v = md.get("stemType")
    if isinstance(v, str) and v:
        return norm_stem_type(v)
    name = asset.get("name") or "unknown"
    return norm_stem_type(name.rsplit("-", 1)[-1]) if "-" in name else name.lower()


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

    # Reuse an already-processed upload when we have one (protects credit:
    # re-runs after a tool fix never pay for upload + main split again).
    main_asset = None
    prev_id = (job.get("fadr") or {}).get("asset_id")
    if prev_id:
        try:
            a = fadr.asset(prev_id)
            if a.get("stems"):
                log(f"Reusing existing Fadr asset {prev_id} (no re-upload).")
                main_asset = a
        except SystemExit:
            raise
    if main_asset is None:
        src_asset = fadr.upload(job_dir / "source.wav",
                                display_name=job.get("region_name"))
        task = fadr.wait_task(fadr.stem_task(src_asset["_id"])["_id"],
                              "main stem split")
        main_asset = fadr.asset(task["asset"]["_id"])
    # Record the asset id straight away: if anything later fails, a re-run then
    # reuses this asset instead of paying to upload and split all over again.
    job.setdefault("fadr", {})["asset_id"] = main_asset.get("_id")
    save_job(job_dir, job)

    # NOTE: the chord/MIDI analysis runs after the stems and is collected at the
    # END of this function — the sub-splits and downloads below give it several
    # minutes of cover, instead of us blocking on it here.

    # Collect first-level stems.
    stem_assets = [fadr.asset(sid) for sid in main_asset.get("stems", [])]
    raw_dump["stem_assets"] = stem_assets

    # Optional sub-splits: vocals -> lead/bg, "other" (melodic) -> instruments.
    final_stems = []
    for a in stem_assets:
        name = stem_display_name(a)
        if name in IGNORED_STEMS:
            continue
        split_type = None
        if name == "vocals" and cfg["vocal_split"]:
            split_type = "vocal-stem"
        elif name == "other" and cfg["melodic_split"]:
            split_type = "melodic-stem"
        if split_type:
            # A sub-split already performed on this stem stays attached to it
            # (verified), so re-running an import never pays for it twice.
            existing = a.get("stems") or []
            if existing:
                log(f"Reusing the existing {name} sub-split (no new charge).")
                parent = a
            else:
                t = fadr.wait_task(fadr.stem_task(a["_id"], split_type)["_id"],
                                   f"{name} sub-split")
                parent = fadr.asset(t["asset"]["_id"])
            raw_dump[f"{name}_split_asset"] = parent
            children = [fadr.asset(sid) for sid in parent.get("stems", [])]
            raw_dump[f"{name}_split_children"] = children
            final_stems.extend(children)
        else:
            final_stems.append(a)

    # Download stems in parallel — Fadr throttles per connection, so several at
    # once is dramatically faster than one at a time, and each has its own
    # watchdog and resume.
    slot_map = {norm_stem_type(k): v for k, v in cfg["slot_map"].items()}
    wanted, seen = [], {}
    for a in final_stems:
        name = stem_display_name(a)
        if name in IGNORED_STEMS:
            continue
        seen[name] = seen.get(name, 0) + 1
        base = name if seen[name] == 1 else f"{name}-{seen[name]}"
        wanted.append((a, name, base))

    workers = max(1, min(int(cfg.get("download_workers", DOWNLOAD_WORKERS)),
                         len(wanted) or 1))
    log(f"Downloading {len(wanted)} stems, {workers} at a time...")
    results = [None] * len(wanted)
    done = {"n": 0}

    def fetch(i):
        a, name, base = wanted[i]
        fname = sanitize_filename(f"{base}.wav")
        fadr.download(a["_id"], stems_dir / fname, label=base)
        wav = ensure_riff_wav(stems_dir / fname)
        results[i] = {"fadr_name": name, "file": f"stems/{wav.name}",
                      "slot": slot_map.get(name)}
        done["n"] += 1
        log(f"  [{done['n']} of {len(wanted)}] {base} done")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(fetch, range(len(wanted))))   # re-raises worker failures

    job["stems"] = [r for r in results if r]
    unmapped = [r["fadr_name"] for r in job["stems"] if not r["slot"]]
    if unmapped:
        log(f"WARNING: no slot mapping for stems: {unmapped} — they were "
            f"downloaded but will be skipped by the apply step until you add "
            f"them to slot_map in the config or job.json.")

    # Now collect the chord/MIDI analysis. By this point the sub-splits and the
    # stem downloads have given Fadr several minutes to finish it.
    if not main_asset.get("midi"):
        ready = fadr.wait_asset_midi(main_asset["_id"], budget=600)
        if ready:
            main_asset = ready
    raw_dump["main_asset"] = main_asset

    md = main_asset.get("metaData") or {}
    job["fadr"].update({
        "key": md.get("key"), "tempo": md.get("tempo"),
        "sample_rate": md.get("sampleRate"),
        "beat_length_samples": md.get("beatLength"),
        "beat_offset_samples": md.get("offset"),
    })

    if not main_asset.get("midi"):
        log("WARNING: Fadr has still not produced the chord analysis for this "
            "song. The stems are fine, but there will be no chords. Run the "
            "import again for this song later to collect them — the upload and "
            "the split are reused, so it costs nothing.")

    # Chords + MIDI assets, typed by assetType (verified live):
    #   chord-csv -> chords.csv, chord-midi -> chords.mid,
    #   stem-midi -> <stemtype>.mid
    midi_dir = job_dir / "fadr_midi"
    midi_dir.mkdir(exist_ok=True)
    for mid_id in main_asset.get("midi", []):
        try:
            a = fadr.asset(mid_id)
            at = a.get("assetType") or ""
            if at == "chord-csv":
                fname = "chords.csv"
            elif at == "chord-midi":
                fname = "chords.mid"
            else:
                suffix = (a.get("name") or mid_id).rsplit("-", 1)[-1]
                fname = sanitize_filename(f"{suffix}.mid")
            fadr.download(mid_id, midi_dir / fname, label=fname)
            log(f"Downloaded Fadr analysis: {fname}")
        # Best-effort: losing a chord file must not throw away a good import.
        # (die() raises SystemExit on the CLI and RuntimeError under the web UI,
        # so both are caught here deliberately.)
        except (Exception, SystemExit) as e:
            log(f"WARNING: could not download analysis asset {mid_id}: {e}")

    with open(job_dir / "fadr_raw.json", "w", encoding="utf-8") as f:
        json.dump(raw_dump, f, indent=2, default=str)
    job["stages"]["fadr"] = True
    save_job(job_dir, job)
    log(f"Fadr stage complete: {len(job['stems'])} stems, "
        f"key={job['fadr']['key']} tempo={job['fadr']['tempo']}")


# Fadr chord qualities ("F:maj", "A:min", ...) -> musician-friendly names.
CHORD_QUALITY = {
    "maj": "", "min": "m", "7": "7", "maj7": "maj7", "min7": "m7",
    "dim": "dim", "dim7": "dim7", "aug": "aug", "sus2": "sus2", "sus4": "sus4",
    "min6": "m6", "maj6": "6", "hdim7": "m7b5", "minmaj7": "mMaj7",
}


def pretty_chord(raw):
    if ":" not in raw:
        return raw
    root, qual = raw.split(":", 1)
    return root + CHORD_QUALITY.get(qual, qual)


def stage_chords(job, job_dir, force):
    """Parse Fadr's chords.csv (verified live format: header `chord,start,end`,
    times in seconds). Small inter-chord gaps are healed to the next chord's
    start (no flicker to blank) and consecutive identical chords merged."""
    if job["stages"].get("chords") and not force:
        return
    import csv as csvmod
    chords = []
    f = job_dir / "fadr_midi" / "chords.csv"
    if f.exists():
        with open(f, encoding="utf-8", errors="replace", newline="") as fh:
            for row in csvmod.DictReader(fh):
                try:
                    chords.append({"start": float(row["start"]),
                                   "end": float(row["end"]),
                                   "chord": pretty_chord(row["chord"].strip())})
                except (KeyError, ValueError):
                    continue
    chords.sort(key=lambda c: c["start"])
    merged = []
    for c in chords:
        if merged and merged[-1]["chord"] == c["chord"] and \
                c["start"] - merged[-1]["end"] <= 1.0:
            merged[-1]["end"] = c["end"]
        else:
            if merged and 0 < c["start"] - merged[-1]["end"] <= 1.0:
                merged[-1]["end"] = c["start"]     # heal the gap
            merged.append(dict(c))
    if merged:
        log(f"Parsed {len(chords)} chord segments -> {len(merged)} items "
            f"(gaps healed, repeats merged).")
    else:
        log("NOTE: no parseable chords.csv from Fadr — the chords track will "
            "be skipped by apply.")
    job["chords"] = merged
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


def lyrics_search(artist="", title="", free=""):
    """Candidate lyric records from LRCLIB for the operator to choose between.

    The automatic lookup matches on artist+title+duration and gives up when the
    song is filed under a slightly different name — this is the manual way in.
    """
    hdr = {"User-Agent": USER_AGENT}
    params = {"q": free} if free else {"artist_name": artist, "track_name": title}
    try:
        r = requests.get(f"{LRCLIB_API}/search", params=params, headers=hdr,
                         timeout=30)
        rows = r.json() if r.status_code == 200 else []
    except (requests.RequestException, ValueError) as e:
        raise RuntimeError(f"Could not reach the lyrics database: {e}")
    out = []
    for c in rows[:40]:
        synced = c.get("syncedLyrics") or ""
        out.append({
            "id": c.get("id"),
            "artist": c.get("artistName") or "",
            "title": c.get("trackName") or "",
            "album": c.get("albumName") or "",
            "duration": round(c.get("duration") or 0),
            "synced": bool(synced),
            "plain": bool(c.get("plainLyrics")),
            "lines": len([l for l in synced.splitlines() if l.strip()]),
        })
    # Timed lyrics first, then the ones with the most lines.
    out.sort(key=lambda c: (not c["synced"], -c["lines"]))
    return out


def lyrics_use_record(job, job_dir, record_id):
    """Adopt a specific LRCLIB record chosen by the operator."""
    hdr = {"User-Agent": USER_AGENT}
    try:
        r = requests.get(f"{LRCLIB_API}/get/{int(record_id)}", headers=hdr, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"lyrics record {record_id} not available "
                               f"(HTTP {r.status_code})")
        rec = r.json()
    except (requests.RequestException, ValueError) as e:
        raise RuntimeError(f"Could not fetch those lyrics: {e}")
    lyr = {"synced": False, "lines": [], "plain": "",
           "source": f"lrclib:{rec.get('id')} (chosen by hand)"}
    if rec.get("syncedLyrics"):
        lyr["synced"] = True
        lyr["lines"] = parse_lrc(rec["syncedLyrics"])
    elif rec.get("plainLyrics"):
        lyr["plain"] = rec["plainLyrics"]
    job["lyrics"] = lyr
    job["stages"]["lyrics"] = True
    save_job(job_dir, job)
    log(f"Using lyrics: {rec.get('artistName')} - {rec.get('trackName')} "
        f"({'synced, ' + str(len(lyr['lines'])) + ' lines' if lyr['synced'] else 'plain text'})")
    # Re-check the timing against the vocal stem for the new lyrics.
    stage_lyrics_align(job, job_dir, True)
    return lyr


# ── Ultimate Guitar: chord charts ────────────────────────────────────────────
# Only CHORD SYMBOLS and the key are read from a chart. The lyric text on those
# pages is not ours to copy — lyrics come from LRCLIB, which is built for it.
UG_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0 Safari/537.36"}


def _ug_page_data(url):
    import html as _html
    r = requests.get(url, headers=UG_UA, timeout=25)
    if r.status_code != 200:
        raise RuntimeError(f"Ultimate Guitar returned HTTP {r.status_code}")
    m = re.search(r'<div[^>]+data-content="([^"]+)"', r.text)
    if not m:
        raise RuntimeError("Could not read that Ultimate Guitar page")
    return json.loads(_html.unescape(m.group(1)))


def ug_search(artist, title):
    """Chord charts for a song, best-rated first."""
    q = requests.utils.quote(f"{artist} {title}".strip())
    data = _ug_page_data("https://www.ultimate-guitar.com/search.php"
                         f"?search_type=title&value={q}")
    results = (data.get("store", {}).get("page", {}).get("data", {})
                   .get("results") or [])
    out = []
    for r in results:
        if str(r.get("type", "")).lower() != "chords":
            continue
        url = r.get("tab_url") or ""
        if "tabs.ultimate-guitar.com" not in url:
            continue
        out.append({
            "url": url,
            "artist": r.get("artist_name") or "",
            "title": r.get("song_name") or "",
            "rating": round(float(r.get("rating") or 0), 2),
            "votes": int(r.get("votes") or 0),
            "version": r.get("version"),
        })
    out.sort(key=lambda c: (-c["votes"], -c["rating"]))
    return out[:20]


def ug_chart_vocabulary(url, detected_key=None):
    """The chord symbols a chart uses, corrected for CAPO.

    A capo'd chart prints the SHAPES the guitarist fingers, not the pitches the
    audience hears: with a capo at 3, a printed 'Am' sounds as 'Cm'. Fadr's
    chords come from the recording, so they are sounding pitches. Everything
    below is therefore converted to sounding pitch before being compared to or
    substituted into the detected chords — otherwise a capo'd chart would
    rename every chord wrongly.
    """
    data = _ug_page_data(url)
    page = data.get("store", {}).get("page", {}).get("data", {})
    content = ((page.get("tab_view") or {}).get("wiki_tab") or {}).get("content") or ""
    chords = re.findall(r"\[ch\]([^\[]+)\[/ch\]", content)
    seen, shapes, counts = set(), [], {}
    for c in chords:
        c = c.strip()
        if not c:
            continue
        counts[c] = counts.get(c, 0) + 1
        if c not in seen:
            seen.add(c)
            shapes.append(c)
    try:
        capo = int((page.get("tab_view") or {}).get("capo") or 0)
    except (TypeError, ValueError):
        capo = 0
    shape_key = (page.get("tab") or {}).get("tonality_name") or ""
    sounding = [transpose_chord(c, capo) for c in shapes]
    sounding_key = transpose_chord(shape_key, capo) if shape_key else ""
    # How often each SOUNDING chord appears, used to break ties when forcing a
    # badly-detected chord onto the chart's vocabulary.
    sounding_counts = {}
    for shape, snd in zip(shapes, sounding):
        sounding_counts[snd] = sounding_counts.get(snd, 0) + counts.get(shape, 1)

    return {
        "url": url,
        "vocab": sounding,          # sounding pitches: comparable with Fadr
        "shapes": shapes,           # what the chart actually prints
        "capo": capo,
        "count": len(chords),
        "key": sounding_key,
        "shape_key": shape_key,
        "counts": sounding_counts,
        "detected_key": detected_key or "",
    }


def ug_chart_sequence(url):
    """The chart's chords AS PRINTED, in order, corrected for capo.

    This is the musical truth: a real player's transcription, containing only
    actual chord changes. Fadr, by contrast, reports a chord for every harmonic
    event including passing notes and lead lines, which is why its charts are
    cluttered. Here we keep the chart's sequence intact and use Fadr only to
    place it in time (see chords_from_chart).
    """
    data = _ug_page_data(url)
    page = data.get("store", {}).get("page", {}).get("data", {})
    content = ((page.get("tab_view") or {}).get("wiki_tab") or {}).get("content") or ""
    try:
        capo = int((page.get("tab_view") or {}).get("capo") or 0)
    except (TypeError, ValueError):
        capo = 0

    seq = []
    for line in content.replace("\r\n", "\n").split("\n"):
        # Section headers carry no chords; skip so they cannot pollute the run.
        if re.match(r"^\s*\[?\s*(intro|verse|chorus|bridge|outro|solo|"
                    r"pre-?chorus|interlude|instrumental|refrain|coda)",
                    re.sub(r"\[/?ch\]", "", line), re.I):
            continue
        for c in re.findall(r"\[ch\]([^\[]+)\[/ch\]", line):
            c = c.strip()
            if c:
                seq.append(transpose_chord(c, capo))
    return {"sequence": seq, "capo": capo, "url": url,
            "key": transpose_chord((page.get("tab") or {}).get("tonality_name") or "", capo)}


def _collapse_detected(chords, min_len=0.35):
    """Fadr's stream reduced to plausible chord CHANGES: merge runs of the same
    chord, and drop blips too short to be a real change (passing notes)."""
    merged = []
    for c in chords:
        name = c.get("chord")
        s, e = float(c["start"]), float(c["end"])
        if merged and merged[-1]["chord"] == name:
            merged[-1]["end"] = max(merged[-1]["end"], e)
        else:
            merged.append({"chord": name, "start": s, "end": e})
    kept = [c for c in merged if (c["end"] - c["start"]) >= min_len]
    # Re-merge in case dropping a blip joined two identical neighbours.
    out = []
    for c in kept:
        if out and out[-1]["chord"] == c["chord"]:
            out[-1]["end"] = c["end"]
        else:
            out.append(dict(c))
    return out


def _align(seq_a, seq_b):
    """Needleman-Wunsch alignment of two chord sequences.

    Returns pairs (i, j) where i indexes seq_a and j indexes seq_b, or None for
    a gap. Scoring rewards an exact chord match most, a shared root next; gaps
    are cheap because the two sources legitimately differ in density.
    """
    GAP = -1.0

    def score(a, b):
        if a == b:
            return 3.0
        ra = _root_index(_chord_parts(a)[0])
        rb = _root_index(_chord_parts(b)[0])
        if ra is not None and ra == rb:
            return 2.0
        return -2.0

    n, m = len(seq_a), len(seq_b)
    if not n or not m:
        return []
    # Score matrix
    F = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        F[i][0] = F[i - 1][0] + GAP
    for j in range(1, m + 1):
        F[0][j] = F[0][j - 1] + GAP
    for i in range(1, n + 1):
        ai = seq_a[i - 1]
        Fi, Fp = F[i], F[i - 1]
        for j in range(1, m + 1):
            Fi[j] = max(Fp[j - 1] + score(ai, seq_b[j - 1]),
                        Fp[j] + GAP, Fi[j - 1] + GAP)
    # Traceback
    pairs, i, j = [], n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and abs(F[i][j] - (F[i - 1][j - 1]
                                 + score(seq_a[i - 1], seq_b[j - 1]))) < 1e-9:
            pairs.append((i - 1, j - 1)); i -= 1; j -= 1
        elif i > 0 and abs(F[i][j] - (F[i - 1][j] + GAP)) < 1e-9:
            pairs.append((i - 1, None)); i -= 1
        else:
            pairs.append((None, j - 1)); j -= 1
    pairs.reverse()
    return pairs


def _best_chart_offset(detected, seq):
    """How far the chart is transposed from the recording, in semitones.

    Charts are routinely written in a friendlier key than the record - a
    semitone down for Misery Business, for example - and a capo field does not
    always say so. Comparing roots without correcting for that makes every
    match fail. Each of the twelve offsets is scored by how much of the song's
    DURATION lands on a chord root the transposed chart actually plays, so a
    brief wrong guess cannot outvote the real key.
    """
    chart_roots = set()
    for c in seq:
        i = _root_index(_chord_parts(c)[0])
        if i is not None:
            chart_roots.add(i)
    if not chart_roots or not detected:
        return 0, 0.0
    weights = {}
    total = 0.0
    for d in detected:
        i = _root_index(_chord_parts(d["chord"])[0])
        if i is None:
            continue
        w = max(0.0, float(d["end"]) - float(d["start"]))
        weights[i] = weights.get(i, 0.0) + w
        total += w
    if total <= 0:
        return 0, 0.0
    best_off, best_score = 0, -1.0
    for off in range(12):
        moved = {(r + off) % 12 for r in chart_roots}
        score = sum(w for pc, w in weights.items() if pc in moved)
        if score > best_score:
            best_off, best_score = off, score
    return best_off, best_score / total


def chords_from_chart(job, url, min_len=0.35):
    """Build a chord list that shows the CHART's chords, timed from the audio.

    The chart supplies which chords exist and in what order; the detected
    stream supplies when things change. Chart chords that align to a detected
    change take its time; the rest are spread evenly between their anchored
    neighbours, so nothing is invented and nothing is dropped.
    """
    chart = ug_chart_sequence(url)
    seq = chart["sequence"]
    detected = _collapse_detected(job.get("chords") or [], min_len)
    if not seq:
        raise RuntimeError("That chart contains no chord symbols.")
    if not detected:
        raise RuntimeError("This song has no detected chord timing to anchor to.")

    # Put the chart into the recording's key before trying to match anything.
    offset, fit = _best_chart_offset(detected, seq)
    if offset:
        seq = [transpose_chord(c, offset) for c in seq]

    det_names = [d["chord"] for d in detected]
    pairs = _align(seq, det_names)

    # Anchor times for chart chords that matched something detected.
    anchored = {}
    for i, j in pairs:
        if i is not None and j is not None and i not in anchored:
            anchored[i] = detected[j]["start"]

    song_end = max(d["end"] for d in detected)
    times = [anchored.get(i) for i in range(len(seq))]

    # Fill unanchored chords by spreading them between known anchors, so an
    # unmatched run still lands in musically sensible places.
    first = next((k for k, t in enumerate(times) if t is not None), None)
    if first is None:
        raise RuntimeError("The chart could not be matched to this recording at "
                           "all - it is probably a different arrangement.")
    last = max(k for k, t in enumerate(times) if t is not None)
    # Chords ahead of the first anchor (a chart intro the detector missed) get
    # real room rather than being stacked into a millisecond each.
    if first > 0:
        anchor_t = times[first]
        room = min(anchor_t, first * 1.5)
        step = room / first if first else 0
        for k in range(first):
            times[k] = max(0.0, anchor_t - (first - k) * step)
    prev = first
    for k in range(first + 1, len(times)):
        if times[k] is not None:
            if k - prev > 1:                    # interpolate the gap
                a, b = times[prev], times[k]
                for q in range(prev + 1, k):
                    times[q] = a + (b - a) * (q - prev) / (k - prev)
            prev = k
    tail = [k for k in range(last + 1, len(times))]
    if tail:                                    # after the last anchor
        a = times[last]
        step = max(0.5, (song_end - a) / (len(tail) + 1))
        for n, k in enumerate(tail, start=1):
            times[k] = a + step * n

    # A chord nobody can read is worse than no chord. Where the chart packs in
    # more changes than the recording has room for, merge the crush rather than
    # emitting a flicker of unreadable entries.
    MIN_SHOW = 0.30
    out = []
    for k, name in enumerate(seq):
        s = max(0.0, float(times[k]))
        # The chart can list more changes than the recording actually contains
        # (repeats written out, or a busier arrangement than this take). Any
        # chord that would flash by faster than it can be read is dropped and
        # its predecessor keeps the space - a 0.2s chord helps nobody.
        if out and s - out[-1]["start"] < MIN_SHOW:
            continue
        out.append({"start": round(s, 3), "end": 0.0, "chord": name})
    for k in range(len(out)):
        out[k]["end"] = round(out[k + 1]["start"] if k + 1 < len(out) else song_end, 3)
    out = [c for c in out if c["end"] > c["start"]]
    matched = sum(1 for i, j in pairs if i is not None and j is not None)
    return {
        "chords": out,
        "chart_chords": len(seq),
        "detected_raw": len(job.get("chords") or []),
        "detected_changes": len(detected),
        "anchored": len(anchored),
        "matched": matched,
        "merged": len(seq) - len(out),
        "capo": chart["capo"],
        "key_offset": offset,
        "key_fit_pct": round(100 * fit),
        "key": transpose_chord(chart["key"], offset) if chart["key"] else "",
        "coverage_pct": round(100 * len(anchored) / max(1, len(seq))),
    }


def chart_match_report(job, voc):
    """Does this chart actually belong to this recording?

    Key metadata is a poor test — A minor and C major are the SAME key, so
    comparing key roots reports a 9-semitone gap for a perfect match. Compare
    the evidence instead: how many of the chords detected in the audio have a
    root the chart also uses. Low overlap means a different arrangement, a
    different key, or a wrong capo.
    """
    chart_roots = set()
    for c in voc.get("vocab") or []:
        i = _root_index(_chord_parts(c)[0])
        if i is not None:
            chart_roots.add(i)
    hits = total = 0
    for c in job.get("chords") or []:
        i = _root_index(_chord_parts(c.get("chord"))[0])
        if i is None:
            continue
        total += 1
        if i in chart_roots:
            hits += 1
    pct = round(100 * hits / total) if total else 0
    warning = ""
    if total and pct < 60:
        warning = (f"Only {pct}% of the chords heard in this recording use a "
                   f"root this chart plays. It is probably a different version "
                   f"or key — linking it is fine, but correcting the chord "
                   f"names from it is not recommended.")
    return {"overlap_pct": pct, "matched": hits, "total": total,
            "warning": warning}


_NOTE_INDEX = {"C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3, "E": 4,
               "FB": 4, "F": 5, "E#": 5, "F#": 6, "GB": 6, "G": 7, "G#": 8,
               "AB": 8, "A": 9, "A#": 10, "BB": 10, "B": 11, "CB": 11}


def _chord_parts(name):
    """('F#', 'm7') from 'F#m7'; returns (None, None) if it is not a chord."""
    m = re.match(r"^([A-G][#b]?)(.*)$", str(name).strip())
    if not m:
        return None, None
    return m.group(1), m.group(2).strip()


_SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _root_index(root):
    return _NOTE_INDEX.get(str(root).upper()) if root else None


def transpose_chord(name, semitones):
    """'Am' + 3 -> 'Cm'. Keeps the quality suffix; returns the name unchanged
    if it is not a chord symbol."""
    root, qual = _chord_parts(name)
    idx = _root_index(root)
    if idx is None:
        return name
    if not semitones:
        return name
    return _SHARP_NAMES[(idx + int(semitones)) % 12] + (qual or "")


def key_root_index(key_text):
    """Pitch class of a key written as 'C:maj', 'Am', 'F# minor', ..."""
    if not key_text:
        return None
    m = re.match(r"^\s*([A-G][#b]?)", str(key_text))
    return _root_index(m.group(1)) if m else None


def _nearest_in_vocab(root_pc, by_root, counts):
    """The vocabulary chord whose root is closest around the circle of
    semitones. Ties go to whichever the chart actually plays more often."""
    best, best_d, best_n = None, 99, -1
    for pc, names in by_root.items():
        d = abs(pc - root_pc) % 12
        d = min(d, 12 - d)
        for n in names:
            n_count = counts.get(n, 0)
            if d < best_d or (d == best_d and n_count > best_n):
                best, best_d, best_n = n, d, n_count
    return best, best_d


def snap_chords_to_vocabulary(job, vocab, force=False, counts=None):
    """Improve Fadr's chord NAMES using a chart's chord set, keeping Fadr's
    timing (which comes from the audio and is the part worth trusting).

    Deliberately conservative: a chord is only rewritten when its ROOT matches
    a chord in the chart, adopting the chart's fuller quality (Fadr's flat "F"
    becomes "Fmaj7" if that is what the song actually plays). Chords whose root
    the chart never uses are left exactly as they were and counted, so a poor
    match is visible rather than silently mangling the chart.
    """
    by_root = {}
    for v in vocab:
        root, _ = _chord_parts(v)
        idx = _root_index(root)
        if idx is None:
            continue
        by_root.setdefault(idx, []).append(v)
    counts = counts or {}
    changed = unmatched = forced = 0
    moves = {}
    for c in job.get("chords") or []:
        root, qual = _chord_parts(c.get("chord"))
        idx = _root_index(root)
        cands = by_root.get(idx) if idx is not None else None
        if not cands:
            if force and idx is not None and by_root:
                # The chart is the authority on which chords this song uses, so
                # a detected root the chart never plays is almost certainly a
                # detection error: pull it to the nearest chord the song does.
                pick, dist = _nearest_in_vocab(idx, by_root, counts)
                if pick and pick != c["chord"]:
                    moves[c["chord"] + " -> " + pick] = \
                        moves.get(c["chord"] + " -> " + pick, 0) + 1
                    c["chord"] = pick
                    forced += 1
                    continue
            unmatched += 1
            continue
        # Prefer a chart chord whose quality already matches; else the simplest.
        exact = [v for v in cands if _chord_parts(v)[1].lower() == (qual or "").lower()]
        pick = exact[0] if exact else sorted(cands, key=len)[0]
        if pick != c["chord"]:
            c["chord"] = pick
            changed += 1
    return {"changed": changed, "forced": forced, "unmatched": unmatched,
            "total": len(job.get("chords") or []),
            "moves": sorted(moves.items(), key=lambda kv: -kv[1])[:8]}


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


def ensure_riff_wav(path):
    """Return a path to a REAL RIFF WAV for `path`. Fadr serves stem downloads
    as MP3 data regardless of our .wav naming (verified live — every endpoint
    variant returns ID3-tagged MP3), and REAPER trusts the extension, yielding
    zero-length items. Converts to a SIBLING `<name>.riff.wav` (never in place:
    REAPER may hold the original open, which blocks replacement on Windows)."""
    def is_riff(p):
        try:
            with open(p, "rb") as f:
                return f.read(4) == b"RIFF"
        except OSError:
            return False
    path = Path(path)
    if is_riff(path):
        return path
    out = path.with_name(path.stem + ".riff.wav")
    if is_riff(out):
        return out
    ff = shutil.which("ffmpeg") or die("ffmpeg not found on PATH")
    r = subprocess.run([ff, "-y", "-v", "error", "-i", str(path), str(out)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        die(f"Could not convert {path.name} to WAV:\n{r.stderr[-500:]}")
    log(f"Converted {path.name} -> {out.name} (Fadr serves stems as MP3).")
    return out


# ------------------------------------------------------- lyric timing check

# If lyric lines and sung audio best align at an offset beyond this, correct.
CORRECT_ABOVE = 0.35   # seconds
ALIGN_SEARCH = 6.0     # +/- seconds of offset searched


def _activity(wav_path):
    """(bool activity array, hop seconds) for an isolated-vocal stem:
    ffmpeg -> mono 22.05k -> smoothed RMS envelope -> threshold."""
    import numpy as np
    ff = shutil.which("ffmpeg") or die("ffmpeg not found on PATH")
    r = subprocess.run([ff, "-v", "error", "-i", str(wav_path), "-ac", "1",
                        "-ar", "22050", "-f", "s16le", "-"],
                       capture_output=True)
    if r.returncode != 0:
        return None, None
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    hop, win = 512, 2048
    n = max(0, (len(x) - win) // hop)
    if n < 100:
        return None, None
    idx = np.arange(n)[:, None] * hop + np.arange(win)[None, :]
    env = np.sqrt((x[idx] ** 2).mean(axis=1))
    env = np.convolve(env, np.ones(5) / 5, mode="same")
    thr = max(np.percentile(env, 95) * 0.10, 1e-4)
    return env > thr, hop / 22050.0


def stage_lyrics_align(job, job_dir, force):
    """Cross-correlate sung-vocal activity (from the separated vocal stem)
    against the lyric-line activity timeline (from the LRC timestamps) to find
    the offset at which they line up best. A clear off-zero peak means the
    lyric timing is shifted relative to OUR audio — store a correction.
    A weak/flat correlation is reported, never 'fixed' by guessing."""
    ly = job.get("lyrics") or {}
    if not ly.get("synced") or not ly.get("lines"):
        return
    if ly.get("align") and not force:
        return
    vocal = None
    for s in job.get("stems", []):
        if s.get("slot") == "LEAD_VOX" or s.get("fadr_name") in ("vocals lead", "vocals"):
            vocal = job_dir / s["file"]
            break
    if not vocal or not vocal.exists():
        log("Lyric-align: no vocal stem available — skipping check.")
        return
    import numpy as np
    log("Lyric-align: cross-correlating sung vocals vs lyric-line timing...")
    act, hop_s = _activity(vocal)
    if act is None:
        log("Lyric-align: could not analyze vocal stem — skipping.")
        return
    n = len(act)
    lrc = np.zeros(n, dtype=np.float32)
    lines = ly["lines"]
    for i, lnn in enumerate(lines):
        if not lnn["text"]:
            continue
        s = lnn["time"]
        e = lines[i + 1]["time"] if i + 1 < len(lines) else s + 10.0
        e = min(e, s + 15.0)
        a, b = int(s / hop_s), min(int(e / hop_s), n)
        if a < n:
            lrc[a:b] = 1.0
    au = act.astype(np.float32)
    au -= au.mean(); lrc -= lrc.mean()
    max_lag = int(ALIGN_SEARCH / hop_s)
    lags = np.arange(-max_lag, max_lag + 1)
    scores = np.array([np.dot(au[max(0, -l):n - max(0, l)],
                              lrc[max(0, l):n - max(0, -l)]) for l in lags])
    best_i = int(np.argmax(scores))
    offset = round(int(lags[best_i]) * hop_s, 3)   # +ve: lines should move later
    peak = float(scores[best_i])
    # Sharpness: how much the fit worsens 2s either side of the peak. Applying
    # a big shift needs a real peak; concluding "already aligned" does not.
    two = int(2.0 / hop_s)
    side = float(max(scores[max(0, best_i - two)],
                     scores[min(len(scores) - 1, best_i + two)]))
    drop = float(1.0 - (side / peak if peak > 0 else 1.0))
    shift = 0.0
    if abs(offset) <= CORRECT_ABOVE:
        log(f"Lyric-align: OK — lyric timing matches the sung vocals "
            f"(best offset {offset:+.2f}s); no correction needed.")
    elif drop >= 0.10:
        shift = offset
        log(f"Lyric-align: lyric lines best match the sung vocals when moved "
            f"{offset:+.2f}s (fit worsens {drop * 100:.0f}% by ±2s) — applying.")
    else:
        log(f"Lyric-align: WARNING — best offset {offset:+.2f}s but the "
            f"correlation is too flat (only {drop * 100:.0f}% drop by ±2s) to "
            f"apply safely; lyrics may be for a different version. Review "
            f"timing manually.")
    ly["align"] = {"offset": offset, "peak_drop_2s": round(drop, 3),
                   "shift": shift}
    save_job(job_dir, job)


# ---------------------------------------------------------------- mixdown

def stage_mixdown(job, job_dir, cfg, force):
    """One WAV per Jam Room slot: stems sharing a slot (e.g. strings+wind ->
    EXTRA) are summed with ffmpeg (no normalization, we're recombining a
    separation). Single-stem slots reference their stem file directly."""
    if job["stages"].get("mixdown") and not force:
        return
    # Slot assignment happens HERE (not in stage_fadr) so a mapping fix only
    # needs --force-mixdown, never a re-download. Per-job overrides (from the
    # web UI's review step, keyed by stem file) beat the config guesses;
    # "SKIP" excludes a stem entirely.
    slot_map = {norm_stem_type(k): v for k, v in cfg["slot_map"].items()}
    overrides = job.get("slot_overrides") or {}
    by_slot = {}
    for s in job.get("stems", []):
        ov = overrides.get(s["file"])
        if ov == "SKIP":
            s["slot"] = None
            log(f"Stem '{s['fadr_name']}' skipped by your choice.")
            continue
        s["slot"] = ov or slot_map.get(norm_stem_type(s["fadr_name"]))
        if s["slot"]:
            by_slot.setdefault(s["slot"], []).append(s["file"])
        else:
            log(f"NOTE: stem '{s['fadr_name']}' has no slot mapping — skipped.")
    slots_dir = job_dir / "slots"
    labels = cfg["slot_labels"]
    # Musician-facing names chosen in the review UI beat the generic defaults;
    # they become the "[JR:SLOT] Label" bus name ReaSet's mute screen shows.
    label_overrides = job.get("label_overrides") or {}
    job["slots"] = []
    for slot, files in by_slot.items():
        if len(files) == 1:
            out = files[0]
        else:
            slots_dir.mkdir(exist_ok=True)
            out = f"slots/{slot}.wav"
            ffmpeg = shutil.which("ffmpeg") or die("ffmpeg not found on PATH")
            cmd = [ffmpeg, "-y"]
            for f in files:
                cmd += ["-i", str(job_dir / f)]
            cmd += ["-filter_complex", f"amix=inputs={len(files)}:normalize=0",
                    str(job_dir / out)]
            log(f"Mixing {len(files)} stems -> {out}")
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                die(f"ffmpeg mix failed for {slot}:\n{r.stderr[-800:]}")
        job["slots"].append({"slot": slot,
                             "label": label_overrides.get(slot) or
                                      labels.get(slot, slot.title()),
                             "file": out})
    job["stages"]["mixdown"] = True
    save_job(job_dir, job)


# ---------------------------------------------------------------- reaper apply

def lua_quote(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') \
                       .replace("\n", "\\n").replace("\r", "") + '"'


def write_reaper_job(job, job_dir):
    """Emit job_for_reaper.lua — a plain Lua data file so the apply script
    needs no JSON parser. Paths are absolute with forward slashes."""
    jd = str(job_dir.resolve()).replace("\\", "/")
    L = ["-- generated by jamroom_import.py — do not edit", "return {",
         f"  schema = 1,",
         f"  region_name = {lua_quote(job['region_name'])},",
         f"  duration = {job.get('duration') or 0},",
         f"  tempo = {((job.get('fadr') or {}).get('tempo')) or 'nil'},",
         f"  job_dir = {lua_quote(jd)},",
         "  slots = {"]
    for s in job.get("slots", []):
        L.append(f"    {{ slot = {lua_quote(s['slot'])}, "
                 f"label = {lua_quote(s['label'])}, "
                 f"file = {lua_quote(jd + '/' + s['file'])} }},")
    L.append("  },")
    L.append("  chords = {")
    for c in job.get("chords", []):
        L.append(f"    {{ s = {c['start']}, e = {c['end']}, "
                 f"name = {lua_quote(c['chord'])} }},")
    L.append("  },")
    ly = job.get("lyrics", {})
    shift = ((ly.get("align") or {}).get("shift")) or 0.0
    if ly.get("offset_override") is not None:
        shift = ly["offset_override"]
    L.append("  lyrics_lines = {")
    for ln in ly.get("lines", []):
        L.append(f"    {{ t = {max(0.0, round(ln['time'] + shift, 3))}, "
                 f"text = {lua_quote(ln['text'])} }},")
    L.append("  },")
    if ly.get("plain"):
        L.append(f"  lyrics_plain = {lua_quote(ly['plain'])},")
    L.append("}")
    with open(job_dir / "job_for_reaper.lua", "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def stage_apply(job, job_dir, cfg, force):
    """Hand the job to REAPER: pointer file + `reaper -nonewinst apply.lua`,
    then wait for the script's applied.txt receipt (no optimistic claims)."""
    applied = job_dir / "applied.txt"
    if applied.exists() and not force:
        log(f"Already applied ({applied.read_text().strip()}) — skipping. "
            f"Use --force-apply to re-run.")
        return
    applied.unlink(missing_ok=True)
    tooldir = Path(__file__).resolve().parent
    apply_lua = tooldir / "jamroom_import_apply.lua"
    pointer = tooldir / "jamroom_pending_job.txt"
    pointer.write_text(str(job_dir.resolve()), encoding="utf-8")
    if not cfg["auto_apply"]:
        log(f"REAPER auto-apply off. To apply: run {apply_lua.name} from "
            f"REAPER's action list (job pointer is set).")
        return

    # Preferred trigger: web API action call into the RUNNING instance.
    # (`reaper.exe -nonewinst` can silently spawn a second instance if a modal
    # dialog blocks the handoff — the action route cannot misfire like that.)
    web = cfg["reaper_web"].rstrip("/")

    def web_get(path, timeout=5):
        try:
            r = requests.get(f"{web}/_/{path}", timeout=timeout)
            return r.text if r.status_code == 200 else None
        except requests.RequestException:
            return None

    def stored_cmd():
        t = web_get("GET/EXTSTATE/ReaSetJR/import_cmd")
        if t:
            parts = t.strip().split("\t")
            if len(parts) >= 4 and parts[3].strip():
                return parts[3].strip()
        return None

    if web_get("TRANSPORT") is None:
        log(f"REAPER web interface not reachable at {web} — start REAPER "
            f"(with the web interface enabled) and re-run, or run "
            f"{apply_lua.name} from the Action list manually.")
        return
    cmd = stored_cmd()
    if not cmd:
        # One-time bootstrap: register the apply script as an action.
        reaper = Path(cfg["reaper_exe"])
        if not reaper.exists():
            log("Apply action not registered and reaper_exe not found — run "
                "tools/jamroom_register_apply.lua once from REAPER's Action "
                "list, then re-run this tool.")
            return
        log("Registering apply script as a REAPER action (one-time)...")
        subprocess.Popen([str(reaper), "-nonewinst",
                          str(tooldir / "jamroom_register_apply.lua")])
        t0 = time.time()
        while time.time() - t0 < 30 and not cmd:
            time.sleep(2)
            cmd = stored_cmd()
        if not cmd:
            log("Could not register the apply action automatically — run "
                "tools/jamroom_register_apply.lua from REAPER's Action list "
                "once, then re-run this tool.")
            return
    log(f"Triggering apply in running REAPER (action {cmd})...")
    web_get(cmd, timeout=10)
    t0 = time.time()
    while time.time() - t0 < 90:
        if applied.exists():
            log(f"REAPER confirmed: {applied.read_text(encoding='utf-8').strip()}")
            return
        time.sleep(1)
    log("WARNING: no confirmation from REAPER after 90s — check the ReaScript "
        "console in REAPER. (Is the right project tab active?)")


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
    ap.add_argument("--no-apply", action="store_true",
                    help="Prepare the job but don't touch REAPER")
    ap.add_argument("--lyrics-offset", type=float, default=None,
                    help="Manual lyric shift in seconds (overrides auto-align)")
    for st in ("download", "fadr", "chords", "lyrics", "align", "mixdown", "apply"):
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
        stage_lyrics_align(job, job_dir, args.force_align)
    if args.lyrics_offset is not None:
        job.setdefault("lyrics", {})["offset_override"] = args.lyrics_offset
        save_job(job_dir, job)
        log(f"Lyric offset manually set to {args.lyrics_offset:+.2f}s")
    stage_mixdown(job, job_dir, cfg, args.force_mixdown)
    write_reaper_job(job, job_dir)
    if not args.no_apply:
        stage_apply(job, job_dir, cfg, args.force_apply)

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
