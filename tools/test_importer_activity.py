"""Exercise the real activity UI with delayed/disconnected local API fixtures."""
from collections import Counter
from pathlib import Path
import unittest

from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parent.parent


class ActivityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.pw=await async_playwright().start()
        self.browser=await self.pw.chromium.launch(channel='msedge')
        self.page=await self.browser.new_page(viewport={'width':1280,'height':800})
        self.errors=[];self.page.on('pageerror',lambda e:self.errors.append(str(e)))
        self.calls=Counter();self.held=[];self.hold=None;self.failed_path=None;self.batch=None
        self.project='P';self.jobs=[]
        self.songs=[dict(id=i,name=f'Artist - Song {i}',duration=240,eligible=True,
                         click_eligible=True,level_eligible=True,update_status='Update available') for i in range(1,81)]
        await self.page.route('**/*',self.route)
        await self.page.goto('http://importer.test/')
        await self.page.wait_for_function('window.ImportJobs && ImportJobs.enabled')

    async def asyncTearDown(self):
        await self.browser.close();await self.pw.stop()
        self.assertEqual(self.errors,[])

    async def route(self,r):
        path=r.request.url.split('importer.test')[-1].split('?')[0]
        self.calls[path]+=1
        if path==self.hold:self.held.append(r);return
        if path==self.failed_path:await r.abort();return
        if path.endswith('.js'):
            await r.fulfill(path=str(ROOT/'tools'/path.lstrip('/')),content_type='text/javascript');return
        if path=='/api/checks':
            import jamroom_import as ji
            data=dict(build=ji.BUILD,key=True,reaper=True,ffmpeg=True,ytdlp=True)
        elif path=='/api/jobs':data=dict(schema=1,jobs=self.jobs,paused=False)
        elif path=='/api/updates':data=dict(project=self.project,songs=self.songs,batch=self.batch)
        elif path=='/api/updates/status':data=dict(project=self.project,batch=self.batch)
        elif path=='/api/updates/start':data={'id':'B'}
        elif path=='/api/songs':data={'songs':self.songs}
        elif path.startswith('/api/'):data={'songs':[]}
        else:await r.fulfill(path=str(ROOT/'tools/importer.html'),content_type='text/html');return
        await r.fulfill(json=data)

    async def chooser(self):
        await self.page.evaluate("setSource('man',true);openUpdates()")
        await self.page.wait_for_function('updateSongs.length===80 && !updateLoading')

    async def test_delayed_scan_immediate_feedback_and_no_rescans_on_selection_or_poll(self):
        self.hold='/api/updates'
        await self.page.evaluate("setSource('man',true);openUpdates()")
        await self.page.wait_for_function("document.getElementById('activitySummary').textContent.includes('Checking library')")
        self.assertTrue(await self.page.locator('#updateStart').is_disabled())
        self.assertEqual(await self.page.locator('#updateSongs').get_attribute('aria-busy'),'true')
        await self.held[0].fulfill(json=dict(project='P',songs=self.songs,batch=None));self.hold=None
        await self.page.wait_for_function('updateSongs.length===80 && !updateLoading')
        await self.page.evaluate('chooseUpdates(false);chooseUpdates(true)')
        await self.page.select_option('#updateMode','levels')
        await self.page.evaluate("window.keptRow=document.querySelector('#updateSongs input');keptRow.focus();")
        await self.page.wait_for_timeout(2800)
        self.assertEqual(self.calls['/api/updates'],1)
        self.assertGreaterEqual(self.calls['/api/updates/status'],2)
        self.assertTrue(await self.page.evaluate("keptRow===document.querySelector('#updateSongs input') && document.activeElement===keptRow"))

    async def test_start_once_activity_results_and_return_preserves_position(self):
        await self.chooser()
        await self.page.evaluate("document.getElementById('updateStart').scrollIntoView();window.oldScroll=scrollY;document.getElementById('q').value='unsaved search'")
        self.hold='/api/updates/start'
        await self.page.evaluate('void startUpdates(false,false);void startUpdates(false,false)')
        await self.page.wait_for_function("document.getElementById('activityView').hidden===false")
        self.assertEqual(self.calls['/api/updates/start'],1)
        self.assertIn('Sending request',await self.page.locator('#activitySummary').inner_text())
        self.batch=dict(id='B',status='running',songs=[dict(self.songs[0],status='working',stage='Measuring playback volume'),dict(self.songs[1],status='pending')])
        await self.held[0].fulfill(json={'id':'B'});self.hold=None
        await self.page.wait_for_function("document.getElementById('activityTasks').textContent.includes('Measuring playback volume')")
        await self.page.click('#activityToggle')
        self.assertEqual(await self.page.input_value('#q'),'unsaved search')
        self.assertLess(abs(await self.page.evaluate('scrollY-oldScroll')),3)
        self.batch['status']='complete';self.batch['songs'][0].update(status='done',message='Updated');self.batch['songs'][1].update(status='failed',message='Source files missing')
        await self.page.evaluate('ImporterActivity.poll()')
        self.assertTrue(await self.page.locator('#activityView').is_hidden())
        await self.page.click('#activityToggle')
        self.assertIn('1 need attention',await self.page.locator('#activityTasks').inner_text())
        await self.page.get_by_text('Song results and details',exact=True).click()
        await self.page.get_by_label('Show only problems').check()
        self.assertEqual(await self.page.locator('.activity-result').count(),1)
        self.assertIn('Source files missing',await self.page.locator('.activity-result').inner_text())
        self.batch['songs'][1]['message']='Still missing: bass.wav'
        await self.page.evaluate('ImporterActivity.poll()')
        self.assertEqual(await self.page.evaluate('document.activeElement.id'),'activityProblems')
        self.assertTrue(await self.page.get_by_label('Show only problems').is_checked())
        self.assertIn('bass.wav',await self.page.locator('.activity-result').inner_text())

    async def test_failed_scan_cannot_start_stale_whole_library_and_disconnect_keeps_batch(self):
        await self.chooser();self.failed_path='/api/updates'
        await self.page.evaluate('updateWholeLibrary()')
        self.assertEqual(self.calls['/api/updates/start'],0)
        self.assertIn('Connection lost',await self.page.locator('#activitySummary').inner_text())
        self.batch=dict(id='B',status='running',songs=[dict(self.songs[0],status='working')])
        self.failed_path=None;await self.page.evaluate('ImporterActivity.poll()')
        self.failed_path='/api/updates/status';await self.page.evaluate('ImporterActivity.poll()')
        self.assertIn('Reconnecting',await self.page.locator('#activitySummary').inner_text())
        await self.page.evaluate('ImporterActivity.open()')
        self.assertIn('Artist - Song 1',await self.page.locator('#activityTasks').inner_text())
        self.failed_path=None;await self.page.evaluate('ImporterActivity.poll()')
        self.assertNotIn('Library status unavailable',await self.page.locator('#activityTasks').inner_text())

    async def test_phone_and_zoom_layout_bar_visible_and_last_song_reachable(self):
        await self.chooser()
        for width in (390,640,1280):
            await self.page.set_viewport_size({'width':width,'height':700})
            await self.page.locator('#updateSongs .songrow').last.scroll_into_view_if_needed()
            bounds=await self.page.evaluate('''() => ({bar:document.getElementById('activityBar').getBoundingClientRect().top,
                width:document.documentElement.scrollWidth,viewport:innerWidth,
                last:document.querySelector('#updateSongs .songrow:last-child').getBoundingClientRect().bottom})''')
            self.assertGreaterEqual(bounds['bar'],0);self.assertLess(bounds['bar'],20)
            self.assertLessEqual(bounds['width'],bounds['viewport'])
            self.assertLessEqual(bounds['last'],701)

    async def test_reopen_restores_jobs_and_batch_without_submitting_work(self):
        self.jobs=[dict(id='one',song='First song',state='preparing',stage='Waiting for Fadr'),dict(id='two',song='Second song',state='review',summary='Ready to review')]
        self.batch=dict(id='B',status='interrupted',songs=[dict(self.songs[0],status='pending')])
        await self.page.reload();await self.page.wait_for_function('window.ImportJobs && ImportJobs.enabled')
        await self.page.evaluate('ImporterActivity.open()')
        self.assertIn('First song',await self.page.locator('#activityTasks').inner_text())
        self.assertIn('Second song',await self.page.locator('#activityTasks').inner_text())
        await self.page.wait_for_function("document.getElementById('activityTasks').textContent.includes('interrupted')")
        self.assertEqual(self.calls['/api/updates/start'],0)

    async def test_receipt_does_not_clear_review_and_duplicate_posts_share_request(self):
        await self.page.evaluate("document.getElementById('lyrOffset').value='2.5';document.getElementById('q').value='my song';showReceipt('Chart updated','Saved successfully',[],false,false)")
        self.assertEqual(await self.page.input_value('#lyrOffset'),'2.5')
        self.assertEqual(await self.page.input_value('#q'),'my song')
        self.hold='/api/rechord'
        await self.page.evaluate("void(window.responses=Promise.all([fetch('/api/rechord',{method:'POST',body:'{}'}),fetch('/api/rechord',{method:'POST',body:'{}'})]).then(rs=>Promise.all(rs.map(r=>r.json()))))")
        await self.page.wait_for_timeout(100)
        self.assertEqual(self.calls['/api/rechord'],1)
        await self.held[0].fulfill(json={'ok':True});self.hold=None
        self.assertEqual(await self.page.evaluate('responses'),[{'ok':True},{'ok':True}])

    async def test_iphone_webkit_activity_and_short_viewport(self):
        await self.page.close()
        webkit=await self.pw.webkit.launch()
        try:
            self.page=await webkit.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
            self.page.on('pageerror',lambda e:self.errors.append(str(e)))
            await self.page.route('**/*',self.route)
            self.batch=dict(id='B',status='running',songs=[dict(self.songs[0],status='working',stage='Measuring playback volume')])
            await self.page.goto('http://importer.test/')
            await self.page.wait_for_function('window.ImportJobs && ImportJobs.enabled')
            await self.page.evaluate('ImporterActivity.open()')
            await self.page.wait_for_function("document.getElementById('activityTasks').textContent.includes('Measuring playback volume')")
            self.assertIn('Library update',await self.page.locator('#activityCurrent article').first.inner_text())
            await self.page.set_viewport_size({'width':390,'height':360})
            await self.page.get_by_role('button',name='Pause after this song',exact=True).scroll_into_view_if_needed()
            self.assertLessEqual(await self.page.evaluate('document.documentElement.scrollWidth'),390)
            self.assertTrue(await self.page.locator('#activityToggle').is_visible())
        finally:await webkit.close()


if __name__=='__main__':unittest.main()
