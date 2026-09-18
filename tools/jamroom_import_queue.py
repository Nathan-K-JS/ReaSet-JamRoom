"""Durable, isolated importer workspaces. No work is submitted on startup.

GPL v3, part of ReaSet Jam Room.
"""
import copy
import json
import math
import os
from pathlib import Path
import threading
import time
import uuid
from urllib.parse import quote

import jamroom_import as ji


class Conflict(ValueError):
    pass


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=True, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding='utf-8'))
            backup = path.with_suffix('.previous')
            backup_tmp = path.with_suffix('.previous.tmp')
            backup_tmp.write_text(json.dumps(previous), encoding='utf-8')
            os.replace(backup_tmp, backup)
        except ValueError:
            pass
    for attempt in range(8):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(.05 * (attempt + 1))


class ImportQueue:
    def __init__(self, server, cfg=None):
        self.server = server
        self.cfg = cfg or ji.load_config(None)
        self.root = Path(self.cfg['jobs_dir']).resolve()
        self.path = self.root / 'import-queue.json'
        self.guard = threading.RLock()
        self.analysis = threading.Lock()
        self.running = set()
        self.locks = {}
        self.jobs = {}
        self.paused = False
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding='utf-8'))
            except (ValueError, OSError):
                data = json.loads(self.path.with_suffix('.previous').read_text(encoding='utf-8'))
            self.jobs = data['jobs']
            for row in self.jobs.values():
                if row['state'] in ('queued', 'preparing', 'applying', 'editing'):
                    row['state'] = 'interrupted'
                    row['summary'] = 'Importer restarted. Resume to continue from saved work.'
        # Old cached imports remain explicitly labelled: absence from a project
        # does not establish that an import was unfinished.
        known = {row['folder'] for row in self.jobs.values()}
        for file in self.root.glob('*/job.json'):
            folder = str(file.parent.resolve())
            if folder in known:
                continue
            try:
                job = ji.load_job(file.parent)
                if not job.get('region_name') or job.get('audio_deleted'):
                    continue
                row = self._record(job, folder, 'cached')
                row['summary'] = 'Existing cached song. Open or resume explicitly; it may already be in a project.'
                self.jobs[row['id']] = row
            except (OSError, ValueError):
                continue
        self._save()

    def _record(self, job, folder, state):
        source = job.get('source', {})
        return dict(id=uuid.uuid4().hex, song=job['region_name'], folder=folder,
                    band=job.get('band', ''), title=job.get('title', ''),
                    url=source.get('youtube_url', ''), asset=(job.get('fadr') or {}).get('asset_id'),
                    state=state, stage='', summary='', log=[], revision=0, draft={},
                    target='', operation=uuid.uuid4().hex, created=time.time(),
                    config={k: copy.deepcopy(self.cfg[k]) for k in
                            ('vocal_split', 'melodic_split', 'slot_map', 'slot_labels') if k in self.cfg})

    def _save(self):
        atomic(self.path, {'schema': 1, 'jobs': self.jobs})

    def listing(self):
        with self.guard:
            return {'schema': 1, 'paused': self.paused, 'jobs': [
                {k: copy.deepcopy(v) for k, v in row.items() if k not in ('folder', 'config', 'review', 'draft', 'log')}
                for row in self.jobs.values() if row['state'] != 'removed']}

    def folder(self, ident):
        folder = Path(self.jobs[ident]['folder']).resolve()
        if not folder.is_relative_to(self.root) or folder == self.root:
            raise ValueError('Invalid job folder')
        return folder

    def log(self, ident, message):
        with self.guard:
            row = self.jobs[ident]
            row['log'] = (row['log'] + [str(message)])[-250:]
            self._save()

    def config(self, row):
        cfg = ji.load_config(None)
        cfg.update(row['config'])
        return cfg

    def add(self, body):
        band, title = (ji.sanitize_region_name(str(body.get(k, ''))) for k in ('band', 'title'))
        url = str(body.get('url', '')).strip()
        asset = body.get('asset')
        if not band or not title or not (url or asset):
            raise ValueError('Recording, band and title are required')
        name = f'{band} - {title}'
        with self.guard:
            if self.server.STATE['state'] in self.server.ACTIVE_STATES:
                raise Conflict('Finish the import started by the previous interface first.')
            for row in self.jobs.values():
                if row['song'] == name and row['state'] != 'removed':
                    if row.get('url') == url and row.get('asset') == asset:
                        return {'ok': True, 'id': row['id']}
                    raise Conflict('A different recording already uses this title. Give this version a distinct song title.')
            try:
                songs = self.server.project_songs()
            except Exception:
                songs = []  # The Lua Apply guard checks again against the actual target.
            if any(song['name'] == name for song in songs):
                raise Conflict('This song is already in the open project. Use a distinct title for another version.')
            folder = self.root / ji.sanitize_filename(name)
            if (folder / 'job.json').exists():
                raise Conflict('Cached work already uses this title. Open it in the song list, or use a distinct title.')
            job = dict(schema=1, stages={}, band=band, title=title, region_name=name,
                       source={'youtube_url': url}, duration=body.get('duration') or 0)
            if asset:
                job['fadr'] = {'asset_id': str(asset)}
                job['source']['from_fadr_library'] = True
                job['stages']['download'] = True
            row = self._record(job, str(folder), 'queued')
            row['asset'] = asset
            if asset and not body.get('allow_new_splits'):
                row['config'].update(vocal_split=False, melodic_split=False)
            try:
                row['target'] = self.server.project_identity()
            except Exception:
                pass  # Preparation does not require REAPER online.
            ji.save_job(folder, job)
            self.jobs[row['id']] = row
            self._save()
            self.schedule()
            return {'ok': True, 'id': row['id']}

    def schedule(self):
        with self.guard:
            if self.paused:
                return
            for row in self.jobs.values():
                if len(self.running) >= 2:
                    break
                if row['state'] == 'queued' and row['id'] not in self.running:
                    self.running.add(row['id'])
                    row['state'] = 'preparing'
                    self._save()
                    threading.Thread(target=self.prepare, args=(row['id'],), daemon=True).start()

    def checkpoint(self, row, stage):
        with self.guard:
            row['stage'] = stage
            self._save()
            if self.paused:
                row['state'] = 'paused'
                self._save()
                return False
            return True

    def prepare(self, ident):
        row = self.jobs[ident]
        token = ji.JOB_LOG.set(lambda msg: self.log(ident, msg))
        pause_token = ji.JOB_PAUSE.set(lambda: self.paused)
        try:
            folder = self.folder(ident)
            job, cfg = ji.load_job(folder), self.config(row)
            # Completed source/stem flags alone are not proof the files survived.
            stems_valid = bool(job.get('stems')) and all((folder / stem['file']).is_file() for stem in job['stems'])
            if not row.get('asset') and not stems_valid and not (folder / job.get('source', {}).get('audio_file', 'source.wav')).is_file():
                job['stages'].pop('download', None)
            if any(not (folder / stem['file']).is_file() for stem in job.get('stems', [])):
                job['stages'].pop('fadr', None)
            stages = [
                ('Downloading source', lambda: ji.stage_download(job, folder, row['url'], False), ji.DOWNLOAD_BUDGET),
                ('Separating / downloading stems', lambda: ji.stage_fadr(job, folder, cfg, False), None),
                ('Analysing chords', lambda: ji.stage_chords(job, folder, False), self.analysis),
                ('Finding lyrics', lambda: ji.stage_lyrics(job, folder, False), self.analysis),
                ('Aligning lyrics', lambda: ji.stage_lyrics_align(job, folder, False), self.analysis)]
            for stage, action, lock in stages:
                if stage == 'Downloading source' and stems_valid and job['stages'].get('fadr'):
                    continue
                if not self.checkpoint(row, stage):
                    return
                if lock:
                    with lock:
                        action()
                else:
                    action()
            with self.analysis:
                review = self.server.build_review(job, folder, cfg)
            with self.guard:
                row.update(state='review', stage='', summary='', review=review)
                self._save()
        except ji.ImportPaused as error:
            with self.guard:
                row.update(state='paused', summary=str(error))
                self._save()
        except Exception as error:
            with self.guard:
                row.update(state='failed', summary=str(error))
                self._save()
        finally:
            ji.JOB_LOG.reset(token)
            ji.JOB_PAUSE.reset(pause_token)
            with self.guard:
                self.running.discard(ident)
                self.schedule()

    def detail(self, ident):
        with self.guard:
            row = self.jobs[ident]
            result = copy.deepcopy(row)
            result.pop('folder', None)
            result.pop('config', None)
            if result.get('review'):
                def scope(value):
                    if isinstance(value, dict):
                        return {k: scope(v) for k, v in value.items()}
                    if isinstance(value, list):
                        return [scope(v) for v in value]
                    if isinstance(value, str) and value.startswith('/api/audio?'):
                        return value + '&job=' + quote(ident)
                    return value
                result['review'] = scope(result['review'])
            return result

    def draft(self, ident, body):
        with self.guard:
            row = self.jobs[ident]
            if row['state'] != 'review':
                raise Conflict('This job is not ready for review')
            if body.get('revision') != row['revision']:
                raise Conflict('This review changed in another browser. Reopen it before editing.')
            draft = body.get('draft', {})
            valid_files = {s['file'] for s in ji.load_job(self.folder(ident)).get('stems', [])}
            slots = draft.get('slots', {})
            if any(k not in valid_files or v not in dict(self.server.SLOT_CHOICES) for k, v in slots.items()):
                raise ValueError('Invalid stem routing')
            offset = draft.get('lyrics_offset')
            if offset is not None and (not isinstance(offset, (int, float)) or not math.isfinite(offset)):
                raise ValueError('Invalid lyric offset')
            row['draft'] = copy.deepcopy(draft)
            row['revision'] += 1
            self._save()
            return {'ok': True, 'revision': row['revision']}

    def choose(self, ident, action, body):
        with self.guard:
            row = self.jobs[ident]
            if row['state'] != 'review' or body.get('revision') != row['revision']:
                raise Conflict('This review changed or is busy. Reopen it before continuing.')
            row['state'] = 'editing'
            self._save()
        token = ji.JOB_LOG.set(lambda msg: self.log(ident, msg))
        try:
            folder, cfg = self.folder(ident), self.config(row)
            job = ji.load_job(folder)
            with self.analysis:
                if action == 'lyrics':
                    ji.lyrics_use_record(job, folder, body.get('id'))
                    ji.prepare_chart_document(job, folder)
                else:
                    if not job.get('chords_detected'):
                        job['chords_detected'] = ji.detected_chords(job, folder)
                    result = ji.build_chart_chords(job, body.get('url', ''), job_dir=folder)
                    job['chords'] = result['chords']
                    job['chart'] = {k: result.get(k) for k in ('method', 'key', 'capo',
                        'key_offset', 'lines_matched', 'chart_lines', 'fallback_reason')}
                    job['chart']['url'] = body.get('url', '')
                ji.save_job(folder, job)
                review = self.server.build_review(job, folder, cfg)
            with self.guard:
                row.update(review=review, revision=row['revision'] + 1)
        finally:
            ji.JOB_LOG.reset(token)
            with self.guard:
                row['state'] = 'review'
                self._save()
        return {'ok': True, 'revision': row['revision'], 'review': self.detail(ident)['review'],
                'chart': job.get('chart', {})}

    def action(self, ident, action, body):
        with self.guard:
            row = self.jobs[ident]
            if action == 'resume':
                if row.get('apply_started'):
                    raise Conflict('This Apply needs checking. Open its target project and use Check Apply.')
                if row['state'] not in ('failed', 'interrupted', 'paused', 'cached'):
                    return {'ok': True}
                row.update(state='queued', summary='')
                self._save()
                self.schedule()
                return {'ok': True}
            if action == 'remove':
                if ident in self.running or row['state'] in ('applying', 'editing'):
                    raise Conflict('Pause the queue and let this stage finish before removing the song')
                row['state'] = 'removed'
                self._save()
                return {'ok': True}
            if body.get('revision') != row['revision']:
                raise Conflict('This review changed. Reopen it before continuing.')
            if action == 'reopen':
                if row['state'] != 'done':
                    raise Conflict('Only completed imports can be reopened for another project')
                row.update(state='review', target='', operation=uuid.uuid4().hex,
                           apply_started=False, summary='', revision=row['revision'] + 1)
                self._save()
                return {'ok': True}
            if action == 'target':
                if row['state'] != 'review':
                    raise Conflict('Wait until review is ready')
                if row.get('apply_started'):
                    raise Conflict('An Apply is unresolved. Reopen the original target project and retry there.')
                row['target'] = self.server.project_identity()
                row['revision'] += 1
                self._save()
                return {'ok': True, 'revision': row['revision'], 'target': row['target']}
            if action == 'apply':
                if row['state'] not in ('review', 'interrupted'):
                    raise Conflict('This job is not ready to apply')
                if not row['target'] or self.server.project_identity() != row['target']:
                    raise Conflict('Open the intended project, or explicitly select the current project as the target.')
                if not self.server.BUSY.acquire(blocking=False):
                    raise Conflict('Another REAPER change is running. Try again when it finishes.')
                row.update(state='applying', apply_started=True)
                self._save()
                threading.Thread(target=self.apply, args=(ident,), daemon=True).start()
                return {'ok': True}
            raise ValueError('Unknown job action')

    def protect(self, names):
        with self.guard:
            if any(row['song'] in names and row['state'] not in ('cached', 'done', 'removed') for row in self.jobs.values()):
                raise Conflict('A saved import workspace is using this song. Finish or remove it from the queue before changing its library files.')

    def apply(self, ident):
        row = self.jobs[ident]
        token = ji.JOB_LOG.set(lambda msg: self.log(ident, msg))
        try:
            folder, cfg = self.folder(ident), self.config(row)
            job = ji.load_job(folder)
            draft = row['draft']
            job['slot_overrides'] = draft.get('slots', job.get('slot_overrides', {}))
            labels = {}
            for file, slot in job['slot_overrides'].items():
                label = ji.sanitize_region_name(draft.get('labels', {}).get(file, ''))
                if slot != 'SKIP' and label:
                    labels.setdefault(slot, label)
            job['label_overrides'] = labels or job.get('label_overrides', {})
            if draft.get('lyrics_offset') is not None:
                job.setdefault('lyrics', {})['offset_override'] = draft['lyrics_offset']
            job.update(import_operation=row['operation'], target_project=row['target'])
            ji.save_job(folder, job)
            with self.analysis:
                ji.stage_mixdown(job, folder, cfg, True)
                ji.write_reaper_job(job, folder)
            ji.stage_apply(job, folder, cfg, True)
            if not (folder / 'applied.txt').is_file():
                raise RuntimeError('REAPER did not confirm Apply. Open the intended project, stop playback/recording, then retry. The same operation ID prevents a duplicate append.')
            with self.guard:
                row.update(state='done', summary='Added to REAPER. Save the project to keep it.')
                self._save()
        except Exception as error:
            with self.guard:
                row.update(state='review', summary=str(error))
                self._save()
        finally:
            ji.JOB_LOG.reset(token)
            self.server.BUSY.release()

    def control(self, body):
        with self.guard:
            self.paused = bool(body.get('pause'))
            if body.get('resume'):
                for row in self.jobs.values():
                    if row['state'] in ('paused', 'interrupted', 'failed') and not row.get('apply_started'):
                        row['state'] = 'queued'
            self._save()
            self.schedule()
            return self.listing()
