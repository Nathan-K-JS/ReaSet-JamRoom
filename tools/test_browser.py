"""Real browser smoke tests with the REAPER wire transport stubbed locally."""
import json
import os
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright
import jamroom_chart as chart
import jamroom_import as importer

ROOT = Path(__file__).resolve().parent.parent
EDGE = Path(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)')) / 'Microsoft/Edge/Application/msedge.exe'


@unittest.skipUnless(EDGE.exists(), 'Microsoft Edge is required for these browser tests')
class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=str(EDGE), headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.page.set_default_timeout(5000)
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))

    def tearDown(self):
        self.page.close()
        self.assertEqual(self.errors, [])

    def load_reaset(self):
        def route(req):
            name = req.request.url.rsplit('/', 1)[-1]
            if name == 'main.js':
                req.fulfill(body='var sent=[];function wwr_req(x){sent.push(x)};function wwr_req_recur(){};function wwr_start(){}', content_type='text/javascript')
            elif name in ('ReaSet.html', 'Sortable.min.js'):
                req.fulfill(path=str(ROOT/name))
            else: req.fulfill(body='')
        self.page.route('**/*', route)
        self.page.goto('http://reaset.test/ReaSet.html')
        job = {'duration':60, 'lyrics':{'synced':True,'lines':[{'time':10,'text':'Here we sing'}, {'time':20,'text':''}, {'time':40,'text':'Here we sing'}]}}
        templates = chart.parse_chart('[Intro]\n[ch]C[/ch] [ch]G[/ch]\n[Verse]\n[ch]C[/ch]\nHere we sing\n[Solo]\n[ch]Am[/ch] [ch]F[/ch]')
        doc, _ = chart.build_document(job, templates, [])
        self.page.evaluate('''doc => {
          g_clData={schema:1,project:'test',song:{id:1,start:0,end:60},document:doc,
            chords:[[10,12,'C',10]],lyrics:[[10,20,'Here we sing',10]]};
          g_clHb={val:1,changedAt:Date.now()};currentPos=0;g_chordView='sheet';
          renderChordsView();renderLyricsView();
        }''', doc)

    def test_sections_instruments_editor_and_confirmation(self):
        self.load_reaset()
        self.assertIn('Intro', self.page.locator('#chords-live').inner_text())
        self.assertIn('C', self.page.locator('#chords-live').inner_text())
        self.page.evaluate('currentPos=25;renderChordsView();renderLyricsView()')
        self.assertIn('Solo', self.page.locator('#lyrics-live').inner_text())
        self.page.evaluate("openTimingRepair('lyrics');sectionSave();repairHandleReply(g_tr.pending+'|ok|Section saved')")
        self.assertIsNone(self.page.evaluate('g_tr.pending'))
        self.assertIn('Section saved', self.page.locator('#tr-status').inner_text())
        self.assertIn('|section|', self.page.evaluate('decodeURIComponent(sent[sent.length-1])'))

    def test_precise_chords_clear_during_rest_and_legacy_repair_opens(self):
        self.load_reaset()
        self.page.evaluate("g_chordView='big';g_preciseFollow=true;currentPos=15;renderChordsView()")
        self.assertIn('No chord sounding', self.page.locator('#chords-live').inner_text())
        self.page.evaluate("currentPos=10;renderChordsView()")
        self.assertEqual(self.page.locator('.cv-big').inner_text(), 'C')
        self.page.evaluate("g_clData.document=null;openTimingRepair('lyrics')")
        self.assertIn('Here we sing', self.page.locator('#tr-choices').inner_text())

    def test_empty_song_clears_previous_lyrics(self):
        self.load_reaset()
        self.page.evaluate('g_clData=null;renderLyricsView();renderChordsView()')
        self.assertEqual(self.page.locator('#lyrics-live').inner_text(), 'No lyrics for this song.')

    def setup_transport(self):
        self.load_reaset()
        self.page.clock.install()
        self.page.evaluate('''() => {
          displayList=[{id:'1',name:'A',start:0,end:60,duration:60},
                       {id:'2',name:'B',start:70,end:130,duration:60}];
          g_subRegionMap={};window.g_specialMarkersMap={};g_songOverrides={};
          currentPos=10;isPlaying=false;sent=[];
          document.getElementById('queueModeToggle').checked=false;
          document.getElementById('initSongMidiToggle').checked=true;
        }''')

    def test_normal_play_cancels_midi_initialisation_stop(self):
        self.setup_transport()
        self.page.evaluate('triggerMidi();togglePlay();sent=[]')
        self.page.clock.run_for(1000)
        self.assertNotIn(1016,self.page.evaluate('sent'))

    def test_stop_then_play_before_transport_ack_starts_instead_of_pausing(self):
        self.setup_transport()
        self.page.evaluate('isPlaying=true;smartStop();sent=[];togglePlay()')
        self.assertIn(1007,self.page.evaluate('sent'))
        self.assertNotIn(1008,self.page.evaluate('sent'))

    def test_stop_then_play_another_song_cancels_old_reposition(self):
        self.setup_transport()
        self.page.evaluate("smartStop();playRegion(70,'2');sent=[]")
        self.page.clock.run_for(1000)
        self.assertNotIn('SET/POS/0',self.page.evaluate('sent'))

    def test_import_render_does_not_send_transport_commands(self):
        self.setup_transport()
        self.page.evaluate('isPlaying=true;currentPos=59.9;updatePlaybackUI()')
        self.assertNotIn(1016,self.page.evaluate('sent'))

    def test_play_ignores_stale_end_of_song_poll(self):
        self.setup_transport()
        self.page.evaluate("togglePlay();sent=[];wwr_onreply('TRANSPORT\\t1\\t59.9\\t0\\n')")
        self.assertNotIn(1016,self.page.evaluate('sent'))

    def test_stop_cancels_delayed_next_song_start(self):
        self.setup_transport()
        self.page.evaluate("g_songOverrides={'1':{delayAfter:2}};wwr_onreply('TRANSPORT\\t1\\t59.9\\t0\\n');smartStop();sent=[]")
        self.page.clock.run_for(3000)
        self.assertNotIn(1007,self.page.evaluate('sent'))

    def test_auto_stop_fires_once_and_cues_without_midi_play_stop(self):
        self.setup_transport()
        self.page.evaluate("for(var i=0;i<5;i++)wwr_onreply('TRANSPORT\\t1\\t59.9\\t0\\n')")
        self.page.clock.run_for(1000)
        commands=self.page.evaluate('sent')
        self.assertEqual(commands.count(1016),1)
        self.assertIn('SET/POS/70',commands)
        self.assertNotIn(1007,commands)

    def test_native_play_cancels_pending_automatic_cue(self):
        self.setup_transport()
        self.page.evaluate("wwr_onreply('TRANSPORT\\t1\\t59.9\\t0\\n');wwr_onreply('TRANSPORT\\t0\\t0\\t0\\n');wwr_onreply('TRANSPORT\\t1\\t10\\t0\\n');sent=[]")
        self.page.clock.run_for(1000)
        self.assertEqual(self.page.evaluate('sent'),[])

    def test_slow_old_poll_cannot_stop_new_playback_after_timeout(self):
        self.setup_transport()
        self.page.evaluate('oldRequest=Date.now()-1;startPlayback();sent=[]')
        self.page.clock.fast_forward(5000)
        self.page.evaluate("wwr_onreply('TRANSPORT\\t1\\t59.9\\t0\\n',oldRequest)")
        self.assertNotIn(1016,self.page.evaluate('sent'))

    def test_background_timer_cannot_stop_later_play(self):
        self.setup_transport()
        self.page.evaluate("triggerMidi();playRegion(70,'2');sent=[]")
        self.page.clock.fast_forward(5000)
        self.assertNotIn(1016,self.page.evaluate('sent'))

    def test_song_chain_still_advances(self):
        self.setup_transport()
        self.page.evaluate("displayList[0].chain=true;wwr_onreply('TRANSPORT\\t1\\t59.9\\t0\\n')")
        self.assertIn('SET/POS/70',self.page.evaluate('sent'))
        self.assertNotIn(1016,self.page.evaluate('sent'))

    def test_region_change_cancels_pending_midi_stop(self):
        self.setup_transport()
        self.page.evaluate("g_transportRegions='old';triggerMidi();wwr_onreply('REGION_LIST\\nREGION\\tA\\t1\\t0\\t60\\t0\\nREGION_LIST_END\\n');sent=[]")
        self.page.clock.run_for(1000)
        self.assertNotIn(1016,self.page.evaluate('sent'))

    def test_transport_and_imported_regions_in_one_reply_use_new_boundaries(self):
        self.setup_transport()
        self.page.evaluate("g_transportRegions='old';wwr_onreply('TRANSPORT\\t1\\t59.9\\t0\\nREGION_LIST\\nREGION\\tA\\t1\\t0\\t65\\t0\\nREGION\\tB\\t2\\t70\\t130\\t0\\nREGION_LIST_END\\n')")
        self.assertNotIn(1016,self.page.evaluate('sent'))

    def test_importer_version_warning_matches_running_server(self):
        running = {'build': importer.BUILD, 'key': True, 'reaper': True}
        def route(req):
            if '/api/checks' in req.request.url:
                req.fulfill(json=running)
            elif '/api/' in req.request.url:
                req.fulfill(json={'songs': [], 'state': 'idle'})
            else:
                req.fulfill(path=str(ROOT/'tools/importer.html'))
        self.page.route('**/*', route)
        self.page.goto('http://importer.test/')
        self.page.wait_for_function("document.getElementById('verBadge').textContent.includes('v3.0')")
        self.assertEqual(self.page.evaluate('UI_BUILD'), importer.BUILD)
        self.assertTrue(self.page.locator('#staleWarn').is_hidden())
        for page_version, server_version, expected in [
            ('v2.1', 'v3.0', 'page is older'),
            ('v3.0', 'v2.1', 'running importer is older'),
            ('v3.0', 'v3.10', 'page is older'),
            ('v3.0', None, 'could not be matched'),
            ('v3.0', 'unknown', 'could not be matched'),
        ]:
            with self.subTest(page=page_version, server=server_version):
                message = self.page.evaluate('''versions => {
                    UI_BUILD = versions[0]; return importerVersionWarning(versions[1]);
                }''', [page_version, server_version])
                self.assertIn(expected, message)
                self.assertNotIn('Stop-Process', message)
        self.assertEqual(self.page.evaluate("importerVersionWarning('v3.0.0')"), '')

    def test_bulk_selection_and_protection(self):
        songs=[{'id':i,'name':'Song '+str(i),'eligible':i==1,'protected':i==2,'update_status':'Update available'} for i in (1,2,3)]
        posts=[]
        def route(req):
            url=req.request.url
            if '/api/updates/start' in url:
                posts.append(req.request.post_data_json);req.fulfill(json={'id':'batch'})
            elif '/api/updates' in url:req.fulfill(json={'project':'test','songs':songs,'batch':None})
            elif '/api/' in url:req.fulfill(json={'songs':[],'state':'idle'})
            elif url.split('#')[0].endswith('/'):
                req.fulfill(path=str(ROOT/'tools/importer.html'))
            else:req.fulfill(body='')
        self.page.route('**/*',route)
        self.page.goto('http://importer.test/#updates=1,2')
        self.page.wait_for_function('updateSongs.length===3')
        self.page.evaluate('startUpdates(false,false)')
        self.page.wait_for_function("document.getElementById('updateStart').disabled")
        self.page.wait_for_timeout(100)
        self.assertEqual(posts[0]['ids'],[1])


if __name__ == '__main__': unittest.main()
