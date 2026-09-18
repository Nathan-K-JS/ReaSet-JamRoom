"""Compressed upload contract and legacy cache compatibility; no paid requests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import jamroom_import as ji
import jamroom_importer_server as server


class AudioUploadTests(unittest.TestCase):
    def test_download_resumes_after_restart_and_expired_url_then_reuses_completion(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td)/'bass.wav'
            dest.with_name('bass.wav.part').write_bytes(b'first')
            dest.with_name('bass.wav.part.asset').write_text('asset')
            stale = MagicMock(status_code=403, headers={})
            stale.__enter__.return_value = stale
            fresh = MagicMock(status_code=206, headers={'Content-Length':'4', 'Content-Range':'bytes 5-8/9'})
            fresh.__enter__.return_value = fresh
            fresh.iter_content.return_value = [b'last']
            fadr = ji.Fadr('test')
            fadr.s = Mock()
            fadr.s.get.return_value = Mock(status_code=200, json=lambda:{'url':'https://download.invalid'})
            with patch.object(ji.requests, 'get', side_effect=[stale, fresh]) as download, patch.object(ji.time, 'sleep'):
                fadr.download('asset', dest)
                self.assertEqual(dest.read_bytes(), b'firstlast')
                self.assertEqual(download.call_count, 2)
                self.assertEqual(download.call_args.kwargs['headers'], {'Range':'bytes=5-'})
                fadr.download('asset', dest)
                self.assertEqual(download.call_count, 2)

    def test_download_restarts_incomplete_file_when_range_is_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td)/'bass.wav'
            dest.with_name('bass.wav.part').write_bytes(b'old')
            dest.with_name('bass.wav.part.asset').write_text('asset')
            response = MagicMock(status_code=200, headers={'Content-Length':'3'})
            response.__enter__.return_value = response
            response.iter_content.return_value = [b'new']
            fadr = ji.Fadr('test'); fadr.s = Mock()
            fadr.s.get.return_value = Mock(status_code=200, json=lambda:{'url':'https://download.invalid'})
            with patch.object(ji.requests, 'get', return_value=response):
                fadr.download('asset', dest)
            self.assertEqual(dest.read_bytes(), b'new')

    def test_upload_metadata_matches_actual_extension(self):
        for extension,mime in [('m4a','audio/mp4'),('wav','audio/wav'),('mp3','audio/mpeg')]:
            with self.subTest(extension=extension),tempfile.TemporaryDirectory() as td:
                path=Path(td)/('source.'+extension);path.write_bytes(b'audio')
                fadr=ji.Fadr('test')
                fadr.s=Mock()
                fadr.s.post.side_effect=[Mock(status_code=200,json=lambda:{'url':'https://upload.invalid','s3Path':'test'}),
                                         Mock(status_code=200,json=lambda:{'asset':{'_id':'asset'}})]
                with patch.object(ji.requests,'put',return_value=Mock(status_code=200)) as upload:
                    self.assertEqual(fadr.upload(path,'Band - Song'),{'_id':'asset'})
                for call in fadr.s.post.call_args_list:
                    self.assertEqual(call.kwargs['json']['extension'],extension)
                    self.assertEqual(call.kwargs['json']['name'],'Band - Song.'+extension)
                self.assertEqual(upload.call_args.kwargs['headers']['Content-Type'],mime)

    def test_youtube_prefers_native_compressed_audio(self):
        with patch.object(ji,'run_ytdlp') as run:
            ji._ytdlp_download(Path('source.%(ext)s'),'https://example.invalid',None)
        args=run.call_args.args[0]
        self.assertEqual(args[args.index('-f')+1],'bestaudio[ext=m4a]/bestaudio')
        self.assertEqual(args[args.index('--audio-format')+1],'m4a')

    def test_compressed_partial_download_is_protected_like_wav(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td)/'source.m4a').write_bytes(b'cached')
            self.assertTrue(server.job_has_cached_audio(td))

    def test_completed_wav_download_is_not_replaced(self):
        job={'stages':{'download':True},'source':{'audio_file':'source.wav'}}
        with patch.object(ji,'_download_any_client') as download:
            ji.stage_download(job,Path('unused'),'unused',False)
        download.assert_not_called()
        self.assertEqual(job['source']['audio_file'],'source.wav')


if __name__=='__main__':unittest.main()
