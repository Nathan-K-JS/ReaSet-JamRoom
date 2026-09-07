"""Real browser smoke tests with the REAPER wire transport stubbed locally."""
import json
import os
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright
import jamroom_chart as chart

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
