"""Restart, concurrent edits, isolation, and paid-task recovery regressions."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

import jamroom_import as ji
import jamroom_importer_server as server
from jamroom_import_queue import ImportQueue, Conflict


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cfg = {'jobs_dir': self.temp.name, 'slot_map': {'bass':'BASS'},
                    'slot_labels': {'BASS':'Bass'}, 'vocal_split':False, 'melodic_split':False,
                    'fadr_api_key':'secret'}
        self.config = patch.object(ji, 'load_config', return_value=self.cfg)
        self.config.start(); self.addCleanup(self.config.stop)
        self.bridge = Mock(STATE={'state':'idle'}, ACTIVE_STATES=server.ACTIVE_STATES,
                           SLOT_CHOICES=server.SLOT_CHOICES, BUSY=threading.Lock())
        self.bridge.project_identity.return_value = 'project-A'
        self.bridge.project_songs.return_value = []
        self.bridge.build_review.return_value = {'stems':[], 'vocal_audio':'/api/audio?f=bass.wav'}
        self.queue = ImportQueue(self.bridge, self.cfg)
        self.queue.paused = True

    def add(self, title='Song'):
        return self.queue.add({'band':'Band', 'title':title, 'url':'https://example.test/' + title})['id']

    def review(self, ident):
        row = self.queue.jobs[ident]
        folder = self.queue.folder(ident)
        job = ji.load_job(folder)
        (folder/'stems').mkdir(exist_ok=True)
        (folder/'stems/bass.wav').write_bytes(b'RIFFtest')
        job.update(stems=[{'file':'stems/bass.wav', 'fadr_name':'bass'}])
        job['stages'].update(download=True, fadr=True)
        ji.save_job(folder, job)
        row.update(state='review', review=self.bridge.build_review.return_value)
        self.queue._save()
        return row

    def test_update_drain_blocks_new_work_and_waits_for_workers(self):
        import requests
        http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        url = 'http://127.0.0.1:' + str(http.server_port)
        try:
            with patch.object(server, 'QUEUE', self.queue), patch.object(server, 'UPDATES', Mock()):
                self.queue.running.add('worker')
                result = requests.post(url + '/api/drain', json={}, timeout=5)
                self.assertFalse(result.json()['ready'])
                self.assertTrue(self.queue.paused)
                result = requests.post(url + '/api/jobs', json={}, timeout=5)
                self.assertEqual(result.status_code, 503)
                self.queue.running.clear()
                self.assertTrue(requests.get(url + '/api/drain', timeout=5).json()['ready'])
                requests.post(url + '/api/drain', json={'resume':True}, timeout=5).raise_for_status()
                self.assertFalse(server.DRAIN.is_set())
                self.assertTrue(self.queue.paused)
        finally:
            server.DRAIN.clear()
            http.shutdown(); http.server_close(); thread.join()

    def test_duplicate_add_and_separate_recording_conflict(self):
        ident = self.add()
        self.assertEqual(self.add(), ident)
        with self.assertRaises(Conflict):
            self.queue.add({'band':'Band', 'title':'Song', 'url':'different'})
        self.assertEqual(len(self.queue.jobs), 1)
        self.assertNotIn('secret', self.queue.path.read_text())

    def test_removed_youtube_review_reopens_from_its_fadr_asset(self):
        ident=self.add();row=self.review(ident)
        folder=self.queue.folder(ident);job=ji.load_job(folder)
        job['fadr']={'asset_id':'asset-one'};ji.save_job(folder,job)
        row['draft']={'lyrics_offset':1.25};self.queue._save()
        self.queue.action(ident,'remove',{})
        reopened=ImportQueue(self.bridge,self.cfg);reopened.paused=True
        with patch.object(ji,'Fadr') as fadr:
            result=reopened.add({'band':'Band','title':'Song','asset':'asset-one'})
            self.assertEqual(result['id'],ident)
            self.assertEqual(reopened.jobs[ident]['state'],'review')
            self.assertEqual(reopened.jobs[ident]['draft'],{'lyrics_offset':1.25})
            fadr.assert_not_called()
        with self.assertRaises(Conflict):
            reopened.add({'band':'Band','title':'Song','asset':'different-asset'})

    def test_unfinished_and_legacy_cached_fadr_work_can_be_selected_again(self):
        ident=self.add();self.review(ident)
        folder=self.queue.folder(ident);job=ji.load_job(folder)
        job['fadr']={'asset_id':'asset-one'};ji.save_job(folder,job)
        body={'band':'Band','title':'Song','asset':'asset-one'}
        self.assertEqual(self.queue.add(body)['id'],ident)
        self.queue.jobs={};self.queue._save()
        recovered=self.queue.add(body)['id']
        self.assertEqual(self.queue.jobs[recovered]['state'],'cached')
        self.assertEqual(self.queue.jobs[recovered]['asset'],'asset-one')

    def test_draft_survives_restart_and_rejects_stale_browser(self):
        ident = self.add(); self.review(ident)
        draft = {'slots':{'stems/bass.wav':'SKIP'}, 'labels':{'stems/bass.wav':'Custom'}, 'lyrics_offset':1.25}
        self.queue.draft(ident, {'revision':0, 'draft':draft})
        restored = ImportQueue(self.bridge, self.cfg)
        self.assertEqual(restored.detail(ident)['draft'], draft)
        self.assertEqual(restored.jobs[ident]['state'], 'review')
        self.assertIn('job=' + ident, restored.detail(ident)['review']['vocal_audio'])
        with self.assertRaises(Conflict):
            restored.draft(ident, {'revision':0, 'draft':{}})

    def test_crashed_work_is_paused_without_remote_requests(self):
        ident = self.add(); self.queue.jobs[ident]['state'] = 'preparing'; self.queue._save()
        with patch.object(ji, 'Fadr') as fadr:
            restored = ImportQueue(self.bridge, self.cfg)
            self.assertEqual(restored.jobs[ident]['state'], 'interrupted')
            self.assertFalse(restored.running)
            fadr.assert_not_called()

    def test_corrupt_queue_recovers_previous_checkpoint(self):
        ident = self.add(); self.queue._save()
        self.queue.path.write_text('{broken')
        restored = ImportQueue(self.bridge, self.cfg)
        self.assertIn(ident, restored.jobs)

    def test_remove_keeps_media_and_known_cache_is_not_rediscovered(self):
        ident = self.add(); self.review(ident)
        self.queue.action(ident, 'remove', {})
        self.assertTrue((self.queue.folder(ident)/'stems/bass.wav').exists())
        restored = ImportQueue(self.bridge, self.cfg)
        self.assertEqual(restored.listing()['jobs'], [])

    def test_resumed_review_can_confirm_target_without_losing_draft(self):
        ident=self.add();row=self.review(ident)
        row['draft']={'slots':{'stems/bass.wav':'BASS'}}
        self.queue._save()
        resumed=ImportQueue(self.bridge,self.cfg)
        self.bridge.project_identity.return_value='project-B'
        result=resumed.action(ident,'check-target',{'revision':0})
        self.assertFalse(result['matches']);self.assertTrue(result['can_select'])
        self.bridge.project_identity.return_value='project-C'
        with self.assertRaises(Conflict):
            resumed.action(ident,'target',{'revision':0,'expected_project':'project-B'})
        self.assertEqual(resumed.jobs[ident]['target'],'project-A')
        resumed.action(ident,'target',{'revision':0,'expected_project':'project-C'})
        self.assertEqual(resumed.jobs[ident]['target'],'project-C')
        self.assertEqual(resumed.jobs[ident]['draft'],row['draft'])
        self.assertEqual(resumed.jobs[ident]['operation'],row['operation'])

    def test_project_change_refuses_apply_before_mutation(self):
        ident = self.add(); self.review(ident)
        self.bridge.project_identity.return_value = 'project-B'
        with self.assertRaises(Conflict):
            self.queue.action(ident, 'apply', {'revision':0})
        self.assertFalse(self.bridge.BUSY.locked())

    def test_unresolved_apply_cannot_change_project_or_resume_processing(self):
        ident = self.add(); row = self.review(ident)
        row['apply_started'] = True
        with self.assertRaises(Conflict):self.queue.action(ident, 'target', {'revision':0})
        with self.assertRaises(Conflict):self.queue.action(ident, 'resume', {})

    def test_two_workers_and_logs_are_isolated_with_one_failure(self):
        first, second, third = self.add('One'), self.add('Two'), self.add('Three')
        entered = threading.Barrier(3); release = threading.Event()
        def download(job, folder, url, force):
            if job['title'] != 'Three':
                entered.wait(timeout=5); release.wait(timeout=5)
            ji.log(job['title'])
            if job['title'] == 'One':raise RuntimeError('only One failed')
        with patch.object(ji, 'stage_download', side_effect=download), \
             patch.object(ji, 'stage_fadr'), patch.object(ji, 'stage_chords'), \
             patch.object(ji, 'stage_lyrics'), patch.object(ji, 'stage_lyrics_align'):
            self.queue.paused = False; self.queue.schedule()
            entered.wait(timeout=5)
            self.assertEqual(len(self.queue.running), 2)
            self.assertEqual(self.queue.jobs[third]['state'], 'queued')
            release.set()
            deadline = time.monotonic() + 5
            while self.queue.running and time.monotonic() < deadline:time.sleep(.01)
        self.assertFalse(self.queue.running)
        self.assertEqual(self.queue.jobs[first]['state'], 'failed')
        self.assertEqual(self.queue.jobs[second]['state'], 'review')
        self.assertEqual(self.queue.jobs[third]['state'], 'review')
        self.assertEqual(self.queue.jobs[first]['log'], ['One'])
        self.assertEqual(self.queue.jobs[second]['log'], ['Two'])

    def test_task_id_saved_before_wait_and_reused_after_restart(self):
        ident = self.add(); folder = self.queue.folder(ident); job = ji.load_job(folder)
        fadr = Mock(); fadr.asset.return_value = {'_id':'asset'}
        fadr.stem_task.return_value = {'_id':'task'}
        def interrupted(*args):
            self.assertEqual(ji.load_job(folder)['fadr_tasks']['asset:main']['id'], 'task')
            raise RuntimeError('shutdown')
        fadr.wait_task.side_effect = interrupted
        with self.assertRaises(RuntimeError):ji.resume_fadr_task(fadr, job, folder, 'asset')
        job = ji.load_job(folder)
        fadr.wait_task.side_effect = None
        fadr.asset.side_effect = [{'_id':'asset'}, {'_id':'asset', 'stems':['bass']}]
        ji.resume_fadr_task(fadr, job, folder, 'asset')
        self.assertEqual(fadr.stem_task.call_count, 1)
        fadr.wait_task.assert_called_with('task', 'main stem split')

    def test_lost_billable_response_never_resubmits(self):
        ident = self.add(); folder = self.queue.folder(ident); job = ji.load_job(folder)
        fadr = Mock(); fadr.asset.return_value = {'_id':'asset'}
        fadr.stem_task.side_effect = TimeoutError('response lost')
        with self.assertRaises(TimeoutError):ji.resume_fadr_task(fadr, job, folder, 'asset')
        with self.assertRaisesRegex(RuntimeError, 'needs checking'):
            ji.resume_fadr_task(fadr, ji.load_job(folder), folder, 'asset')
        self.assertEqual(fadr.stem_task.call_count, 1)
        fadr.asset.return_value = {'_id':'asset', 'stems':['bass']}
        self.assertEqual(ji.resume_fadr_task(fadr, ji.load_job(folder), folder, 'asset')['stems'], ['bass'])

    def test_paused_queue_does_not_submit_subsplit(self):
        ident = self.add(); folder = self.queue.folder(ident)
        token = ji.JOB_PAUSE.set(lambda: True)
        try:
            fadr = Mock()
            with self.assertRaises(ji.ImportPaused):ji.resume_fadr_task(fadr, ji.load_job(folder), folder, 'asset')
            fadr.stem_task.assert_not_called()
        finally:ji.JOB_PAUSE.reset(token)

    def test_unresolved_remote_task_keeps_budget_after_worker_exit(self):
        first, second = self.add('One'), self.add('Two')
        folder = self.queue.folder(first); job = ji.load_job(folder)
        job['fadr_tasks'] = {'asset:main':{'id':'task', 'state':'waiting'}}
        ji.save_job(folder, job)
        self.queue.jobs[first]['state'] = 'failed'
        with self.assertRaisesRegex(RuntimeError, 'may still be running'):
            self.queue.check_remote_work(second)
        with self.assertRaises(Conflict):self.queue.action(first, 'remove', {})
        self.queue.check_remote_work(first)  # Its own task can be reconciled.

    def test_apply_started_freezes_review_media_choices(self):
        ident = self.add(); row = self.review(ident); row['apply_started'] = True
        with self.assertRaises(Conflict):self.queue.draft(ident, {'revision':0, 'draft':{}})

    def test_preparation_failure_does_not_freeze_review(self):
        ident = self.add(); row = self.review(ident)
        with patch.object(ji, 'stage_mixdown', side_effect=RuntimeError('disk full')):
            self.queue.action(ident,'apply',{'revision':0})
            deadline = time.monotonic()+5
            while self.bridge.BUSY.locked() and time.monotonic()<deadline:time.sleep(.01)
        self.assertEqual(row['state'],'review')
        self.assertFalse(row.get('apply_started'))
        self.queue.draft(ident,{'revision':0,'draft':{}})
        self.queue.action(ident,'target',{'revision':1})

    def test_provider_check_releases_failed_task_without_resubmitting(self):
        ident = self.add(); row = self.queue.jobs[ident];row['state']='failed'
        folder=self.queue.folder(ident);job=ji.load_job(folder)
        job['fadr_tasks']={'asset:main':{'asset':'asset','id':'task','state':'waiting'}}
        ji.save_job(folder,job)
        with patch.object(ji,'Fadr') as constructor:
            fadr=constructor.return_value;fadr.asset.return_value={'_id':'asset'}
            fadr._check.return_value={'tasks':[{'_id':'task','status':{'failed':True}}]}
            result=self.queue.recover_provider(ident,{})
            self.assertTrue(result['retryable'])
            fadr.stem_task.assert_not_called();fadr.upload.assert_not_called()
            self.assertEqual(ji.load_job(folder)['fadr_tasks']['asset:main']['state'],'failed')
            self.queue.recover_provider(ident,{'retry_failed':True})
            self.assertEqual(ji.load_job(folder)['fadr_tasks'],{})
            fadr.stem_task.assert_not_called()

    def test_recover_completed_upload_without_reupload(self):
        ident=self.add();self.queue.jobs[ident]['state']='failed'
        folder=self.queue.folder(ident);job=ji.load_job(folder);job['upload_pending']=True;ji.save_job(folder,job)
        with patch.object(ji,'Fadr') as constructor:
            constructor.return_value.asset.return_value={'_id':'existing','assetType':'upload','stems':['stem']}
            self.queue.recover_provider(ident,{'asset':'existing'})
            constructor.return_value.upload.assert_not_called()
        job=ji.load_job(folder)
        self.assertNotIn('upload_pending',job)
        self.assertEqual(job['fadr']['asset_id'],'existing')

    def test_removed_workspace_can_be_reopened_from_library(self):
        ident = self.add(); self.review(ident)
        self.queue.action(ident, 'remove', {})
        self.assertEqual(self.queue.control({'open_cached':'Band - Song'})['id'], ident)
        self.assertEqual(self.queue.jobs[ident]['state'], 'review')

    def test_browser_switch_autosave_reload_and_conflicting_editor(self):
        from playwright.sync_api import sync_playwright
        from test_browser import EDGE
        if not EDGE.exists():self.skipTest('Edge is required')
        first, second = self.add('One'), self.add('Two')
        for ident in (first, second):
            row = self.review(ident)
            row['review'] = {'band':'Band', 'title':row['title'], 'stems':[
                {'file':'stems/bass.wav', 'name':'bass', 'slot':'BASS', 'label':'Bass',
                 'profile':{'error':'preview unavailable'}, 'audio':'/api/audio?f=bass.wav'}],
                'slot_choices':server.SLOT_CHOICES, 'slot_labels':{'BASS':'Bass'},
                'lyrics':{'suggested_offset':0}, 'chart':{}, 'chords_count':0}
        self.queue._save()
        http = server.ImporterServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
        try:
            with patch.object(server, 'QUEUE', self.queue), sync_playwright() as pw:
                browser = pw.chromium.launch(executable_path=str(EDGE), headless=True)
                page = browser.new_page(); errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.route('**/api/checks', lambda r:r.fulfill(json={'build':ji.BUILD, 'key':True, 'reaper':True}))
                page.goto('http://127.0.0.1:' + str(http.server_port))
                page.get_by_role('button', name='Open Band - One', exact=True).wait_for()
                self.assertFalse(page.get_by_role('button',name='Remove from queue',exact=True).first.is_visible())
                page.locator('#importQueue details[data-song] summary').first.click()
                page.once('dialog',lambda dialog:dialog.dismiss())
                page.get_by_role('button',name='Remove from queue',exact=True).first.click()
                self.assertEqual(self.queue.jobs[first]['state'],'review')
                page.get_by_role('button', name='Open Band - One', exact=True).click()
                page.locator('#stemList input.lbl').fill('My custom bass')
                page.locator('#stemList select').select_option('SKIP')
                page.locator('#lyrOffset').fill('1.25')
                page.get_by_role('button', name='Open Band - Two', exact=True).click()
                page.wait_for_function("document.getElementById('progTitle').textContent.includes('Band - Two')")
                page.get_by_role('button', name='Open Band - One', exact=True).click()
                page.wait_for_function("document.querySelector('#stemList select')?.value === 'SKIP'")
                self.assertEqual(page.locator('#stemList select').input_value(), 'SKIP')
                self.assertEqual(page.locator('#stemList input.lbl').input_value(), 'My custom bass')
                page.reload()
                page.wait_for_function("document.querySelector('#stemList select')?.value === 'SKIP'")
                self.assertEqual(page.locator('#lyrOffset').input_value(), '1.25')
                # Browser A holds an edit while browser B saves the same revision.
                page.locator('#stemList select').select_option('BASS')
                page.locator('#stemList input.lbl').fill('Unsaved browser A')
                revision = self.queue.jobs[first]['revision']
                self.queue.draft(first, {'revision':revision, 'draft':{'labels':{'stems/bass.wav':'Browser B'}}})
                page.wait_for_function("document.getElementById('queueSaved').textContent.includes('Could not save')")
                self.assertEqual(page.locator('#stemList input.lbl').input_value(), 'Unsaved browser A')
                self.assertEqual(self.queue.jobs[first]['draft']['labels']['stems/bass.wav'], 'Browser B')
                self.assertEqual(errors, [])
                browser.close()
        finally:
            http.shutdown(); http.server_close(); thread.join(timeout=3)


if __name__ == '__main__':unittest.main()
