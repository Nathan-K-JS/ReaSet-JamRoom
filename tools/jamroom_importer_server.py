#!/usr/bin/env python3
"""Jam Room Importer — friendly local web UI for the one-shot song import.

Serves a single page (tools/importer.html) on http://localhost:8765 (and the
LAN, so the tablet can use it too — same trust model as REAPER's own web
interface). Search YouTube, pick the match, confirm band/title, import.
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

STATE = {"state": "idle", "song": "", "log": [], "summary": ""}
BUSY = threading.Lock()


# Route the pipeline's logging into the UI, and make fatal errors raise
# instead of killing the process.
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
           "reaper": False, "lan": lan_url(),
           "splits": True}
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
    """YouTube search (or single-URL probe) -> candidate rows for the UI."""
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


def run_import(url, band, title):
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
            STATE["summary"] = ("REAPER did not confirm the apply — check "
                                "REAPER's ReaScript console and any open "
                                "dialogs, then press Import again.")
            STATE["state"] = "failed"
    except Exception as e:  # noqa: BLE001 — surface anything to the UI
        STATE["summary"] = str(e)
        STATE["state"] = "failed"
        _ui_log(f"FAILED: {e}")
    finally:
        BUSY.release()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet the request log
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

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, (TOOLDIR / "importer.html").read_bytes(),
                       "text/html")
        elif self.path == "/api/checks":
            self._send(200, checks())
        elif self.path == "/api/status":
            self._send(200, STATE)
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
                if not BUSY.acquire(blocking=False):
                    self._send(409, {"error": "An import is already running."})
                    return
                STATE.update({"state": "running", "log": [], "summary": "",
                              "song": f"{body.get('band')} - {body.get('title')}"})
                threading.Thread(target=run_import,
                                 args=(body.get("url", ""),
                                       body.get("band", ""),
                                       body.get("title", "")),
                                 daemon=True).start()
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
