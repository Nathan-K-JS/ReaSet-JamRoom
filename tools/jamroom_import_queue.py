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
                if row.get('apply_started') and not row.get('apply_prepared'):
                    row['apply_started'] = False
                    row['apply_phase'] = 'preparing'
                if row['state'] in ('queued', 'preparing', 'applying', 'editing', 'checking'):
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
        def same_recording(row, job):
            source = job.get('source') or {}
            saved_url = row.get('url') or source.get('youtube_url')
            saved_assets = [row.get('asset'), (job.get('fadr') or {}).get('asset_id')]
            return bool((url and url == saved_url) or
                        (asset and str(asset) in {str(a) for a in saved_assets if a}))
        with self.guard:
            if self.server.STATE['state'] in self.server.ACTIVE_STATES:
                raise Conflict('Finish the import started by the previous interface first.')
            for row in self.jobs.values():
                if row['song'] == name:
                    job = ji.load_job(self.folder(row['id']))
                    if same_recording(row, job):
                        if row['state'] == 'removed':
                            row['state'] = row.pop('removed_state', 'cached')
                            self._save()
                            self.schedule()
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
                job = ji.load_job(folder)
                if same_recording({}, job):
                    row = self._record(job, str(folder), 'cached')
                    self.jobs[row['id']] = row
                    self._save()
                    return {'ok': True, 'id': row['id']}
                raise Conflict('Cached work already uses this title. Open it in the song list, or use a distinct title.')
            job = dict(schema=1, stages={}, band=band, title=title, region_name=name,
                       source={'youtube_url': url}, duration=body.get('duration') or 0)
            if asset:
                job['fadr'] = {'asset_id': str(asset)}
                job.setdefault('source', {})['from_fadr_library'] = True
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
        submit_token = ji.JOB_SUBMIT.set(lambda: self.check_remote_work(ident))
        try:
            folder = self.folder(ident)
            job, cfg = ji.load_job(folder), self.config(row)
            # Completed source/stem flags alone are not proof the files survived.
            stems_valid = bool(job.get('stems')) and all(
                (folder / stem['file']).is_file() and (folder / stem['file']).stat().st_size > 44
                for stem in job['stems'])
            if not row.get('asset') and not stems_valid and not (folder / job.get('source', {}).get('audio_file', 'source.wav')).is_file():
                job['stages'].pop('download', None)
            if not stems_valid:
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
                        ji.check_import_pause()
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
            ji.JOB_SUBMIT.reset(submit_token)
            with self.guard:
                self.running.discard(ident)
                self.schedule()

    def check_remote_work(self, ident):
        # A timed-out/local paused worker does not cancel its provider task.
        # Keep the remote budget conservative even across process restarts.
        with self.guard:
            for other, row in self.jobs.items():
                if other == ident or row['state'] in ('review', 'done', 'cached'):
                    continue
                job = ji.load_job(self.folder(other))
                if any(task.get('state') not in ('complete', 'failed') for task in job.get('fadr_tasks', {}).values()):
                    raise RuntimeError('Another saved Fadr task may still be running for ' + row['song'] +
                                       '. Resume/check that song first, then retry this one. No new split was submitted.')

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

    def recover_provider(self, ident, body):
        """Read existing provider state. Never create an upload or split here."""
        with self.guard:
            row = self.jobs[ident]
            if row['state'] not in ('failed', 'interrupted', 'paused') or row.get('apply_started'):
                raise Conflict('Pause/finish processing before checking its Fadr result')
            previous = row['state']
            row['state'] = 'checking'
            self._save()
        try:
            folder = self.folder(ident)
            job = ji.load_job(folder)
            fadr = ji.Fadr(self.config(row)['fadr_api_key'])
            asset_id = body.get('asset')
            if asset_id:
                known = job.get('fadr', {}).get('asset_id')
                if known and known != asset_id:
                    raise Conflict('This job already owns a different Fadr asset; check its existing task instead.')
                asset = fadr.asset(str(asset_id))
                if not asset.get('stems') or asset.get('assetType') != 'upload':
                    raise ValueError('Choose a completed original recording from the Fadr library')
                job.setdefault('fadr', {})['asset_id'] = str(asset_id)
                job.pop('upload_pending', None)
                job.setdefault('source', {})['from_fadr_library'] = True
                job['stages']['download'] = True
                row['asset'] = str(asset_id)
            records = job.get('fadr_tasks', {})
            for key, task in records.items():
                if task.get('state') in ('complete', 'failed'):
                    continue
                asset = fadr.asset(task.get('asset') or key.split(':')[0])
                if asset.get('stems'):
                    task['state'] = 'complete'
                elif task.get('id'):
                    data = fadr._check(fadr._read('post', ji.FADR_API + '/tasks/query', json={'_ids':[task['id']]}), 'check saved task')
                    found = next((t for t in data.get('tasks', []) if t.get('_id') == task['id']), None)
                    status = found and found.get('status')
                    if isinstance(status, dict) and (status.get('failed') is True or status.get('complete') is True and status.get('error')):
                        task['state'] = 'failed'
                        task['error'] = str(status.get('msg') or status.get('error') or 'Provider reported failure')
            failed = [k for k, t in records.items() if t.get('state') == 'failed']
            pending = [k for k, t in records.items() if t.get('state') not in ('complete', 'failed')]
            if body.get('retry_failed'):
                if not failed or pending or job.get('upload_pending'):
                    raise Conflict('Only provider-confirmed failed tasks can be replaced; unresolved submissions must be checked first.')
                job.setdefault('fadr_task_history', []).extend(records[k] for k in failed)
                for key in failed:
                    del records[key]
                failed = []
            ji.save_job(folder, job)
            text = ('Upload needs checking. Select its completed recording from the Fadr library below.' if job.get('upload_pending') else
                    'Fadr still has an unresolved task. Wait, then check again; no replacement split was submitted.' if pending else
                    'Fadr confirmed a failed task. You can explicitly retry it; a new split may be charged.' if failed else
                    'Saved Fadr results checked. Resume this song to continue.')
            with self.guard:
                row.update(summary=text, provider_retryable=bool(failed and not pending), revision=row['revision'] + 1)
            return {'ok':True, 'summary':text, 'retryable':row['provider_retryable']}
        finally:
            with self.guard:
                row['state'] = previous
                self._save()

    def draft(self, ident, body):
        with self.guard:
            row = self.jobs[ident]
            if row['state'] != 'review' or row.get('apply_started'):
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
            row['apply_prepared'] = False
            row['revision'] += 1
            self._save()
            return {'ok': True, 'revision': row['revision']}

    def choose(self, ident, action, body):
        with self.guard:
            row = self.jobs[ident]
            if row['state'] != 'review' or row.get('apply_started') or body.get('revision') != row['revision']:
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
            if action == 'pause':
                if row['state'] != 'queued':
                    raise Conflict('Only a queued song can be paused individually. Use Pause queue for active work.')
                row['state'] = 'paused'
                self._save()
                return {'ok': True}
            if action == 'first':
                if row['state'] != 'queued':
                    raise Conflict('This song is no longer queued')
                self.jobs = {ident:row, **{k:v for k,v in self.jobs.items() if k != ident}}
                self._save()
                return {'ok': True}
            if action == 'resume':
                if row['state'] == 'cached' and self.server.BUSY.locked():
                    raise Conflict('Let the current library change finish before reopening cached work.')
                if row.get('apply_started'):
                    raise Conflict('This Apply needs checking. Open its target project and use Check Apply.')
                if row['state'] not in ('failed', 'interrupted', 'paused', 'cached'):
                    return {'ok': True}
                row.update(state='queued', summary='')
                self._save()
                self.schedule()
                return {'ok': True}
            if action == 'remove':
                if ident in self.running or row['state'] in ('applying', 'editing', 'checking'):
                    raise Conflict('Pause the queue and let this stage finish before removing the song')
                job = ji.load_job(self.folder(ident))
                if row['state'] not in ('review', 'done', 'cached') and any(
                        task.get('state') not in ('complete', 'failed') for task in job.get('fadr_tasks', {}).values()):
                    raise Conflict('This song has an unresolved Fadr task. Resume/check it before removing its workspace.')
                row['removed_state'] = row['state']
                row['state'] = 'removed'
                self._save()
                return {'ok': True}
            if body.get('revision') != row['revision']:
                raise Conflict('This review changed. Reopen it before continuing.')
            if action == 'reopen':
                if row['state'] != 'done':
                    raise Conflict('Only completed imports can be reopened for another project')
                if self.server.BUSY.locked():
                    raise Conflict('Let the current library change finish before reopening this review.')
                row.update(state='review', target='', operation=uuid.uuid4().hex,
                           apply_started=False, apply_prepared=False, summary='', revision=row['revision'] + 1)
                self._save()
                return {'ok': True}
            if action == 'target':
                if row['state'] != 'review':
                    raise Conflict('Wait until review is ready')
                if row.get('apply_started'):
                    raise Conflict('An Apply is unresolved. Reopen the original target project and retry there.')
                row['target'] = self.server.project_identity()
                row['apply_prepared'] = False
                row['revision'] += 1
                self._save()
                return {'ok': True, 'revision': row['revision'], 'target': row['target']}
            if action == 'apply':
                if row['state'] != 'review' and not (row['state'] == 'interrupted' and row.get('apply_started')):
                    raise Conflict('This job is not ready to apply')
                if not row['target'] or self.server.project_identity() != row['target']:
                    raise Conflict('Open the intended project, or explicitly select the current project as the target.')
                if not self.server.BUSY.acquire(blocking=False):
                    raise Conflict('Another REAPER change is running. Try again when it finishes.')
                old_state = row['state']
                try:
                    row.update(state='applying', apply_phase='submitted' if row.get('apply_started') else 'preparing')
                    self._save()
                    threading.Thread(target=self.apply, args=(ident,), daemon=True).start()
                except Exception:
                    row['state'] = old_state
                    self.server.BUSY.release()
                    raise
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
            if not row.get('apply_prepared'):
                with self.analysis:
                    ji.stage_mixdown(job, folder, cfg, True)
                    ji.write_reaper_job(job, folder)
                with self.guard:
                    row['apply_prepared'] = True
                    self._save()
            with self.guard:
                row.update(apply_started=True, apply_phase='submitted')
                self._save()  # Durable intent precedes the shared REAPER request.
            ji.stage_apply(job, folder, cfg, True)
            if not (folder / 'applied.txt').is_file():
                raise RuntimeError('REAPER did not confirm Apply. Open the intended project, stop playback/recording, then retry. The same operation ID prevents a duplicate append.')
            with self.guard:
                level = job.get('level') or {}
                note = (f' Matched playback level: {level["gain"]:.0%}.' if level.get('status')=='measured' else
                        ' Volume matching: ' + level.get('reason','not measured') + '.')
                row.update(state='done', apply_phase='confirmed', summary='Added to REAPER.' + note + ' Save the project to keep it.')
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
            if body.get('open_cached'):
                for row in self.jobs.values():
                    if row['song'] == body['open_cached']:
                        if row['state'] == 'removed':
                            row['state'] = row.pop('removed_state', 'cached')
                            self._save()
                            self.schedule()
                        return {'id':row['id']}
                raise ValueError('Cached song not found. Restart the importer to discover new files.')
            self.paused = bool(body.get('pause'))
            if not self.paused:
                for row in self.jobs.values():
                    if (row['state'] == 'paused' or body.get('resume') and row['state'] in ('interrupted', 'failed')) and not row.get('apply_started'):
                        row['state'] = 'queued'
            self._save()
            self.schedule()
            return self.listing()
