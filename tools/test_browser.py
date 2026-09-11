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
        self.page.evaluate("chartEditorOpen();chartEditorSave();repairHandleReply(g_chartPending.nonce+'|ok|Sections saved')")
        self.assertIsNone(self.page.evaluate('g_chartPending'))
        self.assertIn('Sections saved', self.page.evaluate('g_chartMessage'))
        self.assertIn('|layout|', self.page.evaluate('decodeURIComponent(sent[sent.length-1])'))

    def test_removed_precise_view_uses_chart_and_old_repair_links_request_upgrade(self):
        self.load_reaset()
        self.page.evaluate("setChordView('big');currentPos=15;renderChordsView()")
        self.assertEqual(self.page.evaluate('g_chordView'),'sheet')
        self.assertEqual(self.page.locator('.cv-big').count(),0)
        self.page.evaluate("window.alert=m=>window.upgradeMessage=m;g_clData.document=null;openTimingRepair('lyrics')")
        self.assertIn('Update this song', self.page.evaluate('upgradeMessage'))
        self.assertEqual(self.page.locator('.timing-fix-btn,#timing-repair').count(),0)

    def test_empty_song_clears_previous_lyrics(self):
        self.load_reaset()
        self.page.evaluate('g_clData=null;renderLyricsView();renderChordsView()')
        self.assertEqual(self.page.locator('#lyrics-live').inner_text(), 'No lyrics for this song.')

    def test_source_chart_pages_keep_every_chord_visible_above_words(self):
        self.load_reaset()
        rows='\n'.join('[ch]C[/ch]           [ch]G[/ch]                      [ch]Am[/ch]  [ch]F[/ch]\nAn original lyric line for the musicians' for _ in range(16))
        doc,_=chart.build_document({'duration':120},chart.parse_chart('[Verse]\n'+rows),[])
        self.page.evaluate('doc=>{g_clData.document=doc;g_clData.song.end=120;g_chordView="sheet"}',doc)
        self.page.locator('#tab-btn-chords').click()
        for width,height in [(1440,1000),(768,1024),(390,844),(1024,768)]:
            self.page.set_viewport_size({'width':width,'height':height})
            self.page.evaluate('g_clHb.changedAt=Date.now();renderChordsView();renderChordsView()')
            count=self.page.evaluate('document.querySelector("#chords-live")._pages.length')
            shown=0
            for i in range(count):
                self.page.evaluate('i=>{g_chartPage=i;g_clHb.changedAt=Date.now();renderChordsView()}',i)
                metrics=self.page.locator('#chords-live').evaluate('''host=>{
                    let paper=host.querySelector('.sc-paper'), box=paper.getBoundingClientRect();
                    return {x:paper.scrollWidth-paper.clientWidth,y:paper.scrollHeight-paper.clientHeight,
                      chords:paper.querySelectorAll('.sc-chords b').length,
                      overlap:[...paper.querySelectorAll('.sc-line')].some(line=>{
                        let words=line.querySelector('.sc-words');return words&&[...line.querySelectorAll('b')].some(ch=>ch.getBoundingClientRect().bottom>words.getBoundingClientRect().top+1);
                      })};}''')
                self.assertLessEqual(metrics['x'],1,(width,i,metrics))
                self.assertLessEqual(metrics['y'],1,(width,i,metrics))
                self.assertFalse(metrics['overlap'])
                shown+=metrics['chords']
            self.assertEqual(shown,64,'Pagination must neither drop nor repeat chords')
        self.page.locator('[data-cv="chart"]').click()
        self.assertEqual(self.page.locator('#chords-live .sc-words').count(),0)
        self.assertIn('C',self.page.locator('#chords-live .sc-paper').inner_text())

    def test_pagination_does_not_orphan_transition_on_an_extra_page(self):
        self.load_reaset()
        rows='\n'.join('[ch]C[/ch]     [ch]G[/ch]\nAn original line for the musicians' for _ in range(9))
        doc,_=chart.build_document({'duration':60},chart.parse_chart('[Verse]\n'+rows+'\n[ch]C[/ch] [ch]G[/ch]'),[])
        pages=self.page.evaluate("doc=>chartBuildPages(doc,1440,732,'sheet',0)",doc)
        self.assertEqual(len(pages),2,'Two pages fit; balancing must not introduce a third')
        self.assertTrue(any(p['hasWords'] for p in pages[-1]['parts']))
        self.assertFalse(pages[-1]['parts'][-1]['hasWords'])

    def test_full_chart_editor_keeps_unsaved_changes_local(self):
        self.load_reaset()
        self.page.evaluate('chartEditorOpen()')
        before=self.page.evaluate('JSON.stringify(g_clData.document)')
        self.page.evaluate('chartEditorJoin(1)')
        self.page.evaluate('chartEditorSplit(0,1)')
        self.assertEqual(self.page.evaluate('JSON.stringify(g_clData.document)'),before)
        self.assertIn('Here we sing',self.page.locator('#chart-edit-lines').inner_text())
        self.page.evaluate('chartEditorSave()')
        self.assertEqual(self.page.evaluate('JSON.stringify(g_clData.document)'),before)
        self.assertIn('|layout|',self.page.evaluate('decodeURIComponent(sent[sent.length-1])'))
        commands=self.page.evaluate('sent.filter(c=>c.includes("/edit:"))')
        self.assertTrue(commands)
        self.assertTrue(all(len(c)<500 for c in commands))
        payload=bytes.fromhex(''.join(c.rsplit('/',1)[1] for c in commands)).decode('utf-8')
        self.assertIn('sections',json.loads(payload))

    def test_page_turn_lead_offset_preview_and_removed_views(self):
        self.load_reaset()
        self.assertEqual(self.page.locator('[data-cv="big"],[data-cv="timeline"]').count(),0)
        self.page.evaluate("setChordView('big')")
        self.assertEqual(self.page.evaluate('g_chordView'),'sheet')
        self.assertIn('Here we sing',self.page.locator('#chords-live .sc-preview').inner_text())
        for playing,position,offset,expected in [(False,9.5,0,9.5),(True,9.5,0,10.25),(True,9.5,2,8.25)]:
            actual=self.page.evaluate('v=>{isPlaying=v[0];currentPos=v[1];return chartDisplayTime({timing_offset:v[2]})}',[playing,position,offset])
            self.assertAlmostEqual(actual,expected)
        self.page.locator('#tab-btn-chords').click()
        pages=self.page.evaluate('JSON.stringify(document.getElementById("chords-live")._pages)')
        self.page.evaluate('g_chartTiming=true;renderChordsView()')
        self.assertEqual(self.page.evaluate('JSON.stringify(document.getElementById("chords-live")._pages)'),pages)
        self.page.get_by_role('button',name='Later 0.5s',exact=True).click()
        self.assertIn('|offset|',self.page.evaluate('decodeURIComponent(sent[sent.length-1])'))

    def test_transposed_repeats_have_space_without_moving_word_anchors(self):
        self.load_reaset()
        result=self.page.evaluate('''()=>{
            let row={text:'Held note',chord_line:'C                   C C C',anchors:[
              {symbol:'C',offset:0,width:1},{symbol:'C',offset:20,width:1},
              {symbol:'C',offset:22,width:1},{symbol:'C',offset:24,width:1}]};
            let before=JSON.stringify(row),parts=chartFragments(row,80,'sheet',0,0,1);
            return {before,after:JSON.stringify(row),anchors:parts[0].anchors};
        }''')
        self.assertEqual(result['before'],result['after'])
        self.assertEqual(result['anchors'][0]['offset'],0)
        for previous,current in zip(result['anchors'],result['anchors'][1:]):
            self.assertGreaterEqual(current['offset']-previous['offset']-len(previous['symbol']),2)

    def test_whole_library_uses_all_project_songs_and_keeps_protected_versions(self):
        songs=[{'id':i,'name':'Song '+str(i),'eligible':i!=2,'protected':i==2,'update_status':'Update available'} for i in (1,2,3)]
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
        self.page.goto('http://importer.test/#updates=1')
        self.page.get_by_role('button',name='Update whole library',exact=True).click()
        self.page.wait_for_timeout(300)
        self.assertEqual(posts[0]['ids'],[1,3])
        self.assertEqual(posts[0]['project'],'test')
        self.assertFalse(posts[0]['replace_edits'])
        self.assertEqual(self.page.locator('#updateScope').input_value(),'all')
        self.assertEqual(self.page.get_by_role('button',name='Shift timing',exact=True).count(),0)

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
        self.page.wait_for_function("v => document.getElementById('verBadge').textContent.includes(v)", arg=importer.BUILD)
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

    def test_importer_review_does_not_treat_a_perfect_match_as_quality_approval(self):
        def route(req):
            if '/api/' in req.request.url:req.fulfill(json={'songs':[],'state':'idle'})
            else:req.fulfill(path=str(ROOT/'tools/importer.html'))
        self.page.route('**/*',route)
        self.page.goto('http://importer.test/')
        self.page.evaluate("""renderChartNow({chart:{url:'https://tabs.ultimate-guitar.com/test',method:'sections',lines_matched:50,chart_lines:50,
          review:{issues:[{message:'Missing passage <example>'}]}}})""")
        text=self.page.locator('#chartNow').inner_text()
        self.assertIn('Text matching does not verify musical timing',text)
        self.assertIn('Missing passage <example>',text)
        self.assertNotIn('50 of 50',text)
        self.assertEqual(self.page.locator('#chartNow example').count(),0)

    def test_fadr_picker_starts_default_import_through_visible_buttons(self):
        song={'id':'split-song','name':'Paramore - Misery Business','duration':199.3,
              'subsplits_done':2,'named_locally':True,'has_chords':True,'stems':5,
              'key':'G#:maj','tempo':173,'created':'2026-08-23'}
        posts=[]
        def route(req):
            url=req.request.url
            if '/api/import_library' in url:
                posts.append(req.request.post_data_json);req.fulfill(json={'ok':True})
            elif '/api/library' in url:req.fulfill(json={'songs':[song]})
            elif '/api/' in url:req.fulfill(json={'songs':[],'state':'idle'})
            else:req.fulfill(path=str(ROOT/'tools/importer.html'))
        self.page.route('**/*',route)
        self.page.goto('http://importer.test/')
        self.page.locator('#srcLib').click()
        self.page.locator('#libFilter').fill('Misery')
        self.page.locator('#libList .result').click()
        self.assertEqual(self.page.locator('#band').input_value(),'Paramore')
        self.assertEqual(self.page.locator('#title').input_value(),'Misery Business')
        self.page.locator('#importBtn').click()
        self.page.wait_for_timeout(200)
        self.assertEqual(posts[0]['id'],'split-song')
        self.assertEqual(posts[0]['title'],'Misery Business')
        self.assertEqual(posts[0]['duration'],199.3)

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
