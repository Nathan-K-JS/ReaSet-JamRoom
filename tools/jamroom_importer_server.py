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
import threading
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
           "reaper": False, "lan": lan_url(), "splits": True}
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
    stems = []
    for s in job.get("stems", []):
        guess = slot_map.get(ji.norm_stem_type(s["fadr_name"])) or "SKIP"
        stems.append({"file": s["file"], "name": s["fadr_name"],
                      "slot": guess,
                      "audio": "/api/audio?f=" +
                               _preview_file(job_dir, s["file"]).name})
    ly = job.get("lyrics") or {}
    first = next((l for l in ly.get("lines", []) if l["text"]), None)
    align = ly.get("align") or {}
    return {"stems": stems, "slot_choices": SLOT_CHOICES,
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


def run_apply(slots, lyrics_offset):
    try:
        cfg = ji.load_config(None)
        job_dir = CURRENT["job_dir"]
        job = ji.load_job(job_dir)
        job["slot_overrides"] = slots or {}
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
            elif self.path == "/api/apply":
                if STATE["state"] != "review":
                    self._send(409, {"error": "Nothing awaiting review."})
                    return
                BUSY.acquire()
                STATE["state"] = "applying"
                threading.Thread(target=run_apply,
                                 args=(body.get("slots") or {},
                                       body.get("lyrics_offset")),
                                 daemon=True).start()
                self._send(200, {"ok": True})
            elif self.path == "/api/cancel":
                if STATE["state"] == "review":
                    STATE.update({"state": "idle", "review": None,
                                  "summary": "", "log": []})
                self._send(200, {"ok": True})
            else:
                self._send(404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001
            self._send(500, {"error": str(e)})


def main():
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"Jam Room Importer running at {url}")
    if lan_url():
        print(f"  (from the tablet: {lan_url()})")
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001 — opening a browser is best-effort
        pass
    srv.serve_forever()


if __name__ == "__main__":
    main()
