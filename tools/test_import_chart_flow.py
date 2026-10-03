"""Guided import review in a real browser; every request uses local fixtures."""
import copy
import unittest
from pathlib import Path
from types import SimpleNamespace

import test_importer_activity as activity


def document(text='Original draft'):
    return {'schema': 3, 'revision': text, 'duration': 60, 'sections': [
        {'id': 'verse', 'label': 'Verse', 'start': 0, 'end': 30, 'rows': [
            {'id': 'one', 'text': text, 'chord_line': 'C', 'anchors': [{'symbol': 'C', 'offset': 0, 'width': 1}]}]},
        {'id': 'chorus', 'label': 'Chorus', 'start': 30, 'end': 60, 'rows': [
            {'id': 'two', 'text': 'Sing together', 'anchors': []}]}]}


class ChartFlowTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = activity.ActivityTests.asyncSetUp
    asyncTearDown = activity.ActivityTests.asyncTearDown

    async def route(self, route):
        path = route.request.url.split('importer.test')[-1].split('?')[0]
        if path in ('/chart-pagination.js', '/chart-author.js'):
            # Exercise the actual HTTP asset handler, not an idealized file route.
            import jamroom_importer_server as server
            payload = []
            server.Handler.do_GET(SimpleNamespace(path=path, _send=lambda *args: payload.append(args)))
            code, body, mime = payload[0]
            await route.fulfill(status=code, body=body, content_type=mime)
            return
        if path == '/api/ug_search':
            self.calls[path] += 1
            if self.hold == path:
                self.held.append(route)
                return
            if self.failed_path == path:
                await route.fulfill(status=503, json={'error': 'Search temporarily unavailable'})
            else:
                await route.fulfill(json={'charts': getattr(self, 'charts', [])})
            return
        if path == '/api/chart-preview':
            await route.fulfill(json={'state': 'error', 'message': 'No audio in this fixture'})
            return
        if path.startswith('/api/jobs/'):
            if path == self.failed_path:
                await route.fulfill(status=503, json={'error': 'Chart could not be fetched'})
                return
            job = next(j for j in self.jobs if j['id'] == path.split('/')[3])
            if route.request.method == 'POST':
                self.calls[path] += 1
                body = route.request.post_data_json
                if body.get('revision') != job['revision']:
                    await route.fulfill(status=409, json={'error': 'Review changed elsewhere'})
                    return
                if path.endswith('/draft'):
                    job['draft'] = body['draft']; job['revision'] += 1
                elif path.endswith('/chart'):
                    review = copy.deepcopy(job['review'])
                    review['chart'] = {'url': body['url'], 'method': 'sections'}
                    review['document'] = document('Chart from ' + body['url'].rsplit('/', 1)[-1])
                    job['candidate'] = review
                    await route.fulfill(json={'candidate': 'candidate', 'review': review})
                    return
                elif path.endswith('/accept-chart'):
                    job['draft']['previous_chart'] = job['draft'].get('chart_document') or job['review']['document']
                    job['review'] = job.pop('candidate')
                    job['draft']['chart_document'] = job['review']['document']
                    job['draft']['chart_reviewed'] = False
                    job['revision'] += 1
                elif path.endswith('/check-target'):
                    await route.fulfill(json={'matches': True})
                    return
                elif path.endswith('/apply'):
                    job['state'] = 'done'
            await route.fulfill(json=job)
            return
        await activity.ActivityTests.route(self, route)

    async def open_job(self, saved=False):
        self.page.set_default_timeout(5000)
        self.charts = [dict(artist='Artist', title='Song', version=i, rating=4.8, votes=100,
                            url=f'https://tabs.ultimate-guitar.com/tab/artist/song-{i}') for i in (1, 2)]
        review = dict(band='Artist', title='Song', duration=60, chart={}, document=document(),
                      stems=[dict(file='bass.wav', name='Bass', slot='BASS', duration=60)],
                      slot_choices=[['BASS', 'Bass'], ['GTR1', 'Guitar 1']], slot_labels={'BASS': 'Bass'}, lyrics={})
        self.jobs = [dict(id=str(i), song=f'Artist - Song {i}', state='review', revision=1,
                         target='Dummy library', review=copy.deepcopy(review), draft={}) for i in range(2)]
        if saved:
            self.jobs[0]['draft'] = {'chart_document': document('Keep my edits'), 'chart_view': 'timing'}
        await self.page.reload()
        await self.page.wait_for_function('ImportJobs.enabled')
        await self.page.get_by_role('button', name='Open Artist - Song 0', exact=True).click()

    async def select_chart(self):
        await self.page.get_by_role('button', name='Continue to chart', exact=True).click()
        await self.page.wait_for_function("document.getElementById('chartSearchStatus').textContent.includes('Top matching chart selected')")

    async def test_fresh_flow_auto_selects_top_preserves_stems_and_applies_only_after_review(self):
        await self.open_job()
        self.assertEqual(self.calls['/api/ug_search'], 0)
        await self.page.locator('#stemList select').select_option('GTR1')
        await self.select_chart()
        self.assertEqual(self.calls['/api/ug_search'], 1)
        self.assertEqual(self.calls['/api/jobs/0/accept-chart'], 1)
        self.assertEqual(self.jobs[0]['draft']['slots']['bass.wav'], 'GTR1')
        self.assertTrue(self.jobs[0]['review']['chart']['url'].endswith('song-1'))
        await self.page.get_by_role('button', name='Continue to review', exact=True).click()
        self.assertEqual(await self.page.locator('#chart-author').get_attribute('data-view'), 'preview')
        self.assertIn('Chart from song-1', await self.page.locator('.ca-pages').inner_text())
        self.assertEqual(await self.page.get_by_role('button', name='Timing', exact=True).count(), 0)
        self.assertEqual(self.calls['/api/jobs/0/apply'], 0)
        await self.page.get_by_role('button', name='Done reviewing', exact=True).click()
        await self.page.wait_for_selector('#chart-author', state='detached')
        await self.page.get_by_role('button', name='Add to REAPER', exact=True).click()
        await self.page.wait_for_function("document.getElementById('workspaceJobState').textContent==='Added to REAPER'")
        self.assertEqual(self.calls['/api/jobs/0/apply'], 1)

    async def test_no_match_and_failed_search_stay_on_chart_step_with_retry(self):
        await self.open_job(); self.charts = []
        await self.page.locator('#applyBtn').click()
        await self.page.wait_for_function("document.getElementById('chartSearchStatus').textContent.includes('No matching')")
        self.assertTrue(await self.page.locator('#applyBtn').is_disabled())
        self.failed_path = '/api/ug_search'
        await self.page.get_by_role('button', name='Search again', exact=True).click()
        await self.page.wait_for_function("document.getElementById('chartSearchStatus').textContent.includes('Search failed')")
        self.assertTrue(await self.page.locator('#ugUrl').is_visible())
        self.assertEqual(self.calls['/api/jobs/0/apply'], 0)

    async def test_delayed_search_cannot_select_chart_for_another_job(self):
        await self.open_job(); self.hold = '/api/ug_search'
        await self.page.locator('#applyBtn').click()
        await self.page.wait_for_function("document.getElementById('chartSearchStatus').textContent.includes('Searching')")
        await self.page.get_by_role('button', name='Open Artist - Song 1', exact=True).click()
        await self.held[0].fulfill(json={'charts': self.charts}); self.hold = None
        await self.page.wait_for_timeout(250)
        self.assertEqual(self.calls['/api/jobs/0/chart'], 0)
        self.assertEqual(self.calls['/api/jobs/1/chart'], 0)
        self.assertEqual(await self.page.locator('#workspaceTitle').inner_text(), 'Artist - Song 1')

    async def test_saved_chart_is_not_replaced_and_old_timing_view_recovers(self):
        await self.open_job(saved=True)
        await self.page.locator('#applyBtn').click()
        self.assertEqual(self.calls['/api/ug_search'], 0)
        await self.page.locator('#applyBtn').click()
        self.assertEqual(await self.page.locator('#chart-author').get_attribute('data-view'), 'preview')
        await self.page.get_by_role('button', name='Edit', exact=True).click()
        self.assertIn('Keep my edits', await self.page.locator('.ca-text').input_value())
        await self.page.locator('.ca-text').fill('Dm\nOur changed words')
        await self.page.get_by_role('button', name='Done reviewing', exact=True).click()
        await self.page.wait_for_selector('#chart-author', state='detached')
        await self.page.reload(); await self.page.wait_for_function('ImportJobs.enabled')
        await self.page.wait_for_function("document.getElementById('applyBtn').textContent==='Add to REAPER'")
        await self.page.get_by_role('button', name='Preview / edit chart', exact=True).click()
        await self.page.get_by_role('button', name='Edit', exact=True).click()
        self.assertIn('Our changed words', await self.page.locator('.ca-text').input_value())
        self.assertEqual(self.calls['/api/ug_search'], 0)

    async def test_newer_search_wins_over_delayed_automatic_search(self):
        await self.open_job(); self.hold = '/api/ug_search'
        await self.page.locator('#applyBtn').click()
        await self.page.wait_for_function("document.getElementById('chartSearchStatus').textContent.includes('Searching')")
        self.hold = None
        self.charts[0]['title'] = 'Newer result'
        await self.page.locator('#ugQuery').fill('My revised search')
        await self.page.get_by_role('button', name='Search charts', exact=True).click()
        await self.page.wait_for_function("document.getElementById('ugResults').textContent.includes('Newer result')")
        await self.held[0].fulfill(json={'charts': [dict(self.charts[0], title='Stale result')]})
        await self.page.wait_for_timeout(100)
        self.assertNotIn('Stale result', await self.page.locator('#ugResults').inner_text())
        self.assertEqual(self.calls['/api/jobs/0/accept-chart'], 0)

    async def test_failed_top_chart_keeps_step_blocked_and_pasted_chart_can_recover(self):
        await self.open_job(); self.failed_path = '/api/jobs/0/chart'
        await self.page.locator('#applyBtn').click()
        await self.page.wait_for_function("document.getElementById('chartSearchStatus').textContent.includes('Could not load')")
        self.assertTrue(await self.page.locator('#applyBtn').is_disabled())
        self.assertEqual(self.calls['/api/jobs/0/accept-chart'], 0)
        self.failed_path = None
        await self.page.locator('#ugUrl').fill('https://tabs.ultimate-guitar.com/tab/manual')
        await self.page.get_by_role('button', name='Use this chart', exact=True).click()
        await self.page.wait_for_function("!document.getElementById('applyBtn').disabled")
        self.assertTrue(self.jobs[0]['review']['chart']['url'].endswith('/manual'))
        self.assertEqual(self.calls['/api/jobs/0/apply'], 0)

    async def test_replacement_preview_can_be_cancelled_without_losing_original(self):
        await self.open_job(); await self.select_chart()
        await self.page.locator('#ugResults button').nth(1).click()
        await self.page.wait_for_selector('#chart-author')
        self.assertTrue(self.jobs[0]['review']['chart']['url'].endswith('song-1'))
        await self.page.get_by_role('button', name='Close', exact=True).click()
        self.assertEqual(self.calls['/api/jobs/0/accept-chart'], 1)
        await self.page.locator('#ugResults button').nth(1).click()
        await self.page.locator('#chart-author').get_by_role('button', name='Use this chart', exact=True).click()
        await self.page.wait_for_function("document.querySelector('.ca-title').textContent==='Artist - Song 0'")
        self.assertTrue(self.jobs[0]['review']['chart']['url'].endswith('song-2'))

    async def test_preview_edit_and_optional_timing_fit_phone_tablet_and_desktop(self):
        await self.open_job(); await self.select_chart()
        folder = Path(__file__).resolve().parent.parent / 'imports/.visual/import-chart-flow'
        folder.mkdir(parents=True, exist_ok=True)
        for width, height in [(1440,900),(390,844),(320,568)]:
            await self.page.set_viewport_size(dict(width=width, height=height))
            box = await self.page.locator('#applyBtn').bounding_box()
            self.assertLessEqual(box['y'] + box['height'], height + 1)
            await self.page.screenshot(path=str(folder / f'chart-selection-{width}.png'))
        await self.page.locator('#applyBtn').click()
        for width, height in [(1440,900),(768,1024),(390,844),(320,568),(844,390)]:
            await self.page.set_viewport_size(dict(width=width, height=height))
            for view in ('Preview', 'Edit'):
                await self.page.get_by_role('button', name=view, exact=True).click()
                for label in ('Done reviewing', 'Close', 'Stop'):
                    box = await self.page.get_by_role('button', name=label, exact=True).bounding_box()
                    self.assertGreaterEqual(box['y'], 0)
                    self.assertLessEqual(box['y'] + box['height'], height + 1)
                self.assertTrue(await self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                await self.page.screenshot(path=str(folder / f'editor-{width}-{view.lower()}.png'))
            await self.page.locator('.ca-timing-tools summary').click()
            offset = self.page.get_by_label('Whole song timing offset')
            await offset.scroll_into_view_if_needed(); await offset.fill('1.5'); await offset.press('Tab')
            self.assertEqual(await self.page.evaluate('ChartAuthor.active.getDocument().timing_offset'), 1.5)
            await self.page.locator('.ca-timing-tools summary').click()
            await self.page.screenshot(path=str(folder / f'editor-{width}.png'))


if __name__ == '__main__':
    unittest.main()
