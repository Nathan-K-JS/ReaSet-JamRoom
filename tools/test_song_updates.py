"""Batch persistence, protection, partial failures and restart recovery."""
import copy
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import jamroom_import as ji
from jamroom_updates import Updates, read, write


class ImmediateThread:
    def __init__(self, target, args, **kwargs): self.target,self.args=target,args
    def start(self): self.target(*self.args)


class UpdateTests(unittest.TestCase):
    def fake_click(self,job,folder,*args):
        file=Path(folder)/'test-click.wav'
        ji.click_model.render(file,[0,1,2],job['duration'])
        job['click']={'file':file.name,'generator':ji.click_model.GENERATOR,'muted':False,
                      'quality':{'status':'checks_passed'},'review':'Automatic timing checks passed'}
        return job['click']

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.folder=Path(self.tmp.name)
        self.cfg={'jobs_dir':str(self.folder)}
        self.root=self.folder/'.updates'/'P'; self.root.mkdir(parents=True)
        self.songs=[]
        for i in (1,2):
            folder=self.folder/('Song'+str(i))
            ji.save_job(folder, {'duration':60,'stages':{},'fadr':{'sample_rate':44100,'beat_length_samples':22050,'beat_offset_samples':0},'lyrics':{'synced':True,
                'lines':[{'time':10,'text':'Song words'},{'time':20,'text':''}]},
                'chords_detected':[{'start':0,'end':30,'chord':'C'}]})
            self.songs.append({'id':i,'name':folder.name,'start':(i-1)*60,'end':i*60,
                               'folder':str(folder),'review_status':''})
        self.push=Mock(side_effect=self.fake_push)
        self.up=Updates(lambda cfg:'P',lambda:copy.deepcopy(self.songs),self.push,threading.Lock(),{'state':'idle'})
        self.up.song_state=Mock(return_value={})
        self.patches=[patch.object(ji,'load_config',return_value=self.cfg),
                      patch.object(ji.click_model,'ensure_click',side_effect=self.fake_click),
                      patch.object(ji,'stage_lyrics_align'),
                      patch('jamroom_updates.threading.Thread',ImmediateThread),
                      patch('jamroom_updates.requests.get',return_value=Mock(text='TRANSPORT\t0\t0'))]
        for p in self.patches:p.start()

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def fake_push(self,*args,operation_dir,**kwargs):
        write(operation_dir/'before.json', {'old':'snapshot'})
        write(operation_dir/'after.json', {'new':'snapshot'})

    def batch(self):return self.up.listing()['batch']

    def test_installed_fallback_remains_eligible_for_whole_library_retry(self):
        folder=Path(self.songs[0]['folder']);job=ji.load_job(folder)
        click=ji.click_model.ensure_click(job,folder)
        click['analysis_unavailable']=True
        ji.save_job(folder,job)
        self.up.song_state.return_value={'song:1:click':click['generator']+':'+click['file']}
        song=self.up.listing()['songs'][0]
        self.assertFalse(song['click_current'])
        self.assertTrue(song['click_eligible'])
        self.assertIn('Automatic',song['click_status'])

    def test_protected_and_missing_sources_are_not_preselected(self):
        self.up.protect(1,'Song1',True)
        Path(self.songs[1]['folder'],'job.json').unlink()
        listing=self.up.listing()['songs']
        self.assertFalse(any(s['eligible'] for s in listing))
        self.assertEqual(listing[1]['update_status'],'Source files missing')
        with self.assertRaises(ValueError):self.up.start([1])
        self.assertFalse(self.up.busy.locked())

    def test_current_and_manual_revision_are_distinguished(self):
        folder=Path(self.songs[0]['folder']);job=ji.load_job(folder)
        job['generation']={'generator':ji.chart_model.GENERATOR,'revision':'generated'};ji.save_job(folder,job)
        self.up.song_state.return_value={'song:1:revision':'generated'}
        self.assertTrue(self.up.listing()['songs'][0]['current'])
        self.up.song_state.return_value={'song:1:revision':'manual'}
        self.up.start([1])
        self.assertEqual(self.batch()['songs'][0]['status'],'failed')
        self.push.assert_not_called()

    def test_failure_continues_and_resume_only_retries_failed_song(self):
        def failing(*args,**kwargs):
            if args[2]['id']==1:raise RuntimeError('injected failure')
            self.fake_push(*args,**kwargs)
        self.push.side_effect=failing
        before=Path(self.songs[0]['folder'],'job.json').read_bytes()
        self.up.start([1,2])
        self.assertEqual([s['status'] for s in self.batch()['songs']],['failed','done'])
        self.assertEqual(Path(self.songs[0]['folder'],'job.json').read_bytes(),before)
        self.push.side_effect=self.fake_push;self.push.reset_mock()
        self.up.start(resume=True)
        self.assertEqual([s['status'] for s in self.batch()['songs']],['done','done'])
        self.assertEqual(self.push.call_count,1)
        self.assertFalse(self.up.busy.locked())

    def test_restore_retry_freezes_the_original_target(self):
        original=Path(self.songs[0]['folder'],'job.json').read_bytes()
        self.up.start([1]);self.up.start([1],restore=True)
        batch=self.batch();item=batch['songs'][0]
        first_target=self.push.call_args.kwargs['restore']
        self.up.update_one(self.cfg,self.root,batch,item)
        self.assertEqual(self.push.call_args.kwargs['restore'],first_target)
        self.assertEqual(Path(item['folder'],'job.json').read_bytes(),original)

    def test_project_switch_rejected_and_playback_pauses(self):
        with self.assertRaisesRegex(ValueError,'Project changed'):
            self.up.start([1],target_project='another')
        with patch('jamroom_updates.requests.get',return_value=Mock(text='TRANSPORT\t1\t0')):
            self.up.start([1])
        self.assertEqual(self.batch()['status'],'paused');self.push.assert_not_called()

    def test_timing_fixes_require_explicit_replacement(self):
        self.songs[0]['review_status']='Timing adjusted · drift corrected'
        self.up.start([1]);self.push.assert_not_called()
        self.up.start([1],replace_edits=True)
        self.assertEqual(self.batch()['songs'][0]['status'],'done')

    def test_click_only_updates_kept_manual_chart_without_regenerating_it(self):
        self.up.protect(1,'Song1',True)
        self.songs[0]['review_status']='Timing adjusted'
        with patch.object(ji,'prepare_chart_document') as generate:
            self.up.start([1],clicks_only=True)
        self.assertEqual(self.batch()['songs'][0]['status'],'done')
        generate.assert_not_called()
        arguments=self.push.call_args.kwargs
        self.assertIsNone(arguments['document']);self.assertIsNone(arguments['chords']);self.assertIsNone(arguments['lyric_lines'])
        self.assertTrue(Path(arguments['click']['file']).is_file())

    def test_listening_acceptance_uses_reviewed_file_without_regenerating_or_editing_chart(self):
        folder=Path(self.songs[0]['folder']);job=ji.load_job(folder)
        click=self.fake_click(job,folder);click['muted']=True;ji.save_job(folder,job)
        token=click['generator']+':'+click['file']
        self.up.protect(1,'Song1',True)
        with patch.object(ji.click_model,'ensure_click',side_effect=AssertionError('Do not replace the auditioned click')):
            self.up.start([1],clicks_only=True,approve_click=token)
        self.assertEqual(self.batch()['songs'][0]['status'],'done')
        self.assertFalse(self.push.call_args.kwargs['click']['muted'])
        self.assertIsNone(self.push.call_args.kwargs['document'])
        self.assertTrue(ji.load_job(folder)['click']['listening_approved'])

    def test_accepting_a_stale_listening_report_does_not_change_reaper(self):
        self.up.start([1],clicks_only=True,approve_click='wrong-file')
        self.assertEqual(self.batch()['songs'][0]['status'],'failed')
        self.push.assert_not_called()

    def test_batch_write_retries_windows_reader_lock_without_truncating_old_state(self):
        target=self.folder/'progress.json';write(target,{'status':'old'})
        real=Path.replace;attempts=[]
        def briefly_locked(path,destination):
            attempts.append(path)
            if len(attempts)<3:
                self.assertEqual(read(target),{'status':'old'})
                raise PermissionError('Windows reader lock')
            return real(path,destination)
        with patch.object(Path,'replace',briefly_locked),patch('jamroom_updates.time.sleep'):
            write(target,{'status':'done'})
        self.assertEqual(read(target),{'status':'done'})
        self.assertEqual(len(attempts),3)

    def test_permanent_progress_failure_still_releases_worker_ownership(self):
        batch={'id':'broken','project':'P','songs':[],'status':'running'}
        self.up.active='broken';self.up.busy.acquire()
        with patch('jamroom_updates.write',side_effect=PermissionError('disk locked')):
            with self.assertRaises(PermissionError):self.up.run(self.cfg,self.root,batch)
        self.assertIsNone(self.up.active)
        self.assertFalse(self.up.busy.locked())


if __name__=='__main__':unittest.main()
