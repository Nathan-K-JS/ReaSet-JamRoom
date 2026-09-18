"""Listening persistence, local downloads and Android/iPhone browser behavior."""
import copy
from http.server import ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import wave

import requests

import jamroom_listening as listen
import jamroom_importer_server as server


class ListeningFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='listening-test-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.service = listen.Listening(lambda: {}, self.home / 'service')
        self.folder = self.home / 'copy'; self.folder.mkdir()
        self.token = 'a' * 32
        self.row = {'key': 'project:copy', 'id': 'copy', 'project': 'project', 'state': 'ready',
                    'token': self.token, 'folder': str(self.folder), 'title': 'Vox 🎵 <take> "one"',
                    'created': 'Today', 'files': {'mp3': 16}}
        self.service.data['jobs'][self.row['key']] = self.row
        (self.folder / 'mix.mp3').write_bytes(b'0123456789abcdef')
        self.service._save()

    def http(self):
        self.mock = patch.object(server, 'LISTENING', self.service); self.mock.start(); self.addCleanup(self.mock.stop)
        http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
        self.addCleanup(http.server_close); self.addCleanup(http.shutdown)
        return f'http://127.0.0.1:{http.server_port}'


class ListeningTests(ListeningFixture):
    @unittest.skipUnless(os.name == 'nt', 'Windows worker isolation')
    def test_worker_lifetime_closes_its_owned_child(self):
        child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'], creationflags=subprocess.CREATE_NO_WINDOW)
        close=listen.bind_worker_lifetime(child)
        close()
        self.assertIsNotNone(child.wait(timeout=5))
    def test_safari_ranges_head_and_unicode_downloads(self):
        url = self.http() + '/listen/' + self.token
        for byte_range, code, expected in [(None, 200, b'0123456789abcdef'), ('bytes=0-1', 206, b'01'),
                ('bytes=5-', 206, b'56789abcdef'), ('bytes=-4', 206, b'cdef'), ('bytes=15-999', 206, b'f'),
                ('bytes=50-', 416, b''), ('bytes=-0', 416, b''), ('bytes=3-1', 416, b''), ('bytes=0-1,3-4', 416, b'')]:
            with self.subTest(range=byte_range):
                r = requests.get(url + '/audio.mp3', headers={'Range': byte_range} if byte_range else {}, timeout=3)
                self.assertEqual((r.status_code, r.content), (code, expected))
        r = requests.head(url + '/audio.mp3', headers={'Range': 'bytes=0-1'}, timeout=3)
        self.assertEqual(r.status_code, 206); self.assertEqual(r.content, b'')
        self.assertEqual(r.headers['Content-Length'], '2')
        self.assertEqual(r.headers['Content-Range'], 'bytes 0-1/16')
        r = requests.get(url + '/download.mp3', timeout=3)
        self.assertEqual(r.headers['Content-Type'], 'audio/mpeg')
        self.assertIn("filename*=UTF-8''", r.headers['Content-Disposition'])
        self.assertIn('%F0%9F%8E%B5', r.headers['Content-Disposition'])
        self.assertEqual(requests.head(url, timeout=3).content, b'')

    def test_page_qr_escape_title_and_lan_link(self):
        # Upgrade an existing two-format copy without breaking its MP3 link.
        self.row['files']['wav'] = 12
        (self.folder/'mix.wav').write_bytes(b'internal wav')
        self.service._save()
        self.service = listen.Listening(lambda: {}, self.home/'service')
        self.assertEqual(self.service.ready(self.token)['files'], {'mp3':16})
        url = self.http() + '/listen/' + self.token
        with patch.object(server, 'lan_url', return_value='http://192.168.1.99:8765'):
            r = requests.get(url, timeout=3)
            self.assertIn('&lt;take&gt;', r.text); self.assertNotIn('<take>', r.text)
            self.assertIn('value="http://192.168.1.99:8765/listen/' + self.token, r.text)
            self.assertIn('Files → Downloads', r.text)
            self.assertNotIn('WAV', r.text)
            self.assertNotIn('.wav', r.text)
            qr = requests.get(url + '/qr.svg', timeout=3)
            self.assertEqual(qr.status_code, 200); self.assertIn('<svg', qr.text)
            self.assertNotIn('https://', qr.text)
        self.assertEqual(requests.get(url + '/../../source.RPP', timeout=3).status_code, 404)
        for endpoint in ('audio.wav','download.wav'):
            self.assertEqual(requests.get(url+'/'+endpoint,timeout=3).status_code,404)
            self.assertEqual(requests.head(url+'/'+endpoint,timeout=3).status_code,404)

    def test_revocation_and_remove_never_touch_multitracks(self):
        original = self.folder / 'original.wav'; original.write_bytes(b'keep')
        media=self.folder/'Media';media.mkdir();(media/'1.wav').write_bytes(b'private copy')
        listen.atomic(self.folder/'media.json', ['Media/1.wav'])
        self.service.action(self.row['key'], 'revoke')
        with self.assertRaises(ValueError): self.service.ready(self.token)
        current = self.row['token']; self.assertEqual(self.service.ready(current)['state'], 'ready')
        self.service.action(self.row['key'], 'remove')
        with self.assertRaises(ValueError): self.service.ready(current)
        self.assertEqual(original.read_bytes(), b'keep'); self.assertFalse((self.folder/'mix.mp3').exists())
        self.assertFalse((media/'1.wav').exists())
        self.assertEqual(self.service.listing()['jobs'], [])

    def test_restart_resumes_interrupted_jobs_and_keeps_ready_copies(self):
        job = copy.deepcopy(self.row); job.update(key='project:other', id='other', state='rendering')
        self.service.data['jobs'][job['key']] = job; self.service._save()
        restarted = listen.Listening(lambda: {}, self.home / 'service')
        self.assertEqual(restarted.data['jobs'][job['key']]['state'], 'queued')
        self.assertEqual(restarted.ready(self.token)['files'], {'mp3': 16})

    def test_discovery_is_idempotent_and_uses_only_reaper_published_root(self):
        root = self.home / 'setlist.RPP.recordings'; folder = root / 'Listening' / 'new'
        folder.mkdir(parents=True)
        listen.atomic(root/'index.json', {'project':'actual', 'version':1})
        listen.atomic(folder/'request.json', {'id':'new','project':'actual','version':1,'title':'New take','created':'Today'})
        response = requests.Response(); response.status_code = 200
        response._content = ('PROJEXTSTATE\tReaSetRec\tindex\t'+str(root/'index.json')+'\n').encode()
        with patch.object(listen.requests, 'get', return_value=response):
            self.service.discover(); self.service.discover()
        self.assertEqual(len(self.service.data['jobs']), 2)
        self.assertNotIn('folder', self.service.listing()['jobs'][-1])

    def test_encoding_failure_retains_verified_wav_and_retry_skips_render(self):
        (self.folder / 'mix.mp3').unlink(); (self.folder/'mix.wav').write_bytes(b'verified wav')
        listen.atomic(self.folder/'request.json', {'duration':5,'rate':1})
        with patch.object(listen, 'probe'), patch.object(listen, 'render') as render, \
                patch.object(listen.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(ValueError, 'rendered audio is saved'):
                self.service.process(self.row['key'])
            render.assert_not_called()
        self.service.change(self.row['key'], state='failed')
        with self.assertRaises(ValueError): self.service.ready(self.token)
        self.assertEqual(self.row['files'], {})
        self.service.action(self.row['key'], 'retry')
        self.assertEqual(self.row['state'], 'queued')
        self.assertEqual((self.folder/'mix.wav').read_bytes(), b'verified wav')
        original=self.folder/'original.wav';original.write_bytes(b'original recording')
        def encode(*args, **kwargs):
            (self.folder/'mp3-pending.mp3').write_bytes(b'encoded mp3')
            return subprocess.CompletedProcess(args[0],0,stderr='')
        with patch.object(listen,'probe'), patch.object(listen,'render') as render, \
                patch.object(listen.shutil,'which',return_value='ffmpeg'), \
                patch.object(listen.subprocess,'run',side_effect=encode), patch.object(listen,'scan',return_value=(-16,-1)):
            self.service.process(self.row['key'])
            self.service.process(self.row['key'])  # Resume after final publication/cleanup.
            render.assert_not_called()
        self.assertEqual(self.service.ready(self.token)['files'], {'mp3':11})
        self.assertFalse((self.folder/'mix.wav').exists())
        self.assertEqual(original.read_bytes(),b'original recording')

    def test_render_failure_does_not_publish_output(self):
        (self.folder / 'mix.mp3').unlink(); self.row['files'] = {}
        listen.atomic(self.folder/'request.json', {'duration':5,'rate':1})
        with patch.object(listen, 'render', side_effect=OSError('Disk full')):
            with self.assertRaisesRegex(OSError, 'Disk full'): self.service.process(self.row['key'])
        with self.assertRaises(ValueError): self.service.ready(self.token)
        self.assertFalse((self.folder/'mix.wav').exists())

    def test_remove_rejects_media_outside_its_copy(self):
        original=self.home/'original.wav';original.write_bytes(b'original')
        listen.atomic(self.folder/'media.json', ['../original.wav'])
        with self.assertRaisesRegex(ValueError,'no files were removed'):
            self.service.action(self.row['key'],'remove')
        self.assertEqual(original.read_bytes(),b'original')
        self.assertEqual(self.service.ready(self.token)['state'],'ready')


EDGE = Path(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)')) / 'Microsoft/Edge/Application/msedge.exe'


@unittest.skipUnless(EDGE.exists() and shutil.which('ffmpeg'), 'Browser and ffmpeg required')
class ListeningPhones(ListeningFixture):
    def test_phone_playback_seeking_download_and_layout(self):
        from playwright.sync_api import sync_playwright
        with wave.open(str(self.folder/'mix.wav'), 'wb') as f:
            f.setparams((2, 2, 48000, 0, 'NONE', 'not compressed'))
            f.writeframes(b''.join(struct.pack('<hh', *([int(2000*math.sin(2*math.pi*440*n/48000))]*2)) for n in range(48000*4)))
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(self.folder/'mix.wav'),'-b:a','256k',str(self.folder/'mix.mp3')], check=True)
        self.row['files'] = {ext:(self.folder/('mix.'+ext)).stat().st_size for ext in ('mp3','wav')}
        base = self.http()
        with sync_playwright() as pw:
            engines = [('Android Chrome', pw.chromium, {'executable_path':str(EDGE)}, 'Pixel 7'),
                       ('iPhone WebKit', pw.webkit, {}, 'iPhone 13')]
            for name, engine, args, device in engines:
                with self.subTest(browser=name):
                    browser = engine.launch(headless=True, **args)
                    try:
                        context = browser.new_context(**pw.devices[device], accept_downloads=True)
                        # LAN HTTP does not expose secure-context sharing/clipboard APIs.
                        context.add_init_script("Object.defineProperty(navigator,'share',{value:undefined});Object.defineProperty(navigator,'clipboard',{value:undefined});")
                        page = context.new_page(); errors=[]; page.on('pageerror', lambda e:errors.append(str(e)))
                        page.goto(base+'/listen/'+self.token)
                        self.assertFalse(page.locator('#share').is_visible())
                        page.wait_for_function('document.querySelector(".qr").complete&&document.querySelector(".qr").naturalWidth>0')
                        page.wait_for_function('document.querySelector("audio").readyState>=1')
                        page.locator('audio').evaluate('(a)=>a.play()')
                        page.wait_for_function('document.querySelector("audio").currentTime>.1')
                        page.locator('audio').evaluate('(a)=>{a.pause();a.currentTime=2;}')
                        page.wait_for_function('Math.abs(document.querySelector("audio").currentTime-2)<.1')
                        self.assertEqual(page.get_by_role('link',name='Download WAV',exact=False).count(),0)
                        with page.expect_download() as pending:
                            page.get_by_role('link', name='Download MP3', exact=False).click()
                        download = pending.value
                        self.assertTrue(download.suggested_filename.endswith('.mp3'))
                        self.assertIsNone(download.failure())
                        for width,height in [(320,568),(390,844),(844,390)]:
                            page.set_viewport_size({'width':width,'height':height})
                            page.locator('#sharing').evaluate('(e)=>e.open=true')
                            self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                            self.assertGreaterEqual(page.locator('#copy').bounding_box()['height'],44)
                        page.get_by_role('button', name='Copy link', exact=True).click()
                        page.wait_for_function('document.getElementById("copy-status").textContent.length>0')
                        page.goto(base+'/recordings?project=project')
                        page.get_by_role('link',name='Listen, download & share',exact=True).wait_for()
                        self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                        self.assertFalse(errors)
                        context.close()
                    finally: browser.close()


if __name__ == '__main__': unittest.main()
