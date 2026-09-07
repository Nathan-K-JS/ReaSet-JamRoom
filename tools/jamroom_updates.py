"""Resumable, opt-in library upgrades using the normal chart generator. GPL-3.0."""
import copy
import json
import threading
import uuid
from pathlib import Path

import requests
import jamroom_import as ji


def read(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=True, indent=2), encoding="utf-8")
    tmp.replace(path)


class Updates:
    def __init__(self, project_identity, project_songs, push, busy, state):
        self.identity, self.songs, self.push = project_identity, project_songs, push
        self.busy, self.state = busy, state
        self.guard = threading.RLock()
        self.stop = threading.Event()
        self.active = None

    def context(self):
        cfg = ji.load_config(None)
        project = self.identity(cfg)
        root = Path(cfg["jobs_dir"]) / ".updates" / project
        return cfg, project, root

    def song_state(self, cfg, songs):
        keys = [f"song:{s['id']}:{field}" for s in songs for field in ("revision",)]
        if not keys: return {}
        result = requests.get(ji_url(cfg) + "/_/" + ";".join("GET/PROJEXTSTATE/ReaSetSong/" + k for k in keys), timeout=10)
        result.raise_for_status()
        return {f[2]: f[3] if len(f)>3 else "" for line in result.text.splitlines()
                if len(f := line.split("\t")) >= 3 and f[0]=="PROJEXTSTATE"}

    def listing(self):
        cfg, project, root = self.context()
        songs = self.songs()
        states = self.song_state(cfg, songs)
        settings = read(root / "settings.json", {})
        out = []
        for song in songs:
            folder = Path(song["folder"]) if song.get("folder") else None
            job = ji.load_job(folder) if folder and (folder / "job.json").is_file() else {}
            protected = settings.get(str(song["id"])) == song["name"]
            generation = job.get("generation") or {}
            current = (generation.get("generator") == ji.chart_model.GENERATOR and
                       states.get(f"song:{song['id']}:revision") == generation.get("revision"))
            revision = states.get(f"song:{song['id']}:revision")
            manual_edits = bool(revision and revision != generation.get("revision"))
            status = "Keep this version" if protected else "Current" if current else "Update available" if job else "Source files missing"
            out.append(dict(song, project=project, protected=protected, current=current,
                            manual_edits=manual_edits, update_status=status,
                            eligible=bool(job) and not protected and not current))
        latest = read(root / "latest.json", {})
        batch = read(root / (latest.get("id", "none") + ".json"), None)
        if batch and batch["status"] == "running" and self.active != batch["id"]:
            batch["status"] = "interrupted"
        return {"project": project, "songs": out, "batch": batch}

    def protect(self, song_id, name, keep, target_project=None):
        _, project, root = self.context()
        if target_project and project != target_project: raise ValueError("Project changed; refresh the list")
        if not any(s["id"] == song_id and s["name"] == name for s in self.songs()):
            raise ValueError("Song changed; refresh the list")
        with self.guard:
            values = read(root / "settings.json", {})
            if keep: values[str(song_id)] = name
            else: values.pop(str(song_id), None)
            write(root / "settings.json", values)

    def start(self, ids=None, resume=False, restore=False, replace_edits=False, target_project=None):
        if not self.busy.acquire(blocking=False):
            raise ValueError("Another import or change is running")
        try:
            if self.state["state"] in ("preparing", "review", "applying"):
                raise ValueError("Finish the current import first")
            listing = self.listing()
            cfg, project, root = self.context()
            if listing["project"] != project or (target_project and target_project != project):
                raise ValueError("Project changed; refresh the list")
            if resume:
                batch = listing["batch"]
                if not batch: raise ValueError("No batch to resume")
                if batch["project"] != project: raise ValueError("Project changed")
                for item in batch["songs"]:
                    if item["status"] in ("failed", "pending", "working"):
                        item["status"] = "pending"
            else:
                if not isinstance(ids, list) or not ids: raise ValueError("Select songs to update")
                chosen = [s for s in listing["songs"] if s["id"] in ids and
                          (restore or not s["protected"] and (not s["current"] or replace_edits))]
                batch = {"id": uuid.uuid4().hex, "project": project, "status": "running",
                         "restore": bool(restore), "replace_edits": bool(replace_edits),
                         "songs": [dict(s, status="pending", message="") for s in chosen]}
                if not batch["songs"]: raise ValueError("Selected songs are protected, already current, or unavailable")
            batch["status"] = "running"
            write(root / (batch["id"] + ".json"), batch)
            write(root / "latest.json", {"id": batch["id"]})
            self.active = batch["id"]; self.stop.clear()
            threading.Thread(target=self.run, args=(cfg, root, batch), daemon=True).start()
            return batch["id"]
        except Exception:
            self.busy.release()
            raise

    def run(self, cfg, root, batch):
        path = root / (batch["id"] + ".json")
        try:
            for item in batch["songs"]:
                if item["status"] != "pending": continue
                if self.stop.is_set():
                    batch["status"] = "paused"; break
                if self.identity(cfg) != batch["project"]:
                    batch["status"] = "paused"; break
                # Never apply while a rehearsal is playing. Resume after stop.
                transport = requests.get(ji_url(cfg) + "/_/TRANSPORT", timeout=5)
                transport.raise_for_status()
                if int(transport.text.split("\t")[1]) != 0:
                    batch["status"] = "paused"; break
                settings = read(root / "settings.json", {})
                if not batch["restore"] and settings.get(str(item["id"])) == item["name"]:
                    item.update(status="skipped", message="Keep this version"); write(path,batch); continue
                item["status"] = "working"; write(path,batch)
                try:
                    self.update_one(cfg, root, batch, item)
                    item.update(status="done", message="Restored" if batch["restore"] else "Updated")
                except Exception as e:
                    item.update(status="failed", message=str(e))
                write(path,batch)
            else:
                batch["status"] = "complete"
        except Exception as e:
            batch.update(status="paused", error=str(e))
        finally:
            write(path,batch)
            self.active = None
            self.busy.release()

    def update_one(self, cfg, root, batch, item):
        if not item.get("folder"): raise ValueError("Original song sources are missing")
        folder = Path(item["folder"]).resolve()
        if folder.parent != Path(cfg["jobs_dir"]).resolve(): raise ValueError("Invalid song folder")
        op = root / (batch["id"] + "-" + str(item["id"]))
        op.mkdir(exist_ok=True)
        installed_path = root / ("song-" + str(item["id"]) + ".json")
        installed = read(installed_path, {})
        if batch["restore"]:
            # Freeze the target before applying: a retry after saving the job or
            # installation manifest must restore the same revision again.
            target_path = op / "restore-target.json"
            if target_path.exists():
                installed = read(target_path)
            elif installed.get("before"):
                write(target_path, installed)
            if not installed.get("before"): raise ValueError("No saved previous version for this song")
            self.push(cfg, item["name"], item, operation_dir=op,
                      expected=installed["after"], restore=installed["before"])
            previous = read(Path(installed["job_before"]), {})
            ji.save_job(folder, previous)
            previous_installation = read(Path(installed["installation_before"]), {})
            if previous_installation: previous_installation["after"] = str(op / "after.json")
            write(installed_path, previous_installation)
            return
        candidate_path = op / "candidate.json"
        if candidate_path.exists():
            candidate = read(candidate_path)
        else:
            original = ji.load_job(folder)
            if not (folder / "job.json").is_file(): raise ValueError("No saved source job")
            if not ((original.get("lyrics") or {}).get("lines") or
                    (original.get("lyrics") or {}).get("plain") or
                    (original.get("chart") or {}).get("url") or ji.detected_chords(original,folder)):
                raise ValueError("Cached lyrics and chord sources are missing; previous song retained")
            if (item.get("manual_edits") or "Timing adjusted" in item.get("review_status", "")) and not batch["replace_edits"]:
                raise ValueError("Saved timing fixes: select 'Replace old timing fixes' to rebuild, or keep this version")
            write(op / "job-before.json", original)
            write(op / "installation-before.json", installed)
            candidate = copy.deepcopy(original)
            candidate["duration"] = item["end"] - item["start"]
            ji.stage_lyrics_align(candidate, folder, False, persist=False)
            ji.prepare_chart_document(candidate, folder)
            write(candidate_path,candidate)
        expected = None if batch["replace_edits"] else installed.get("after")
        self.push(cfg, item["name"], item, chords=candidate["chords"],
                  lyric_lines=ji.chart_model.lyric_items(candidate), document=candidate["chart_document"],
                  operation_dir=op, expected=expected)
        ji.save_job(folder,candidate)
        write(installed_path, {"before": str(op / "before.json"), "after": str(op / "after.json"),
                              "job_before": str(op / "job-before.json"),
                              "installation_before": str(op / "installation-before.json"),
                              "revision": candidate["chart_document"]["revision"]})


def ji_url(cfg):
    return cfg.get("reaper_web", "http://localhost:8080").rstrip("/")
