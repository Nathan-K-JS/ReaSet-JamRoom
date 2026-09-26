"""Authored text, draft durability, timing and native save wire regressions."""
import copy
import json
import tempfile
import unittest
import time
import wave
import struct
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

import jamroom_chart_author as author
import jamroom_import as ji
import test_browser as bt
import test_import_queue as queue_tests
from jamroom_import_queue import ImportQueue, Conflict


def document():
    return {'schema':3,'revision':'original','duration':60,'sections':[
        {'id':'s1','label':'Verse','start':0,'end':30,'timing_status':'matched','rows':[
            {'id':'r1','text':'We sing together','chord_line':'C    Am7','anchors':[{'symbol':'C','offset':0,'width':1},{'symbol':'Am7','offset':5,'width':3}],'cue':0},
            {'id':'r2','text':'A new day','chord_line':'F    G/B','anchors':[{'symbol':'F','offset':0,'width':1},{'symbol':'G/B','offset':5,'width':3}],'cue':10}]},
        {'id':'s2','label':'Solo','start':30,'end':60,'rows':[{'id':'r3','text':'','chord_line':'| Am | F | x2','anchors':[{'symbol':'Am','offset':2,'width':2},{'symbol':'F','offset':7,'width':1}]}]}]}


class AuthorValidationTests(unittest.TestCase):
    def test_library_install_retry_keeps_native_revision_after_lost_response(self):
        import jamroom_chart_library as library
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);ident='a'*32;cache=root/'.chart-candidates';cache.mkdir()
            (cache/(ident+'.json')).write_text(json.dumps({'song':{'name':'Example','start':0,'end':60},'job':{},'revision':'original'}),encoding='utf-8')
            sent=[]
            def push(*args, **kwargs):
                sent.append(copy.deepcopy(kwargs['document']))
                if len(sent)==1:raise TimeoutError('Native receipt was saved but the response was lost')
                return 'Already applied'
            server=SimpleNamespace(QUEUE=None,_push_song_items=push)
            body={'candidate':ident,'document':document()}
            with patch.object(ji,'load_config',return_value={'jobs_dir':temporary}),patch.object(ji,'load_job',return_value={}),patch.object(ji,'save_job') as save:
                with self.assertRaises(TimeoutError):library.install(server,body)
                result=library.install(server,body)
                self.assertEqual(sent[0],sent[1])
                self.assertEqual(result['revision'],sent[0]['revision'])
                self.assertEqual(save.call_args.args[1]['authored_chart'],sent[0])
                body['document']['sections'][0]['rows'][0]['text']='Different edits'
                with self.assertRaisesRegex(ValueError,'different edits'):library.install(server,body)

    def test_legacy_lyric_offset_cannot_replace_native_authored_chart(self):
        import jamroom_chart_library as library
        import jamroom_importer_server as server
        with patch.object(ji,'load_config',return_value={}),patch.object(ji,'load_job',return_value={}),patch.object(server,'project_identity',return_value='test-project'),patch.object(server,'project_songs',return_value=[{'id':1,'name':'Example'}]),patch.object(library,'revision',return_value='manual:edited'),patch.object(server,'_push_song_items') as push:
            with self.assertRaisesRegex(ValueError,'manual edits'):server.relyric_song('Example',offset=1)
            push.assert_not_called()

    def test_author_survives_regeneration_and_corrects_fallback_words(self):
        d=author.validate(document(),60);job={'duration':60,'authored_chart':d,'lyrics':{'synced':True,'lines':[{'time':0,'text':'wrong words'}]}}
        with tempfile.TemporaryDirectory() as folder, patch.object(ji,'build_chart_chords',side_effect=AssertionError('Do not regenerate authored charts')):
            self.assertEqual(ji.prepare_chart_document(job,Path(folder))['sections'],d['sections'])
            self.assertIn('We sing together',ji.chart_model.lyric_items(job)[0]['text'])
            self.assertEqual(job['lyrics']['lines'][0]['text'],'wrong words')

    def test_reject_invalid_boundaries_id_and_positions(self):
        for mutate in [lambda d:d['sections'][1].update(start=0),lambda d:d['sections'][1].update(id='s1'),lambda d:d['sections'][0]['rows'][0]['anchors'][0].update(offset=-1),lambda d:d.update(timing_offset=float('nan'))]:
            d=document();mutate(d)
            with self.assertRaises(ValueError):author.validate(d,60)

    def test_cues_outside_moved_sections_are_removed(self):
        d=document();d['sections'][1]['start']=5
        checked=author.validate(d,60)
        self.assertNotIn('cue',checked['sections'][0]['rows'][1])
        self.assertNotIn('page_cues',checked['sections'][0]['rows'][1])

    def test_reaper_import_payload_uses_authored_words(self):
        job={'duration':60,'region_name':'Example','authored_chart':document(),'lyrics':{'lines':[{'time':0,'text':'wrong source words'}],'plain':'wrong source words'},'slots':[]}
        with tempfile.TemporaryDirectory() as temporary,patch.object(ji.level_model,'analyse'):
            folder=Path(temporary);ji.write_reaper_job(job,folder)
            payload=(folder/'job_for_reaper.lua').read_text(encoding='utf-8')
            self.assertIn('We sing together',payload)
            self.assertNotIn('wrong source words',payload)

    def test_preview_audio_origin_duration_peak_and_click_exclusion(self):
        import jamroom_chart_preview as preview
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            def audio(name,impulse):
                with wave.open(str(folder/name),'wb') as f:
                    f.setnchannels(1);f.setsampwidth(2);f.setframerate(22050)
                    f.writeframes(b''.join(struct.pack('<h',24000 if i==impulse else 0) for i in range(22050)))
            audio('voice.wav',5512);audio('click.wav',18000)
            job={'duration':1,'stems':[{'file':'voice.wav','slot':'VOX'},{'file':'click.wav','slot':'CLICK'}]}
            result=preview.prepare(folder,job)
            until=time.monotonic()+15
            while result['state']=='preparing' and time.monotonic()<until:
                time.sleep(.05);result=preview.prepare(folder,job)
            self.assertEqual(result['state'],'ready',result)
            with wave.open(str(folder/'.chart-preview'/result['key']/'audio.wav')) as f:
                data=struct.unpack('<'+'h'*f.getnframes(),f.readframes(f.getnframes()))
                self.assertEqual(f.getnframes(),22050)
                self.assertEqual(max(range(len(data)),key=lambda i:abs(data[i])),5512)
                self.assertEqual(data[18000],0)
            self.assertEqual(preview.prepare(folder,job)['key'],result['key'])


class AuthoredQueueTests(unittest.TestCase):
    setUp=queue_tests.QueueTests.setUp
    add=queue_tests.QueueTests.add
    review=queue_tests.QueueTests.review

    def test_authored_review_restores_and_rejects_stale_drafts(self):
        ident=self.add();row=self.review(ident);folder=self.queue.folder(ident)
        job=ji.load_job(folder);job['duration']=60;ji.save_job(folder,job)
        revision=row['revision']
        self.queue.draft(ident,{'revision':revision,'draft':{'chart_document':document()}})
        reopened=ImportQueue(self.bridge,self.cfg).detail(ident)
        self.assertEqual(reopened['draft']['chart_document']['sections'][0]['rows'][0]['text'],'We sing together')
        with self.assertRaises(Conflict):self.queue.draft(ident,{'revision':revision,'draft':{}})

    def test_source_preview_is_isolated_and_accept_retains_previous_chart(self):
        ident=self.add();row=self.review(ident);folder=self.queue.folder(ident)
        job=ji.load_job(folder);job.update(duration=60,authored_chart=document(),chords_detected=[{'start':0,'end':60,'chord':'C'}]);ji.save_job(folder,job)
        row['draft']={'chart_document':document()};original=(folder/'job.json').read_bytes()
        candidate=copy.deepcopy(document());candidate['sections'][0]['rows'][0]['text']='Different candidate'
        self.bridge.build_review.return_value={'stems':[],'document':candidate,'duration':60}
        with patch.object(ji,'build_chart_chords',return_value={'chords':[]}):
            result=self.queue.choose(ident,'chart',{'revision':row['revision'],'url':'https://tabs.ultimate-guitar.com/tab/test','preview':True})
        self.assertEqual((folder/'job.json').read_bytes(),original)
        self.assertEqual(row['draft']['chart_document']['sections'][0]['rows'][0]['text'],'We sing together')
        recovered=ImportQueue(self.bridge,self.cfg)
        accepted=recovered.action(ident,'accept-chart',{'revision':row['revision'],'candidate':result['candidate']})
        self.assertEqual(accepted['draft']['chart_document']['sections'][0]['rows'][0]['text'],'Different candidate')
        self.assertEqual(accepted['draft']['previous_chart']['sections'][0]['rows'][0]['text'],'We sing together')

    def test_failed_candidate_keeps_cached_job_and_existing_draft(self):
        ident=self.add();row=self.review(ident);folder=self.queue.folder(ident)
        job=ji.load_job(folder);job.update(duration=60,authored_chart=document(),chords_detected=[{'start':0,'end':60,'chord':'C'}]);ji.save_job(folder,job)
        row['draft']={'chart_document':document()};original=(folder/'job.json').read_bytes()
        with patch.object(ji,'build_chart_chords',side_effect=ValueError('Source unavailable')):
            with self.assertRaises(ValueError):self.queue.choose(ident,'chart',{'revision':row['revision'],'url':'bad','preview':True})
        self.assertEqual((folder/'job.json').read_bytes(),original)
        self.assertEqual(row['state'],'review')


class AuthorBrowserTests(unittest.TestCase):
    setUpClass=classmethod(bt.BrowserTests.setUpClass.__func__)
    tearDownClass=classmethod(bt.BrowserTests.tearDownClass.__func__)
    setUp=bt.BrowserTests.setUp
    tearDown=bt.BrowserTests.tearDown
    load_reaset=bt.BrowserTests.load_reaset

    def editor(self):
        self.load_reaset()
        self.page.evaluate('d=>{g_clData.document=d;chartEditorOpen();}',document())

    def test_recognises_music_without_swallowing_lyrics_and_keeps_offsets(self):
        self.load_reaset()
        result=self.page.evaluate('''() => {
          const rows=ChartAuthor.parse('C   Am7\\nWe sing together\\n| F | G/B | x2\\nDm7 G7\\n\\nA\\nA new day',[],[]);
          return {rows, chords:['Cmaj7','F#m7b5','Bbadd9','G7(b9)','Dsus4','N.C.','C/G'].map(s=>ChartAuthor.isChordLine(s)),a:ChartAuthor.isChordLine('A'),forced:ChartAuthor.isChordLine('A','Chords')};
        }''')
        self.assertTrue(all(result['chords']))
        self.assertFalse(result['a']);self.assertTrue(result['forced'])
        self.assertEqual(result['rows'][0]['anchors'][1]['offset'],4)
        self.assertEqual(result['rows'][1]['text'],'')
        self.assertEqual(result['rows'][-2]['text'],'A')

    def test_typing_highlights_without_resetting_caret_then_recovers(self):
        self.editor();text=self.page.get_by_role('textbox',name='Chart text')
        text.fill('C       Am7\nNew original words\nF    G/B\nAnother line')
        self.assertEqual(self.page.locator('.ca-highlight b').all_text_contents(),['C','Am7','F','G/B'])
        text.press('End');text.press_sequentially('!')
        self.assertEqual(text.evaluate('e=>e.selectionStart'),len(text.input_value()))
        original=self.page.evaluate('g_clData.document.sections[0].rows[0].text')
        self.assertEqual(original,'We sing together')
        self.page.get_by_role('button',name='Close',exact=True).click();self.page.evaluate('chartEditorOpen()')
        self.assertIn('New original words',text.input_value())

    def test_split_merge_keep_lines_and_timing_drag_does_not_reorder_text(self):
        self.editor();text=self.page.get_by_role('textbox',name='Chart text')
        text.evaluate("e=>e.setSelectionRange(e.value.indexOf('F    G/B'),e.value.indexOf('F    G/B'))")
        self.page.get_by_role('button',name='Split here',exact=True).click()
        d=self.page.evaluate('ChartAuthor.active.getDocument()')
        self.assertEqual(len(d['sections']),3)
        self.assertEqual(d['sections'][1]['rows'][0]['text'],'A new day')
        self.page.get_by_role('button',name='Merge previous',exact=True).click()
        self.assertEqual(len(self.page.evaluate('ChartAuthor.active.getDocument().sections')),2)
        self.page.locator('.ca-marker').nth(1).press('ArrowRight')
        self.assertAlmostEqual(self.page.evaluate('ChartAuthor.active.getDocument().sections[1].start'),30.1)

    def test_save_chunks_and_native_errors_keep_draft(self):
        self.editor();self.page.get_by_role('textbox',name='Chart text').fill('Dm7 G7\nCorrected words')
        self.page.get_by_role('button',name='Save chart',exact=True).click()
        self.page.wait_for_function('g_chartPending && g_chartPending.submitted')
        self.assertIn('|author|',self.page.evaluate('decodeURIComponent(sent.at(-1))'))
        commands=[c for c in self.chart_wire if '/edit:' in c]
        payload=json.loads(bytes.fromhex(''.join(c.rsplit('/',1)[1] for c in commands)).decode())
        self.assertEqual(payload['sections'][0]['rows'][0]['text'],'Corrected words')
        self.page.evaluate("repairHandleReply(g_chartPending.nonce+'|error|Chart changed; reopen')")
        self.assertIn('Not saved',self.page.locator('.ca-status').inner_text())
        self.assertIn('Corrected words',self.page.locator('.ca-text').input_value())

    def test_layout_actions_visible_all_sizes_and_zoom(self):
        self.editor()
        folder=bt.ROOT/'imports/.visual/chart-author';folder.mkdir(parents=True,exist_ok=True)
        for width,height in [(1440,900),(768,1024),(390,844),(320,568),(844,390)]:
            self.page.set_viewport_size({'width':width,'height':height})
            for view in ['Edit','Preview','Timing']:
                self.page.locator('#chart-author nav').get_by_role('button',name=view,exact=True).click()
                for label in ['Save chart','Stop','Close']:
                    r=self.page.locator('#chart-author').get_by_role('button',name=label,exact=True).bounding_box()
                    self.assertGreaterEqual(r['y'],0,(width,height,label))
                    self.assertLessEqual(r['y']+r['height'],height+1,(width,height,label))
                self.assertTrue(self.page.evaluate('document.querySelector("#chart-author").scrollWidth<=innerWidth'))
            self.page.locator('#chart-author nav').get_by_role('button',name='Edit',exact=True).click()
            self.page.screenshot(path=str(folder/f'editor-{width}.png'))
        self.page.get_by_role('button',name='Close',exact=True).click()
        self.page.evaluate("document.body.style.zoom='2';chartEditorOpen()")
        r=self.page.get_by_role('button',name='Save chart',exact=True).bounding_box()
        self.assertLessEqual(r['y']+r['height'],390)

    def test_shared_code_is_identical_to_native_embedding(self):
        html=(bt.ROOT/'ReaSet.html').read_text(encoding='utf-8')
        self.assertEqual(html.split('<script id="chart-author-core">',1)[1].split('</script>',1)[0].strip(),(bt.ROOT/'tools/chart-author.js').read_text(encoding='utf-8').strip())

    def test_switching_sections_does_not_turn_matches_into_manual_edits(self):
        self.editor();self.page.locator('.ca-section-list button').nth(1).click()
        self.assertEqual(self.page.evaluate('ChartAuthor.active.getDocument().sections[0].timing_status'),'matched')

    def test_chord_only_correction_preserves_timing_but_new_words_do_not(self):
        self.editor();text=self.page.locator('.ca-text')
        text.fill(text.input_value().replace('C    Am7','Dm   Am7'))
        section=self.page.evaluate('ChartAuthor.active.getDocument().sections[0]')
        self.assertEqual(section['timing_status'],'matched')
        self.assertEqual(section['rows'][0]['cue'],0)
        self.assertEqual(section['rows'][0]['id'],'r1')
        text.fill(text.input_value().replace('We sing together','We play alone'))
        section=self.page.evaluate('ChartAuthor.active.getDocument().sections[0]')
        self.assertEqual(section['timing_status'],'manual')
        self.assertNotIn('cue',section['rows'][0])

    def test_first_section_merge_keeps_music_and_view_recovers(self):
        self.editor();self.page.get_by_role('button',name='Merge next',exact=True).click()
        section=self.page.evaluate('ChartAuthor.active.getDocument().sections')
        self.assertEqual(len(section),1);self.assertEqual(len(section[0]['rows']),3)
        self.page.locator('#chart-author nav').get_by_role('button',name='Timing',exact=True).click()
        self.page.get_by_role('button',name='Close',exact=True).click();self.page.evaluate('chartEditorOpen()')
        self.assertEqual(self.page.locator('#chart-author').get_attribute('data-view'),'timing')

    def test_timing_suggestion_uses_retained_matching_words_and_keeps_checked_cue(self):
        self.load_reaset();d=document()
        d['sections'][1]['rows'][0].update(text='An original solo lyric',cue=35,cue_word_coverage=1)
        self.page.evaluate('d=>{g_clData.document=d;chartEditorOpen();}',d)
        self.page.locator('.ca-section-list button').nth(1).click()
        self.page.locator('#chart-author nav').get_by_role('button',name='Timing',exact=True).click()
        self.page.get_by_role('button',name='Suggest timing',exact=True).click()
        section=self.page.evaluate('ChartAuthor.active.getDocument().sections[1]')
        self.assertEqual(section['start'],35);self.assertEqual(section['timing_status'],'matched')
        self.assertIn('retained match',self.page.locator('.ca-status').inner_text())
        self.page.evaluate("()=>{const d=ChartAuthor.active.getDocument();d.sections[1].timing_status='checked';d.sections[1].start=34;ChartAuthor.active.replace(d);}")
        self.page.locator('.ca-section-list button').nth(1).click()
        self.page.get_by_role('button',name='Suggest timing',exact=True).click()
        self.assertEqual(self.page.evaluate('ChartAuthor.active.getDocument().sections[1].start'),34)

    def test_marker_pointer_drag_preserves_source_rows(self):
        self.editor();before=self.page.evaluate('ChartAuthor.active.getDocument().sections.map(s=>s.rows)')
        r=self.page.locator('.ca-marker').nth(1).bounding_box()
        self.page.mouse.move(r['x']+r['width']/2,r['y']+r['height']/2);self.page.mouse.down()
        self.page.mouse.move(r['x']+r['width']/2+70,r['y']+r['height']/2);self.page.mouse.up()
        self.assertGreater(self.page.evaluate('ChartAuthor.active.getDocument().sections[1].start'),30)
        after=self.page.evaluate('ChartAuthor.active.getDocument().sections.map(s=>s.rows)')
        for rows in after:
            for row in rows:row.pop('_from',None);row.pop('_to',None)
        self.assertEqual(before,after)

    def test_editor_uses_sounding_pitch_without_changing_it_when_lyrics_change(self):
        self.load_reaset();d=document()
        d['sections'][0]['rows'][0]['anchors'][0]['symbol']='C#'
        d['sections'][0]['rows'][0]['anchors'][1]['symbol']='A#m7'
        self.page.evaluate('d=>{g_clData.document=d;chartEditorOpen();}',d)
        text=self.page.locator('.ca-text')
        self.assertTrue(text.input_value().startswith('C#   A#m7'))
        text.fill(text.input_value().replace('We sing together','We play together'))
        self.assertEqual(self.page.evaluate('ChartAuthor.active.getDocument().sections[0].rows[0].anchors.map(a=>a.symbol)'),['C#','A#m7'])

    def test_iphone_webkit_authoring_and_keyboard_height(self):
        browser=self.pw.webkit.launch()
        try:
            page=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
            page.on('pageerror',lambda e:self.errors.append(str(e)))
            page.set_content('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><body>')
            page.add_script_tag(path=str(bt.ROOT/'tools/chart-author.js'))
            page.evaluate('d=>ChartAuthor.open({document:d,duration:60,save:async()=>{}})',document())
            text=page.locator('.ca-text');text.fill('Dm7 G/B\nWords on an iPhone')
            self.assertEqual(page.locator('.ca-highlight b').all_text_contents(),['Dm7','G/B'])
            page.set_viewport_size({'width':390,'height':360})
            page.wait_for_timeout(150)
            r=page.get_by_role('button',name='Save chart',exact=True).bounding_box()
            self.assertLessEqual(r['y']+r['height'],361)
            self.assertTrue(text.is_visible())
            area=text.bounding_box();player=page.locator('.ca-player').bounding_box()
            self.assertLessEqual(area['y']+area['height'],player['y']+1)
            self.assertGreaterEqual(area['height'],48)
            page.screenshot(path=str(bt.ROOT/'imports/.visual/chart-author/iphone-keyboard.png'))
        finally:browser.close()


if __name__=='__main__':unittest.main()
