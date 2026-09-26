"""Readable section following, source preservation and migration regressions."""
import copy
import json
import unittest
import tempfile
from unittest.mock import Mock, patch
from pathlib import Path
from lupa import LuaRuntime
import jamroom_chart as chart
import jamroom_chart_author as author
from jamroom_chart_migrate import convert, effective_document
import test_browser as bt


def source():
    return '[Intro]\n[ch]C[/ch] [ch]G[/ch]\n[Verse]\n[ch]Am[/ch]\nOriginal example words\n[ch]F[/ch]\nAnother example line\n[Chorus]\n[ch]G[/ch]\nTogether we play again'


def document():
    return chart.build_document({'duration':90}, chart.parse_chart(source()), [])[0]


class ModelTests(unittest.TestCase):
    def test_conversion_keeps_effective_legacy_timing_once(self):
        d=document();d['schema']=2
        shifted=effective_document(d,'10=12','10=20')
        self.assertEqual(shifted['sections'][1]['start'],32)
        converted=convert(shifted)
        self.assertEqual(converted['sections'][0]['label'],'Intro')
        self.assertEqual(converted['sections'][0]['start'],0)
        self.assertEqual(effective_document(converted,'10=12'),converted)
        author.validate(converted,90)

    def test_library_conversion_retry_keeps_revision_and_does_not_rebuild_audio(self):
        from jamroom_updates import Updates
        import jamroom_import as ji
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);folder=root/'song';folder.mkdir();op=root/'operation';op.mkdir()
            original={'slots':[{'slot':'BASS','file':'bass.wav'}],'tempo':120,'level':{'gain':.6}}
            ji.save_job(folder,original)
            d=document();d['schema']=2
            response=Mock(text='PROJEXTSTATE\tReaSetSong\tsong:1:document\t'+json.dumps(d)+'\nPROJEXTSTATE\tReaSetSong\tsong:1:revision\toriginal')
            push=Mock(side_effect=[TimeoutError('Receipt lost'),'Converted'])
            updates=Updates(None,None,push,None,None)
            item={'id':1,'name':'Song','start':0,'end':90}
            with patch('jamroom_updates.requests.get',return_value=response) as get,patch.object(ji,'prepare_chart_document') as regenerate,patch.object(ji.level_model,'analyse') as analyse:
                with self.assertRaises(TimeoutError):updates.convert_chart({},folder,op,root/'installed.json',{},item)
                self.assertEqual(ji.load_job(folder),original)
                updates.convert_chart({},folder,op,root/'installed.json',{},item)
                get.assert_called_once();regenerate.assert_not_called();analyse.assert_not_called()
            self.assertEqual(push.call_args_list[0],push.call_args_list[1])
            self.assertNotIn('click',push.call_args.kwargs)
            self.assertNotIn('level',push.call_args.kwargs)
            saved=ji.load_job(folder)
            self.assertEqual(saved['slots'],original['slots'])
            self.assertEqual(saved['level'],original['level'])
            self.assertEqual(saved['authored_chart']['schema'],3)

    def test_opening_inline_chords_and_solos_survive(self):
        raw='[ch]C[/ch] [ch]G[/ch]\nOpening words before heading\nIntro- [ch]Am[/ch]\n\n[Sax Solo]\n[ch]F[/ch]\n[Bagpipes solo]\n[ch]Dm[/ch]\nRiff 1: [ch]E[/ch]\ne|---0---|'
        templates=chart.parse_chart(raw)
        self.assertEqual([a['symbol'] for s in templates for r in s['rows'] for a in r['anchors']],['C','G','Am','F','Dm','E'])
        self.assertEqual(templates[0]['rows'][0]['text'],'Opening words before heading')
        self.assertIn('Sax Solo',[s['label'] for s in templates])
        self.assertEqual(templates[-1]['rows'][-1]['kind'],'notation')

    def test_gaps_and_bad_reference_do_not_create_fragments(self):
        job={'duration':90,'lyrics':{'synced':True,'lines':[{'time':10,'text':'Original example words'},{'time':11,'text':''},{'time':70,'text':'Another example line'},{'time':500,'text':'Together we play again'}]}}
        d,_=chart.build_document(job,chart.parse_chart(source()),[])
        self.assertEqual([s['label'] for s in d['sections']],['Intro','Verse','Chorus'])
        self.assertTrue(all(s['end']-s['start']>=10 for s in d['sections']))
        self.assertEqual(d['sections'][-1]['end'],90)
        self.assertFalse(any('cue' in r for s in d['sections'] for r in s['rows']))

    def test_manual_page_cue_becomes_visible_section_without_losing_columns(self):
        d=document();d['schema']=2
        row=d['sections'][1]['rows'][1];row['page_cues']={'0':45}
        original=copy.deepcopy(d);converted=convert(d)
        self.assertEqual(converted['schema'],3)
        self.assertEqual(len(converted['sections']),4)
        self.assertEqual(converted['sections'][2]['start'],45)
        self.assertEqual([r['text'] for s in converted['sections'] for r in s['rows']], [r['text'] for s in d['sections'] for r in s['rows']])
        self.assertEqual(convert(converted),converted)
        self.assertEqual(d,original)
        author.validate(converted,90)

    def test_conflicting_legacy_cue_preserves_original(self):
        d=document();d['schema']=2;d['sections'][1]['rows'][0]['page_cues']={'2':40}
        converted=convert(d)
        self.assertEqual(converted['schema'],2)
        self.assertIn('migration_issue',converted)
        self.assertEqual(converted['sections'],d['sections'])

    def test_native_accepts_shared_schema_and_rejects_obsolete_writes(self):
        lua=LuaRuntime(unpack_returned_tuples=True)
        root=bt.ROOT/'Requirements'
        lua.execute('J=dofile('+json.dumps((root/'ReaSet_JSON.lua').as_posix())+'); E=dofile('+json.dumps((root/'ReaSet_ChartEdit.lua').as_posix())+')')
        d=document();lua.globals().blob=json.dumps(d)
        self.assertEqual(lua.eval("E.apply(J.decode(blob),'author',J.decode(blob),90).schema"),3)
        with self.assertRaises(Exception):lua.eval("E.apply(J.decode(blob),'pagecue',{section=1,time=1,column=0},90)")
        old=copy.deepcopy(d);old['schema']=2;lua.globals().old=json.dumps(old)
        with self.assertRaises(Exception):lua.eval("E.apply(J.decode(blob),'author',J.decode(old),90)")


class DisplayTests(unittest.TestCase):
    setUpClass=classmethod(bt.BrowserTests.setUpClass.__func__)
    tearDownClass=classmethod(bt.BrowserTests.tearDownClass.__func__)
    setUp=bt.BrowserTests.setUp
    tearDown=bt.BrowserTests.tearDown
    load_reaset=bt.BrowserTests.load_reaset

    def load(self):
        self.load_reaset()
        self.page.evaluate("d=>{g_clData.document=d;g_clData.song.name='Example band — Room song';toggleChordsPanel();renderChordsView();}",document())

    def test_section_count_is_independent_of_window_and_chords(self):
        self.load()
        counts=self.page.evaluate("""() => [768,1024,1366,1920].flatMap(w=>['both','lyrics'].map(mode=>chartBuildPages(g_clData.document,w,600,mode,0).map(p=>[p.section,p.cue,p.total])))""")
        self.assertTrue(all(c==counts[0] for c in counts))
        self.assertEqual(len(counts[0]),3)
        self.assertEqual(self.page.locator('#chords-live .uc-section').count(),3)

    def test_manual_scroll_stays_put_until_resume_and_seek_uses_transport(self):
        self.load();host=self.page.locator('#chords-live')
        host.locator('.uc-scroll').dispatch_event('wheel',{'deltaY':100})
        self.page.evaluate('currentPos=85;isPlaying=true;renderChordsView()')
        self.assertEqual(host.locator('.uc-follow').inner_text(),'Resume following')
        host.locator('.uc-follow').click()
        self.assertEqual(host.locator('.uc-select').input_value(),'2')
        self.page.evaluate('currentPos=0;renderChordsView()')
        self.assertEqual(host.locator('.uc-select').input_value(),'0')

    def test_page_anticipation_is_visible_persisted_and_does_not_edit_timing(self):
        self.load();host=self.page.locator('#chords-live')
        before=self.page.evaluate('JSON.stringify(g_clData.document)')
        host.get_by_role('button',name='Pages',exact=True).click()
        self.page.evaluate('currentPos=g_clData.document.sections[1].start-2.1;isPlaying=true;renderChordsView()')
        self.assertEqual(host.locator('.uc-select').input_value(),'0')
        self.page.evaluate('currentPos+=.2;renderChordsView()')
        self.assertEqual(host.locator('.uc-select').input_value(),'1')
        host.locator('.uc-lead').select_option('0')
        self.assertEqual(host.locator('.uc-select').input_value(),'0')
        self.assertEqual(self.page.evaluate('JSON.stringify(g_clData.document)'),before)
        self.page.evaluate("ChartDisplay.dispose(document.getElementById('chords-live'));renderChordsView()")
        self.assertEqual(host.locator('.uc-lead').input_value(),'0')

    def test_long_section_keeps_estimated_reading_position_above_bottom(self):
        self.load();d=document()
        d['revision']='long-test'
        d['sections'][0]['rows']=[{'id':'long-'+str(i),'text':'Line '+str(i)+' of the opening passage','chord_line':'C    G','anchors':[{'symbol':'C','offset':0},{'symbol':'G','offset':5}]} for i in range(24)]
        self.page.evaluate('d=>{g_clData.document=d;isPlaying=true;renderChordsView()}',d)
        for w,h in [(1024,768),(1366,768)]:
            self.page.set_viewport_size({'width':w,'height':h})
            for fraction in [.25,.5,.75,.9]:
                self.page.evaluate('f=>{currentPos=g_clData.document.sections[0].end*f-2;renderChordsView()}',fraction)
                result=self.page.evaluate('''f=>{const b=document.querySelector('#chords-live .uc-scroll'),ls=b.querySelectorAll('[data-section="0"] .uc-line'),r=b.getBoundingClientRect();const y=ls[0].getBoundingClientRect().top+(ls[ls.length-1].getBoundingClientRect().bottom-ls[0].getBoundingClientRect().top)*f;return (y-r.top)/b.clientHeight;}''',fraction)
                self.assertGreater(result,.15)
                self.assertLess(result,.5)
        self.page.evaluate('isPlaying=false;renderChordsView()')
        top=self.page.locator('#chords-live .uc-scroll').evaluate('(b)=>b.scrollTop')
        self.page.evaluate('renderChordsView();renderChordsView()')
        self.assertEqual(self.page.locator('#chords-live .uc-scroll').evaluate('(b)=>b.scrollTop'),top)

    def test_stem_chunks_are_batched_retried_and_large_library_can_mute(self):
        self.load()
        result=self.page.evaluate('''() => {
          const songs={};for(let i=0;i<150;i++)songs[i]={name:'Song '+i,start:i*80,end:i*80+60,controls:[{pb:'PB BASS',label:'Bass',order:1}]};
          const raw=JSON.stringify({songs,globalIssues:[]}),chunks=raw.match(/.{1,800}/g);
          sent=[];g_jrHb={val:'1',changedAt:Date.now()};jrHandleExtState(['EXTSTATE','ReaSetJR','meta','large:'+chunks.length]);
          const first=sent[0];g_jrFetch.at=0;jrHandleExtState(['EXTSTATE','ReaSetJR','meta','large:'+chunks.length]);
          const retried=sent[1]===first;
          chunks.forEach((c,i)=>jrHandleExtState(['EXTSTATE','ReaSetJR','d'+i,'large:'+c]));
          currentPos=149*80;g_jrTracks={'PB BASS':{idx:7,muted:false}};renderTracksPanel();jrTapControl('PB BASS');
          return {retried,count:Object.keys(g_jrData.songs).length,max:Math.max(...sent.map(s=>s.split(';').length)),mute:sent.at(-1),text:document.getElementById('jr-body').innerText};
        }''')
        self.assertTrue(result['retried']);self.assertEqual(result['count'],150)
        self.assertLessEqual(result['max'],16)
        self.assertEqual(result['mute'],'SET/TRACK/7/MUTE/1')
        self.assertIn('Bass',result['text'])

    def test_stem_bridge_error_is_not_reported_as_missing_stems(self):
        self.load()
        self.page.evaluate("g_jrHb={val:'1',changedAt:Date.now()};g_jrData={songs:{},globalIssues:[{type:'bridge_error',msg:'Discovery failed'}]};renderTracksPanel()")
        text=self.page.locator('#jr-body').inner_text()
        self.assertIn('Discovery failed',text)
        self.assertNotIn('No backing stems',text)

    def test_marker_tip_drag_preserves_grab_offset(self):
        self.load();self.page.evaluate('chartEditorOpen()')
        marker=self.page.locator('.ca-marker').nth(1)
        tip=marker.evaluate("b=>({position:getComputedStyle(b,'::after').left,width:b.clientWidth,border:getComputedStyle(b,'::after').borderTopWidth})")
        self.assertEqual(tip['border'],'8px')
        box=marker.bounding_box();wave=self.page.locator('.ca-timeline').bounding_box()
        start=self.page.evaluate('ChartAuthor.active.getDocument().sections[1].start')
        x=box['x']+box['width']/2+6;y=box['y']+8
        self.page.mouse.move(x,y);self.page.mouse.down();self.page.mouse.move(x+24,y);self.page.mouse.up()
        end=self.page.evaluate('ChartAuthor.active.getDocument().sections[1].start')
        self.assertAlmostEqual(end,start+24/wave['width']*90,places=2)

    def test_add_and_split_have_one_marker_and_survive_reopening(self):
        self.load();self.page.evaluate('chartEditorOpen()')
        self.page.get_by_role('button',name='Add section',exact=True).click()
        self.page.get_by_role('button',name='After selected',exact=True).click()
        self.page.locator('.ca-name').fill('New solo');self.page.locator('.ca-name').press('Tab')
        self.page.locator('.ca-text').fill('Dm7  G7\nCmaj7')
        self.assertEqual(self.page.locator('.ca-marker').count(),4)
        self.assertEqual(self.page.locator('.ca-context-section').count(),4)
        self.page.get_by_role('button',name='Close',exact=True).click();self.page.evaluate('chartEditorOpen()')
        d=self.page.evaluate('ChartAuthor.active.getDocument()')
        self.assertEqual(d['sections'][1]['label'],'New solo')
        self.assertEqual(d['sections'][1]['rows'][0]['anchors'][0]['symbol'],'Dm7')
        self.assertEqual(self.page.get_by_role('button',name='Page starts here',exact=True).count(),0)

    def test_migration_is_identical_in_browser_and_importer(self):
        self.load();d=document();d['schema']=2;d['sections'][1]['rows'][1]['page_cues']={'0':45}
        self.assertEqual(self.page.evaluate('d=>ChartDisplay.convert(d)',d),convert(d))

    def test_opening_a_chart_keeps_tagged_chords_with_notation(self):
        self.load();d=document()
        d['sections'][0]['rows']=[{'id':'shape','text':'','chord_line':'Fmaj7  x33210','anchors':[{'symbol':'Fmaj7','offset':0,'width':5}]}]
        self.page.evaluate('d=>{g_clData.document=d;chartEditorOpen()}',d)
        self.page.locator('.ca-section-list button').nth(1).click()
        row=self.page.evaluate('ChartAuthor.active.getDocument().sections[0].rows[0]')
        self.assertEqual(row['anchors'],d['sections'][0]['rows'][0]['anchors'])
        self.assertEqual(row['text'],'')

    def test_selecting_a_distant_section_brings_its_editor_into_view(self):
        self.load();d=document()
        d['sections'][0]['rows']=[{'id':'long-'+str(i),'text':'A long opening passage','anchors':[]} for i in range(40)]
        self.page.evaluate('d=>{g_clData.document=d;chartEditorOpen()}',d)
        self.page.locator('.ca-section-list button').last.click()
        area=self.page.locator('.ca-context').bounding_box()
        text=self.page.locator('.ca-text').bounding_box()
        self.assertGreaterEqual(text['y'],area['y'])
        self.assertLess(text['y'],area['y']+area['height'])

    def test_visual_layouts_keep_controls_and_last_lines_accessible(self):
        self.load();folder=bt.ROOT/'imports/.visual/unified-chart';folder.mkdir(parents=True,exist_ok=True)
        for w,h in [(1024,768),(768,1024),(1366,768),(1920,1080)]:
            self.page.set_viewport_size({'width':w,'height':h});self.page.evaluate('renderChordsView()')
            host=self.page.locator('#chords-live');self.assertTrue(host.locator('.uc-scroll').is_visible())
            self.assertLessEqual(host.locator('.uc-follow').bounding_box()['y'],h)
            self.page.screenshot(path=str(folder/f'scroll-{w}.png'))
            host.get_by_role('button',name='Pages',exact=True).click()
            self.assertEqual(host.locator('.uc-section').count(),1)
            host.get_by_role('button',name='Scroll',exact=True).click()
        self.page.evaluate('chartEditorOpen()')
        self.page.set_viewport_size({'width':1024,'height':768})
        self.page.screenshot(path=str(folder/'editor.png'))
        self.page.locator('#chart-author nav').get_by_role('button',name='Preview',exact=True).click()
        self.page.screenshot(path=str(folder/'preview.png'))
