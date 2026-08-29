#!/usr/bin/env python3
"""Jam Room Importer — friendly local web UI for the one-shot song import.

Serves a single page (tools/importer.html) on http://localhost:8765 (and the
LAN, so the tablet can use it too — same trust model as REAPER's own web
interface). Flow: search YouTube -> pick match -> download + Fadr split +
lyrics fetch -> REVIEW screen (listen to each stem in the browser, choose its
Jam Room slot, confirm/adjust the lyric timing offset) -> apply to REAPER.
All heavy lifting reuses jamroom_import.py's stages; one import at a time.

Part of ReaSet Jam Room. GPL v3, same as the repo.
"""

import json
import re
import shutil
import socket
import subprocess
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

import jamroom_import as ji

PORT = 8765
TOOLDIR = Path(__file__).resolve().parent
CONFIG_PATH = TOOLDIR / "jamroom_import.config.json"

SLOT_CHOICES = [
    ("DRUMS", "Drums"), ("PERC_FX", "Perc/FX"), ("BASS", "Bass"),
    ("GTR1", "Guitar 1"), ("GTR2", "Guitar 2"), ("KEYS", "Keys"),
    ("BVS", "Backing Vocals"), ("LEAD_VOX", "Lead Vocals"),
    ("CLICK", "Click"), ("EXTRA", "Extras"), ("SKIP", "— don't import —"),
]

# States: idle -> preparing -> review -> applying -> done | failed
STATE = {"state": "idle", "song": "", "log": [], "summary": "", "review": None}
CURRENT = {"job_dir": None}
BUSY = threading.Lock()


def _ui_log(msg):
    print(f"[importer] {msg}", flush=True)
    STATE["log"].append(str(msg))


def _ui_die(msg, code=1):
    _ui_log("ERROR: " + str(msg))
    raise RuntimeError(str(msg))


ji.log = _ui_log
ji.die = _ui_die


def lan_url():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return f"http://{ip}:{PORT}"
    except OSError:
        return ""


def checks():
    out = {"config": CONFIG_PATH.exists(), "key": False,
           "ytdlp": bool(shutil.which("yt-dlp")),
           "ffmpeg": bool(shutil.which("ffmpeg")),
           "reaper": False, "lan": lan_url(), "splits": True,
           # Reports the running code, not the files on disk: if this looks old
           # after an update, the server simply needs restarting.
           "build": getattr(ji, "BUILD", "v1.0-or-older"),
           "build_date": getattr(ji, "BUILD_DATE", "")}
    cfg = None
    if out["config"]:
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            k = cfg.get("fadr_api_key", "")
            out["key"] = bool(k) and not k.startswith("PASTE")
            out["splits"] = bool(cfg.get("vocal_split", True) or
                                 cfg.get("melodic_split", True))
        except (OSError, json.JSONDecodeError):
            out["config"] = False
    web = (cfg or {}).get("reaper_web", "http://localhost:8080").rstrip("/")
    try:
        out["reaper"] = requests.get(f"{web}/_/TRANSPORT", timeout=2).status_code == 200
    except requests.RequestException:
        pass
    return out


def set_key(key):
    if not CONFIG_PATH.exists():
        shutil.copy(TOOLDIR / "jamroom_import.config.example.json", CONFIG_PATH)
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    cfg["fadr_api_key"] = key.strip()
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def search(query):
    if re.match(r"https?://", query):
        args = ["--no-playlist", "--skip-download", "--print",
                "%(id)s\t%(title)s\t%(channel,uploader)s\t%(duration)s", query]
    else:
        args = ["--flat-playlist", "--skip-download", "--print",
                "%(id)s\t%(title)s\t%(channel,uploader)s\t%(duration)s",
                f"ytsearch5:{query}"]
    r = ji.run_ytdlp(args)
    if r.returncode != 0:
        raise RuntimeError("YouTube lookup failed: " + r.stderr[-300:])
    rows = []
    for line in r.stdout.strip().splitlines():
        vid, title, channel, dur = (line.split("\t") + ["", "", ""])[:4]
        try:
            duration = int(float(dur))
        except ValueError:
            duration = 0
        band, song = ji.guess_band_title(title, channel)
        rows.append({"url": f"https://www.youtube.com/watch?v={vid}",
                     "title": title, "channel": channel, "duration": duration,
                     "band": band, "song": song})
    return rows


def _preview_file(job_dir, stem_file):
    """Best browser-playable file for a stem: the original Fadr download
    (MP3 data — small, streams well) if the entry points at a converted
    .riff.wav sibling; otherwise the file itself."""
    p = job_dir / stem_file
    if p.name.endswith(".riff.wav"):
        orig = p.with_name(p.name[:-len(".riff.wav")] + ".wav")
        if orig.exists():
            return orig
    return p


def build_review(job, job_dir, cfg):
    slot_map = {ji.norm_stem_type(k): v for k, v in cfg["slot_map"].items()}
    # Decisions made last time this song was reviewed win over the config
    # guesses, so re-importing or re-adding does not make you redo the work.
    prev_slots = job.get("slot_overrides") or {}
    prev_labels = job.get("label_overrides") or {}
    default_labels = cfg["slot_labels"]
    stems = []
    for s in job.get("stems", []):
        slot = prev_slots.get(s["file"]) \
            or slot_map.get(ji.norm_stem_type(s["fadr_name"])) or "SKIP"
        stems.append({"file": s["file"], "name": s["fadr_name"],
                      "slot": slot,
                      "label": prev_labels.get(slot)
                               or default_labels.get(slot, ""),
                      "audio": "/api/audio?f=" +
                               _preview_file(job_dir, s["file"]).name})
    ly = job.get("lyrics") or {}
    first = next((l for l in ly.get("lines", []) if l["text"]), None)
    align = ly.get("align") or {}
    chart = job.get("chart") or {}
    return {"stems": stems, "slot_choices": SLOT_CHOICES,
            "band": job.get("band", ""), "title": job.get("title", ""),
            "chords_count": len(job.get("chords") or []),
            "chart": {"url": chart.get("url"), "vocab": chart.get("vocab") or [],
                      "key": chart.get("key"), "snapped": chart.get("snapped")},
            "lyrics_source": ly.get("source"),
            "slot_labels": {sid: cfg["slot_labels"].get(sid, name)
                            for sid, name in SLOT_CHOICES if sid != "SKIP"},
            "lyrics": {
                "synced": bool(ly.get("synced")),
                "plain": bool(ly.get("plain")),
                "first_time": first["time"] if first else None,
                "first_text": first["text"] if first else "",
                "suggested_offset": align.get("shift", 0.0) or 0.0,
                "align_note": (
                    f"Audio analysis: best match at {align.get('offset', 0):+.2f}s"
                    if align else "Audio analysis unavailable"),
            },
            "vocal_audio": next((s["audio"] for s in stems
                                 if s["slot"] == "LEAD_VOX"), None)}


def run_prepare(url, band, title):
    try:
        cfg = ji.load_config(None)
        band = ji.sanitize_region_name(band)
        title = ji.sanitize_region_name(title)
        if not band or not title:
            raise RuntimeError("Band and song title are both required.")
        job_dir = Path(cfg["jobs_dir"]) / ji.sanitize_filename(f"{band} - {title}")
        job = ji.load_job(job_dir)
        job.update({"band": band, "title": title,
                    "region_name": f"{band} - {title}"})
        job.setdefault("source", {})["youtube_url"] = url
        ji.save_job(job_dir, job)
        _ui_log(f"Job folder: {job_dir}")
        ji.stage_download(job, job_dir, url, False)
        ji.stage_fadr(job, job_dir, cfg, False)
        ji.stage_chords(job, job_dir, False)
        ji.stage_lyrics(job, job_dir, False)
        ji.stage_lyrics_align(job, job_dir, False)
        CURRENT["job_dir"] = job_dir
        STATE["review"] = build_review(job, job_dir, cfg)
        STATE["state"] = "review"
        _ui_log("Ready for review: listen to the stems, set their slots, "
                "check the lyric timing, then Apply.")
    except Exception as e:  # noqa: BLE001 — surface anything to the UI
        STATE["summary"] = str(e)
        STATE["state"] = "failed"
        _ui_log(f"FAILED: {e}")
    finally:
        BUSY.release()


def _reaper_web(cfg):
    return (cfg or {}).get("reaper_web", "http://localhost:8080").rstrip("/")


def _dir_size(p):
    try:
        return sum(f.stat().st_size for f in Path(p).rglob("*") if f.is_file())
    except OSError:
        return 0


def project_songs():
    """Songs currently in the REAPER project (its regions), each with the size
    of its local import folder so the operator can see what deleting frees."""
    cfg = ji.load_config(None)
    web = _reaper_web(cfg)
    txt = requests.get(f"{web}/_/REGION", timeout=5).text
    jobs_dir = Path(cfg.get("jobs_dir") or (ji.REPO_ROOT / "imports"))
    songs = []
    for line in txt.splitlines():
        f = line.split("\t")
        # REGION \t name \t id \t start \t end \t color
        if len(f) < 5 or f[0] != "REGION":
            continue
        name = f[1].strip()
        if name == "ReaSet Loop":
            continue
        try:
            start, end = float(f[3]), float(f[4])
        except ValueError:
            continue
        folder = jobs_dir / ji.sanitize_filename(name)
        size = _dir_size(folder) if folder.is_dir() else 0
        songs.append({"name": name, "start": start, "end": end,
                      "duration": round(end - start, 1),
                      "folder": str(folder) if folder.is_dir() else None,
                      "folder_mb": round(size / 1e6) if size else 0})
    # Nested regions (song sections) are not songs; drop anything contained
    # in another region, matching how ReaSet and the bridges discover songs.
    tops = []
    for s in songs:
        if not any(o is not s and o["start"] <= s["start"] and o["end"] >= s["end"]
                   and (o["start"] < s["start"] or o["end"] > s["end"]) for o in songs):
            tops.append(s)
    tops.sort(key=lambda s: s["start"])
    return tops


def delete_song(name, start, end, delete_files):
    """Remove a song's region and items from REAPER, optionally its local
    audio too. The REAPER half is one undo step."""
    cfg = ji.load_config(None)
    web = _reaper_web(cfg)
    tooldir = TOOLDIR
    receipt = tooldir / "jamroom_delete_receipt.txt"
    receipt.unlink(missing_ok=True)
    (tooldir / "jamroom_pending_delete.txt").write_text(
        f"{name}\n{start:.3f}\n{end:.3f}\n", encoding="utf-8")

    def web_get(path, timeout=5):
        try:
            r = requests.get(f"{web}/_/{path}", timeout=timeout)
            return r.text if r.status_code == 200 else None
        except requests.RequestException:
            return None

    t = web_get("GET/EXTSTATE/ReaSetJR/delete_cmd")
    cmd = None
    if t:
        parts = t.strip().split("\t")
        if len(parts) >= 4 and parts[3].strip():
            cmd = parts[3].strip()
    if not cmd:
        # Not registered yet (installs predating the delete feature).
        reaper_exe = Path(cfg.get("reaper_exe", ""))
        if reaper_exe.exists():
            subprocess.Popen([str(reaper_exe), "-nonewinst",
                              str(tooldir / "jamroom_register_apply.lua")])
            for _ in range(15):
                time.sleep(2)
                t = web_get("GET/EXTSTATE/ReaSetJR/delete_cmd")
                if t and len(t.strip().split("\t")) >= 4 and t.strip().split("\t")[3].strip():
                    cmd = t.strip().split("\t")[3].strip()
                    break
    if not cmd:
        raise RuntimeError("The delete action is not registered in REAPER. Run "
                           "tools/jamroom_register_apply.lua once from REAPER's "
                           "Action list, then try again.")
    web_get(cmd, timeout=10)
    for _ in range(45):
        if receipt.exists():
            break
        time.sleep(1)
    else:
        why = web_get("GET/EXTSTATE/ReaSetJR/deleter") or ""
        raise RuntimeError("REAPER did not confirm the delete. " + why.strip())

    result = receipt.read_text(encoding="utf-8").strip()
    if delete_files:
        freed = delete_song_audio(cfg, name)
        result += f" audio_deleted={round(freed / 1e6)}MB"
    return result


def delete_song_audio(cfg, name):
    """Delete a song's bulky audio but KEEP job.json and the chord/MIDI files.

    The audio is ~99% of the folder. The job record is a few KB and is worth
    keeping: it maps the Fadr asset id back to a readable song name (older
    uploads are all called "source.wav" on Fadr and are otherwise
    unidentifiable), and it holds the slot assignments, custom group names and
    lyric offset chosen in the review screen, so a later re-import restores
    those decisions instead of asking again.
    """
    jobs_dir = Path(cfg.get("jobs_dir") or (ji.REPO_ROOT / "imports")).resolve()
    folder = jobs_dir / ji.sanitize_filename(name)
    # Refuse anything that is not a job folder directly under jobs_dir.
    if not folder.is_dir() or folder.resolve().parent != jobs_dir:
        return 0
    freed = 0
    for sub in ("stems", "slots"):
        p = folder / sub
        if p.is_dir():
            freed += _dir_size(p)
            shutil.rmtree(p, ignore_errors=True)
    src = folder / "source.wav"
    if src.is_file():
        freed += src.stat().st_size
        src.unlink(missing_ok=True)
    # Mark it so the UI knows the audio is gone without statting every file.
    try:
        job = ji.load_job(folder)
        job["audio_deleted"] = True
        ji.save_job(folder, job)
    except Exception:  # noqa: BLE001 — bookkeeping only
        pass
    return freed


def job_has_audio(folder):
    stems = Path(folder) / "stems"
    return stems.is_dir() and any(stems.glob("*.riff.wav"))


def orphan_jobs():
    """Songs downloaded on this machine that are NOT currently in the project.

    Those that still have their audio can be put back instantly and offline —
    every pipeline stage skips when its work is already cached.
    """
    cfg = ji.load_config(None)
    jobs_dir = Path(cfg.get("jobs_dir") or (ji.REPO_ROOT / "imports"))
    if not jobs_dir.is_dir():
        return []
    try:
        in_project = {s["name"] for s in project_songs()}
    except Exception:  # noqa: BLE001 — REAPER unreachable; show everything
        in_project = set()
    out = []
    for jf in sorted(jobs_dir.glob("*/job.json")):
        try:
            job = json.loads(jf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = job.get("region_name")
        if not name or name in in_project:
            continue
        folder = jf.parent
        out.append({
            "name": name,
            "has_audio": job_has_audio(folder),
            "size_mb": round(_dir_size(folder) / 1e6),
            "duration": round(job.get("duration") or 0, 1),
            "asset_id": (job.get("fadr") or {}).get("asset_id"),
        })
    return out


def run_readd_local(name):
    """Put a previously-downloaded song back into the project using the local
    files — no Fadr, no internet, no waiting. Every stage is already cached, so
    this only rebuilds the review screen from the saved job."""
    try:
        cfg = ji.load_config(None)
        jobs_dir = Path(cfg.get("jobs_dir") or (ji.REPO_ROOT / "imports"))
        job_dir = jobs_dir / ji.sanitize_filename(name)
        job = ji.load_job(job_dir)
        if not job.get("region_name"):
            raise RuntimeError("No saved job for that song.")
        if not job_has_audio(job_dir):
            raise RuntimeError("The audio for this song was deleted. Re-import "
                               "it from the Fadr library tab instead (free).")
        CURRENT["job_dir"] = job_dir
        _ui_log(f"Job folder: {job_dir}")
        _ui_log("Re-adding from the local files — nothing to download.")
        STATE["review"] = build_review(job, job_dir, cfg)
        STATE["state"] = "review"
        _ui_log("Ready for review — your previous group and name choices are "
                "already filled in.")
    except Exception as e:  # noqa: BLE001
        STATE["summary"] = str(e)
        STATE["state"] = "failed"
        _ui_log(f"FAILED: {e}")
    finally:
        BUSY.release()


def run_prepare_library(asset_id, band, title, duration, allow_new_splits=True):
    """Same as run_prepare, but the song is already split on Fadr: skip the
    download, the upload and the main split.

    Sub-splits (lead/backing vocals, guitars/keys) are only free if they were
    already done on that asset. When they were not and the operator declined to
    pay, fall back to the four main stems rather than silently billing them."""
    try:
        cfg = ji.load_config(None)
        if not allow_new_splits:
            cfg = dict(cfg)
            cfg["vocal_split"] = False
            cfg["melodic_split"] = False
            _ui_log("Extra splits declined — importing the main stems only, "
                    "so nothing is charged.")
        job_dir, job = ji.job_from_existing_asset(cfg, asset_id, band, title, duration)
        CURRENT["job_dir"] = job_dir
        _ui_log(f"Job folder: {job_dir}")
        _ui_log("Using an already-split song from your Fadr library — "
                "no upload, no split, no charge.")
        ji.stage_fadr(job, job_dir, cfg, True)
        ji.stage_chords(job, job_dir, True)
        ji.stage_lyrics(job, job_dir, False)
        ji.stage_lyrics_align(job, job_dir, False)
        STATE["review"] = build_review(job, job_dir, cfg)
        STATE["state"] = "review"
        _ui_log("Ready for review.")
    except Exception as e:  # noqa: BLE001
        STATE["summary"] = str(e)
        STATE["state"] = "failed"
        _ui_log(f"FAILED: {e}")
    finally:
        BUSY.release()


def run_apply(slots, labels, lyrics_offset):
    try:
        cfg = ji.load_config(None)
        job_dir = CURRENT["job_dir"]
        job = ji.load_job(job_dir)
        job["slot_overrides"] = slots or {}
        # Per-stem labels from the UI -> one label per slot (first stem
        # assigned to a slot names its bus; labels ride the "[JR:SLOT] Label"
        # track name into ReaSet's mute screen).
        label_overrides = {}
        for file, slot in (slots or {}).items():
            lbl = ji.sanitize_region_name((labels or {}).get(file, ""))
            if slot != "SKIP" and lbl and slot not in label_overrides:
                label_overrides[slot] = lbl
        job["label_overrides"] = label_overrides
        ly = job.setdefault("lyrics", {})
        if lyrics_offset is not None:
            ly["offset_override"] = float(lyrics_offset)
        else:
            ly.pop("offset_override", None)
        ji.save_job(job_dir, job)
        ji.stage_mixdown(job, job_dir, cfg, True)
        ji.write_reaper_job(job, job_dir)
        ji.stage_apply(job, job_dir, cfg, True)
        applied = job_dir / "applied.txt"
        if applied.exists():
            STATE["summary"] = applied.read_text(encoding="utf-8").strip()
            STATE["state"] = "done"
            _ui_log("Import complete. Review the song in REAPER, then SAVE "
                    "the project.")
        else:
            # Ask REAPER why (the apply script leaves its reason in extstate).
            why = ""
            try:
                web = cfg["reaper_web"].rstrip("/")
                t = requests.get(f"{web}/_/GET/EXTSTATE/ReaSetJR/importer",
                                 timeout=3).text.strip().split("\t")
                if len(t) >= 4 and t[3].startswith("failed:"):
                    why = " REAPER says: " + t[3][len("failed:"):]
            except requests.RequestException:
                pass
            STATE["summary"] = ("REAPER did not confirm the apply." + why +
                                " Fix that, then press Apply again.")
            STATE["state"] = "review"
            _ui_log(STATE["summary"])
    except Exception as e:  # noqa: BLE001
        STATE["summary"] = str(e)
        STATE["state"] = "failed"
        _ui_log(f"FAILED: {e}")
    finally:
        BUSY.release()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else \
            json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def _serve_audio(self):
        from urllib.parse import parse_qs, urlparse
        job_dir = CURRENT["job_dir"]
        name = parse_qs(urlparse(self.path).query).get("f", [""])[0]
        if not job_dir:
            return self._send(404, {"error": "no active job"})
        f = (job_dir / "stems" / name).resolve()
        if not str(f).startswith(str(Path(job_dir).resolve())) or not f.is_file():
            return self._send(404, {"error": "not found"})
        with open(f, "rb") as fh:
            head = fh.read(4)
        ctype = "audio/mpeg" if head[:3] == b"ID3" or head[:2] == b"\xff\xfb" \
            else "audio/wav"
        size = f.stat().st_size
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m:
                if m.group(1):
                    start = int(m.group(1))
                if m.group(2):
                    end = min(int(m.group(2)), size - 1)
        length = end - start + 1
        self.send_response(206 if rng else 200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        if rng:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        with open(f, "rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                chunk = fh.read(min(1 << 16, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (ConnectionAbortedError, BrokenPipeError):
                    return
                remaining -= len(chunk)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, (TOOLDIR / "importer.html").read_bytes(),
                       "text/html")
        elif self.path == "/api/checks":
            self._send(200, checks())
        elif self.path == "/api/status":
            self._send(200, STATE)
        elif self.path == "/api/songs":
            try:
                self._send(200, {"songs": project_songs()})
            except Exception as e:  # noqa: BLE001
                self._send(500, {"error": "Could not read the project from "
                                          "REAPER: " + str(e)})
        elif self.path == "/api/orphans":
            try:
                self._send(200, {"jobs": orphan_jobs()})
            except Exception as e:  # noqa: BLE001
                self._send(500, {"error": str(e)})
        elif self.path == "/api/library":
            try:
                self._send(200, {"songs": ji.fadr_library(ji.load_config(None))})
            except Exception as e:  # noqa: BLE001
                self._send(500, {"error": str(e)})
        elif self.path.startswith("/api/audio"):
            self._serve_audio()
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        try:
            body = self._body()
            if self.path == "/api/search":
                self._send(200, {"results": search(body.get("query", ""))})
            elif self.path == "/api/setkey":
                set_key(body.get("key", ""))
                self._send(200, {"ok": True})
            elif self.path == "/api/import":
                if STATE["state"] in ("preparing", "applying", "review"):
                    self._send(409, {"error": "An import is already in "
                                     "progress — finish or cancel it first."})
                    return
                BUSY.acquire()
                STATE.update({"state": "preparing", "log": [], "summary": "",
                              "review": None,
                              "song": f"{body.get('band')} - {body.get('title')}"})
                threading.Thread(target=run_prepare,
                                 args=(body.get("url", ""),
                                       body.get("band", ""),
                                       body.get("title", "")),
                                 daemon=True).start()
                self._send(200, {"ok": True})
            elif self.path == "/api/import_library":
                if STATE["state"] in ("preparing", "applying", "review"):
                    self._send(409, {"error": "An import is already in "
                                     "progress — finish or cancel it first."})
                    return
                BUSY.acquire()
                STATE.update({"state": "preparing", "log": [], "summary": "",
                              "review": None,
                              "song": f"{body.get('band')} - {body.get('title')}"})
                threading.Thread(target=run_prepare_library,
                                 args=(body.get("id", ""), body.get("band", ""),
                                       body.get("title", ""),
                                       body.get("duration", 0),
                                       bool(body.get("allow_new_splits", True))),
                                 daemon=True).start()
                self._send(200, {"ok": True})
            elif self.path == "/api/apply":
                if STATE["state"] != "review":
                    self._send(409, {"error": "Nothing awaiting review."})
                    return
                BUSY.acquire()
                STATE["state"] = "applying"
                threading.Thread(target=run_apply,
                                 args=(body.get("slots") or {},
                                       body.get("labels") or {},
                                       body.get("lyrics_offset")),
                                 daemon=True).start()
                self._send(200, {"ok": True})
            elif self.path == "/api/readd":
                if STATE["state"] in ("preparing", "applying", "review"):
                    self._send(409, {"error": "An import is already in "
                                     "progress — finish or cancel it first."})
                    return
                BUSY.acquire()
                STATE.update({"state": "preparing", "log": [], "summary": "",
                              "review": None, "song": body.get("name", "")})
                threading.Thread(target=run_readd_local,
                                 args=(body.get("name", ""),),
                                 daemon=True).start()
                self._send(200, {"ok": True})
            elif self.path == "/api/lyrics_search":
                try:
                    self._send(200, {"results": ji.lyrics_search(
                        artist=body.get("artist", ""), title=body.get("title", ""),
                        free=body.get("free", ""))})
                except Exception as e:  # noqa: BLE001
                    self._send(500, {"error": str(e)})
            elif self.path == "/api/lyrics_pick":
                if STATE["state"] != "review":
                    self._send(409, {"error": "Nothing is awaiting review."})
                    return
                try:
                    cfg = ji.load_config(None)
                    job_dir = CURRENT["job_dir"]
                    job = ji.load_job(job_dir)
                    ji.lyrics_use_record(job, job_dir, body.get("id"))
                    STATE["review"] = build_review(job, job_dir, cfg)
                    self._send(200, {"ok": True, "review": STATE["review"]})
                except Exception as e:  # noqa: BLE001
                    self._send(500, {"error": str(e)})
            elif self.path == "/api/ug_search":
                try:
                    self._send(200, {"charts": ji.ug_search(
                        body.get("artist", ""), body.get("title", ""))})
                except Exception as e:  # noqa: BLE001
                    self._send(500, {"error": str(e)})
            elif self.path == "/api/ug_use":
                if STATE["state"] != "review":
                    self._send(409, {"error": "Nothing is awaiting review."})
                    return
                try:
                    cfg = ji.load_config(None)
                    job_dir = CURRENT["job_dir"]
                    job = ji.load_job(job_dir)
                    detected = (job.get("fadr") or {}).get("key") or ""
                    voc = ji.ug_chart_vocabulary(body.get("url", ""), detected)
                    if voc.get("capo"):
                        _ui_log(f"Chart has a capo at fret {voc['capo']} — its "
                                f"printed shapes {voc['shapes'][:6]} sound as "
                                f"{voc['vocab'][:6]}. Using the sounding names.")
                    match = ji.chart_match_report(job, voc)
                    _ui_log(f"Chart match: {match['overlap_pct']}% of the "
                            f"detected chords use a root this chart plays.")
                    if match["warning"]:
                        _ui_log("WARNING: " + match["warning"])
                    voc["warning"] = match["warning"]
                    voc["overlap_pct"] = match["overlap_pct"]
                    stats = None
                    if body.get("snap"):
                        stats = ji.snap_chords_to_vocabulary(job, voc["vocab"])
                        _ui_log(f"Chord names snapped to the chart: "
                                f"{stats['changed']} renamed, "
                                f"{stats['unmatched']} left alone "
                                f"(root not in the chart).")
                    job["chart"] = {"url": voc["url"], "vocab": voc["vocab"],
                                    "shapes": voc["shapes"], "key": voc["key"],
                                    "shape_key": voc["shape_key"],
                                    "capo": voc["capo"], "snapped": stats,
                                    "warning": voc.get("warning", ""),
                                    "overlap_pct": voc.get("overlap_pct"),
                                    "detected_key": voc["detected_key"]}
                    ji.save_job(job_dir, job)
                    STATE["review"] = build_review(job, job_dir, cfg)
                    self._send(200, {"ok": True, "chart": job["chart"],
                                     "review": STATE["review"]})
                except Exception as e:  # noqa: BLE001
                    self._send(500, {"error": str(e)})
            elif self.path == "/api/delete_song":
                if STATE["state"] in ("preparing", "applying"):
                    self._send(409, {"error": "An import is running — wait for "
                                     "it to finish before deleting anything."})
                    return
                try:
                    res = delete_song(body.get("name", ""),
                                      float(body.get("start", 0)),
                                      float(body.get("end", 0)),
                                      bool(body.get("delete_files")))
                    self._send(200, {"ok": True, "result": res})
                except Exception as e:  # noqa: BLE001
                    self._send(500, {"error": str(e)})
            elif self.path == "/api/cancel":
                if STATE["state"] == "review":
                    STATE.update({"state": "idle", "review": None,
                                  "summary": "", "log": []})
                self._send(200, {"ok": True})
            else:
                self._send(404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001
            self._send(500, {"error": str(e)})


class ImporterServer(ThreadingHTTPServer):
    # Python defaults this to True, which on Windows lets a SECOND server bind
    # a port the first one already holds. Requests then go to whichever socket
    # Windows picks, so "close it and start it again" can silently leave the
    # OLD server answering — an updated page talking to stale code.
    allow_reuse_address = False


def main():
    try:
        srv = ImporterServer(("0.0.0.0", PORT), Handler)
    except OSError:
        print("=" * 62)
        print(f" A Jam Room Importer is ALREADY RUNNING on port {PORT}.")
        print()
        print(" Close that window first. If there is no window, end any stray")
        print(" python.exe in Task Manager, or run this in PowerShell:")
        print(f"   Get-NetTCPConnection -LocalPort {PORT} -State Listen |")
        print("     ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }")
        print()
        print(" Then start JamRoom Importer.bat again.")
        print("=" * 62)
        try:
            input("Press Enter to close...")
        except EOFError:
            pass
        return
    url = f"http://localhost:{PORT}"
    print(f"Jam Room Importer {getattr(ji, 'BUILD', '?')} running at {url}")
    if lan_url():
        print(f"  (from the tablet: {lan_url()})")
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001 — opening a browser is best-effort
        pass
    srv.serve_forever()


if __name__ == "__main__":
    main()
