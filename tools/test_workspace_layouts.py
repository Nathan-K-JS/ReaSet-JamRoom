"""Musician workflows: visible actions, stable drafts and confirmed state."""
import json
import unittest
import test_browser as browser_tests
import test_importer_activity as activity_tests


class RecordingWorkspaceTests(unittest.TestCase):
    setUpClass = classmethod(browser_tests.BrowserTests.setUpClass.__func__)
    tearDownClass = classmethod(browser_tests.BrowserTests.tearDownClass.__func__)
    setUp = browser_tests.BrowserTests.setUp
    tearDown = browser_tests.BrowserTests.tearDown
    load_reaset = browser_tests.BrowserTests.load_reaset
    recording_state = browser_tests.BrowserTests.recording_state

    def review(self, count=24):
        self.recording_state()
        self.page.evaluate('''count=>{g_recState.device='ready';g_recState.mode='review';g_recState.selected='s';g_recState.take='t';g_recState.recordingOn=true;
        g_recState.sessions=[{id:'s',song:{free:true,name:'Friday jam',click:true},takes:[{id:'t',number:3,parent:'base',inputs:['1'],duration:120,status:'kept'}]}];
        g_recState.parts=Array.from({length:count},(_,i)=>({id:'p'+i,name:'Part '+(i+1),gain:1,muted:false,new:i===count-1}));recRender();}''',count)

    def visible_action(self, label):
        rect=self.page.get_by_role('button',name=label,exact=True).bounding_box()
        self.assertIsNotNone(rect,label)
        self.assertGreaterEqual(rect['y'],0,label)
        self.assertLessEqual(rect['y']+rect['height'],self.page.viewport_size['height']+1,label)

    def test_review_actions_and_last_part_reachable_at_all_sizes(self):
        self.review()
        for width,height in [(320,568),(390,844),(768,1024),(1024,768),(1440,900),(844,390)]:
            self.page.set_viewport_size(dict(width=width,height=height))
            for label in ['Listen','Add part','New take','Export recording']:self.visible_action(label)
            last=self.page.locator('#rec-part-p23');last.scroll_into_view_if_needed()
            self.assertLessEqual(last.bounding_box()['y']+last.bounding_box()['height'],self.page.locator('.rec-work-foot').bounding_box()['y'])
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        self.page.set_viewport_size(dict(width=1440,height=900));self.page.evaluate("document.body.style.zoom='2'")
        self.visible_action('Export recording')

    def test_large_overdub_keeps_options_above_independent_scrolling_panes(self):
        self.review(24)
        self.page.set_viewport_size(dict(width=1440,height=900))
        self.page.evaluate("g_recState.preparation={kind:'part',parent:'t',stopAtEnd:true};recRender()")
        self.visible_action('Count-in: 2 bars')
        self.visible_action('Record part')
        last=self.page.locator('#rec-part-p23');last.scroll_into_view_if_needed()
        self.visible_action('Count-in: 2 bars')
        self.assertLessEqual(last.bounding_box()['y']+last.bounding_box()['height'],self.page.locator('.rec-work-foot').bounding_box()['y'])
        self.assertTrue(self.page.get_by_label('Record Vox 1',exact=True).is_visible())

    def test_prepare_is_a_confirmed_transition_and_preserves_input_selection(self):
        self.review(8)
        self.page.get_by_role('button',name='New take',exact=True).click()
        self.assertEqual(self.page.evaluate('g_recPending.op'),'prepareTake')
        self.assertEqual(self.page.evaluate('g_recState.mode'),'review')
        self.assertIsNone(self.page.query_selector('[data-rec-input]'))
        self.page.evaluate("g_recPending=null;g_recState.preparation={kind:'part',parent:'t',stopAtEnd:true};recRender()")
        self.page.set_viewport_size(dict(width=390,height=844))
        self.visible_action('Record part')
        self.page.get_by_role('button',name='Accompaniment',exact=True).click()
        self.assertTrue(self.page.locator('#rec-part-p0').is_visible())
        self.page.get_by_role('button',name='Inputs',exact=True).click()
        self.assertTrue(self.page.get_by_label('Record Vox 1',exact=True).is_checked())
        self.page.locator('#rec-part-stop').uncheck();self.page.evaluate("g_recState.message='Confirmed';recRender()")
        self.assertFalse(self.page.locator('#rec-part-stop').is_checked())
        self.page.get_by_role('button',name='Record part',exact=True).click()
        cmd=json.loads(self.page.evaluate("decodeURIComponent(sent.at(-1)).split('/want/')[1]"))
        self.assertEqual(cmd['op'],'recordPrepared');self.assertFalse(cmd['stopAtEnd'])

    def test_export_is_not_repeated_after_submitting_and_has_return_context(self):
        self.review(4);self.page.evaluate('window.open=url=>window.lastExport=url')
        self.page.get_by_role('button',name='Export recording',exact=True).click()
        self.page.get_by_role('button',name='Create MP3',exact=True).click()
        self.assertEqual(self.page.evaluate('g_recPending.op'),'listening')
        self.assertIn('return=',self.page.evaluate('lastExport'))
        self.page.evaluate('g_recPending=null;recRender()')
        self.assertEqual(self.page.get_by_role('button',name='Create MP3',exact=True).count(),0)
        self.visible_action('View export')


class ImporterWorkspaceTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = activity_tests.ActivityTests.asyncSetUp
    asyncTearDown = activity_tests.ActivityTests.asyncTearDown

    async def route(self,r):
        path=r.request.url.split('importer.test')[-1].split('?')[0]
        if path.startswith('/api/jobs/') and path!='/api/jobs/control':
            job=next(j for j in self.jobs if j['id']==path.split('/')[3])
            if r.request.method=='POST':
                body=r.request.post_data_json;self.calls[path]+=1
                if path.endswith('/draft'):job['draft']=body['draft'];job['revision']+=1
                if path.endswith('/check-target'):await r.fulfill(json={'matches':True});return
                if path.endswith('/apply'):job['state']='done'
            await r.fulfill(json=job);return
        await activity_tests.ActivityTests.route(self,r)

    async def queue(self):
        review=dict(stems=[dict(file=f'{i}.wav',name=f'Stem {i}',slot='BASS',audio='/audio.wav',duration=180) for i in range(8)],
                    slot_choices=[['BASS','Bass'],['GTR1','Guitar 1']],slot_labels={'BASS':'Bass'},lyrics={'synced':False},chart={})
        self.jobs=[dict(id=str(i),song=f'Artist - Song {i}',state='review' if i<4 else 'preparing',stage='Working',revision=1,target='JamRoom',review=review,draft={}) for i in range(30)]
        await self.page.reload();await self.page.wait_for_function('ImportJobs.enabled')
        await self.page.get_by_role('button',name='Open Artist - Song 0',exact=True).click()

    async def test_review_tabs_autosave_resume_and_apply_stay_in_view(self):
        await self.queue()
        for width,height in [(320,568),(390,844),(768,1024),(1024,768),(1440,900),(844,390)]:
            await self.page.set_viewport_size(dict(width=width,height=height))
            bounds=await self.page.locator('#applyBtn').bounding_box()
            self.assertIsNotNone(bounds);self.assertGreaterEqual(bounds['y'],0)
            self.assertLessEqual(bounds['y']+bounds['height'],height+1)
            self.assertTrue(await self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        await self.page.set_viewport_size(dict(width=390,height=844))
        await self.page.locator('#stemList select').first.select_option('GTR1')
        await self.page.wait_for_function("document.getElementById('queueSaved').textContent==='Saved'")
        await self.page.get_by_role('button',name='Chords / choose',exact=True).click()
        await self.page.locator('#ugQuery').fill('My unfinished search')
        await self.page.wait_for_timeout(700)
        await self.page.reload();await self.page.wait_for_selector('#ugQuery',state='visible')
        self.assertEqual(await self.page.locator('#ugQuery').input_value(),'My unfinished search')
        self.assertEqual(await self.page.locator('#workspaceTitle').inner_text(),'Artist - Song 0')
        await self.page.locator('#applyBtn').click()
        await self.page.wait_for_selector('#workspaceJobState',state='visible')
        self.assertEqual(await self.page.locator('#workspaceJobState').inner_text(),'Added to REAPER')
        self.assertEqual(self.calls['/api/jobs/0/apply'],1)
        await self.page.get_by_role('button',name='Review next ready song',exact=True).click()
        self.assertEqual(await self.page.locator('#workspaceTitle').inner_text(),'Artist - Song 1')

    async def test_library_update_footer_and_last_row_do_not_overlap(self):
        await self.page.evaluate("setSource('man',true);openUpdates()")
        await self.page.wait_for_function('updateSongs.length===80&&!updateLoading')
        for w,h in [(320,568),(390,844),(1024,768),(844,390)]:
            await self.page.set_viewport_size(dict(width=w,height=h))
            await self.page.locator('#updateSongs .songrow').last.scroll_into_view_if_needed()
            last=await self.page.locator('#updateSongs .songrow').last.bounding_box()
            foot=await self.page.locator('#workspaceUpdateFooter').bounding_box()
            self.assertLessEqual(last['y']+last['height'],foot['y']+1)
            action=await self.page.locator('#updateStart').bounding_box();self.assertLessEqual(action['y']+action['height'],h+1)
        before=self.calls['/api/updates']
        await self.page.locator('#workspaceUpdateSearch').fill('Song 8')
        self.assertLess(await self.page.locator('#updateSongs .songrow').count(),80)
        self.assertEqual(self.calls['/api/updates'],before)

    async def test_chart_draft_survives_importer_reload_without_resetting_stems(self):
        import test_chart_authoring as authored
        await self.queue()
        self.jobs[0]['review'].update(document=authored.document(),duration=60)
        await self.page.evaluate('d=>{window._review.document=d;window._review.duration=60;}',authored.document())
        await self.page.evaluate('ImportJobs.editChart()')
        await self.page.locator('.ca-text').fill('Dm7   G/B\nFresh words for our room')
        await self.page.wait_for_timeout(900)
        await self.page.get_by_role('button',name='Close',exact=True).click()
        await self.page.reload()
        await self.page.wait_for_function('ImportJobs.enabled')
        await self.page.evaluate('ImportJobs.editChart()')
        await self.page.wait_for_selector('.ca-text')
        self.assertIn('Fresh words for our room',await self.page.locator('.ca-text').input_value())
