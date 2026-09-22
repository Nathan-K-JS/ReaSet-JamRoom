"""Preserve brief audio, migrate old reviews, and verify browser audition clocks."""
import copy
import json
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np
import requests
from playwright.sync_api import sync_playwright

import jamroom_import as ji
import jamroom_importer_server as server
import test_import_queue as queue_tests
from jamroom_import_queue import ImportQueue


def wav(path, samples, rate=8000):
    path.parent.mkdir(parents=True, exist_ok=True)
    data=np.asarray(samples, dtype='<i2')
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(data.shape[1] if data.ndim==2 else 1)
        out.setsampwidth(2);out.setframerate(rate);out.writeframes(data.tobytes())


class StemAudioTests(unittest.TestCase):
    def test_only_digital_silence_is_excluded_and_stereo_does_not_cancel(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'stem.wav';burst=np.zeros(80000,dtype='<i2');burst[40000]=20000
            for name,data,slot in [('silent',burst*0,'SKIP'),('burst',burst,'EXTRA'),
                    ('quiet',np.ones(80000,dtype='<i2'),'EXTRA'),
                    ('stereo',np.tile([1000,-1000],(80000,1)),'KEYS')]:
                wav(path,data);p=ji.stem_profile(path)
                self.assertEqual(ji.stem_destination({'file':'stem.wav','fadr_name':'piano'}, {},
                    {'slot_map':{'piano':'KEYS'}},p),slot,name)
                self.assertEqual(p['digital_silence'],name=='silent')
                self.assertAlmostEqual(p['duration'],10)
            self.assertEqual(ji.stem_destination({'file':'new.wav','fadr_name':'unknown'}, {}, {'slot_map':{}}, {}),'EXTRA')

    def test_truncated_riff_and_stale_profile_are_not_trusted(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'stem.wav';wav(path,np.ones(8000,dtype='<i2'))
            path.with_name('stem.wav.profile.json').write_text(json.dumps({'verdict':'silent','duration':9999}))
            self.assertFalse(ji.stem_profile(path)['digital_silence'])
            path.write_bytes(path.read_bytes()[:-100])
            with self.assertRaises(ValueError):ji.wav_info(path)

    def test_extras_sum_keeps_all_brief_events(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td);a=np.zeros(8000,dtype='<i2');a[2000]=10000
            b=np.zeros(8000,dtype='<i2');b[5000]=12000
            wav(folder/'stems/a.wav',a);wav(folder/'stems/b.wav',b)
            job={'stages':{},'duration':1,'stems':[{'file':'stems/a.wav','fadr_name':'piano'}, {'file':'stems/b.wav','fadr_name':'wind'}]}
            with patch.object(ji.click_model,'add_slot',return_value={'review':'fixture'}),patch.object(ji,'save_job'):
                ji.stage_mixdown(job,folder,{'slot_map':{'piano':'KEYS'},'slot_labels':{'EXTRA':'Extras'}},True)
            self.assertEqual(len(job['slots']),1);self.assertEqual(job['slots'][0]['slot'],'EXTRA')
            with wave.open(str(folder/job['slots'][0]['file']),'rb') as audio:
                mixed=np.frombuffer(audio.readframes(audio.getnframes()),dtype='<i2')
            np.testing.assert_allclose(mixed,a.astype(np.int32)+b,atol=1)


class StemMigrationTests(unittest.TestCase):
    setUp=queue_tests.QueueTests.setUp
    add=queue_tests.QueueTests.add
    review=queue_tests.QueueTests.review

    def test_migrate_once_preserve_chart_and_do_not_repeat_explicit_exclusion(self):
        ident=self.add();row=self.review(ident);row.pop('stem_policy')
        folder=self.queue.folder(ident);wav(folder/'stems/bass.wav',np.ones(8000,dtype='<i2'))
        row['draft']={'slots':{'stems/bass.wav':'SKIP'},'chart_document':{'sentinel':'authored'},'lyrics_offset':1.5}
        self.bridge.build_review.side_effect=server.build_review
        first=self.queue.detail(ident)
        self.assertEqual(first['draft']['slots']['stems/bass.wav'],'EXTRA')
        self.assertEqual(first['draft']['chart_document'],{'sentinel':'authored'})
        self.assertEqual(first['draft']['lyrics_offset'],1.5)
        self.assertIn('Recovered 1',first['summary'])
        self.assertIn('v=',first['review']['stems'][0]['audio'])
        self.assertIn('job='+ident,first['review']['stems'][0]['audio'])
        row['draft']['slots']['stems/bass.wav']='SKIP';self.queue._save()
        restarted=ImportQueue(self.bridge,self.cfg)
        again=restarted.detail(ident)
        self.assertEqual(again['draft']['slots']['stems/bass.wav'],'SKIP')
        self.assertEqual(first['revision'],again['revision'])
        self.assertEqual(self.bridge.build_review.call_count,1)

    def test_unresolved_apply_cannot_be_migrated(self):
        ident=self.add();row=self.review(ident);row.pop('stem_policy')
        row.update(apply_started=True,apply_prepared=True)
        before=copy.deepcopy(row)
        self.queue.detail(ident)
        self.assertEqual(row,before);self.bridge.build_review.assert_not_called()

    def test_explicit_new_policy_exclusion_survives_new_cached_workspace(self):
        ident=self.add();row=self.review(ident);row.pop('stem_policy')
        folder=self.queue.folder(ident);wav(folder/'stems/bass.wav',np.ones(8000,dtype='<i2'))
        job=ji.load_job(folder)
        job.update(stem_policy=ji.STEM_REVIEW_POLICY,slot_overrides={'stems/bass.wav':'SKIP'},slot_origins={'stems/bass.wav':'explicit'})
        ji.save_job(folder,job);self.bridge.build_review.side_effect=server.build_review
        self.assertEqual(self.queue.detail(ident)['draft']['slots']['stems/bass.wav'],'SKIP')


class StemServingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name);wav(self.folder/'stems/test.wav',np.zeros(80000,dtype='<i2'))
        self.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        self.worker=threading.Thread(target=self.http.serve_forever,daemon=True);self.worker.start()
        self.addCleanup(self.http.server_close);self.addCleanup(self.http.shutdown)
        self.base='http://127.0.0.1:'+str(self.http.server_port)
        fake=type('Queue',(),{'folder':lambda _,ident:self.folder})()
        self.mock=patch.object(server,'import_queue',return_value=fake);self.mock.start();self.addCleanup(self.mock.stop)

    def test_actual_preview_handler_ranges_and_head(self):
        url=self.base+'/api/audio?job=test&f=test.wav';data=(self.folder/'stems/test.wav').read_bytes()
        for header,expected in [('bytes=0-1',data[:2]),('bytes=90-99',data[90:100]),('bytes=-7',data[-7:]),('bytes=160040-',data[160040:])]:
            r=requests.get(url,headers={'Range':header},timeout=5)
            self.assertEqual(r.status_code,206);self.assertEqual(r.content,expected)
            self.assertEqual(r.headers['Content-Type'],'audio/wav')
        r=requests.get(url,headers={'Range':'bytes=999999-'},timeout=5)
        self.assertEqual(r.status_code,416)
        r=requests.head(url,headers={'Range':'bytes=0-1'},timeout=5)
        self.assertEqual(r.status_code,206);self.assertEqual(r.content,b'')
        self.assertEqual(r.headers['Content-Length'],'2')

    def test_browser_metadata_and_audible_landmark_after_seek(self):
        # Distinct frequencies prove the decoded content at the seek, not just currentTime.
        rate=8000;t=np.arange(rate*10)/rate
        signal=(np.sin(2*np.pi*np.where(t<5,250,1000)*t)*12000).astype('<i2')
        wav(self.folder/'stems/test.wav',signal)
        html=(ji.REPO_ROOT/'tools/importer.html').read_text(encoding='utf-8')
        functions=html[html.index('function stemBadge('):html.index('function showReview(')]
        with sync_playwright() as pw:
            for engine in ['chromium','webkit']:
                browser=getattr(pw,engine).launch(**({'channel':'msedge'} if engine=='chromium' else {}))
                try:
                    page=browser.new_page();page.goto(self.base+'/missing')
                    page.set_content('<div><canvas style="width:600px"></canvas><audio controls preload="none"></audio><output class="preview-clock"></output><span class="preview-status"></span></div>')
                    page.add_script_tag(content=functions)
                    p=ji.stem_profile(self.folder/'stems/test.wav')
                    page.evaluate('''p=>{window.a=document.querySelector('audio');a.src='/api/audio?job=test&f=test.wav';drawWave(document.querySelector('canvas'),{name:'Fixture',profile:p},a);
                      if(!(window.AudioContext||window.webkitAudioContext))return;window.ctx=new (window.AudioContext||window.webkitAudioContext)();window.analyser=ctx.createAnalyser();analyser.fftSize=2048;
                      ctx.createMediaElementSource(a).connect(analyser);const silent=ctx.createGain();silent.gain.value=0;analyser.connect(silent);silent.connect(ctx.destination);
                    }''',p)
                    page.locator('canvas').focus();page.locator('canvas').press('End');page.locator('canvas').press('ArrowLeft')
                    page.wait_for_function('a.readyState>=1 && Math.abs(a.currentTime-9)<.1')
                    self.assertAlmostEqual(page.evaluate('a.duration'),10,places=2)
                    if not page.evaluate('!!window.ctx'):
                        self.assertIn('/ 0:10.0',page.locator('.preview-clock').inner_text());continue
                    page.evaluate('async()=>{await ctx.resume();await a.play();}')
                    page.wait_for_timeout(350)
                    measured=page.evaluate('''()=>{const bins=new Float32Array(analyser.frequencyBinCount);analyser.getFloatFrequencyData(bins);let peak=0;for(let i=1;i<bins.length;i++)if(bins[i]>bins[peak])peak=i;return peak*ctx.sampleRate/analyser.fftSize;}''')
                    self.assertAlmostEqual(measured,1000,delta=35,msg=engine)
                    self.assertIn('/ 0:10.0',page.locator('.preview-clock').inner_text())
                finally:browser.close()


if __name__=='__main__':unittest.main()
