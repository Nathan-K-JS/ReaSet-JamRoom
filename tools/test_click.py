import json
from pathlib import Path
import tempfile
import unittest
import wave
from unittest.mock import patch

import numpy as np
import jamroom_click as click


class ClickTests(unittest.TestCase):
    def test_native_dll_failure_falls_back_then_retries_after_repair(self):
        for exception in (ImportError('DLL load failed while importing _typeconv'), OSError('WinError 126')):
            with self.subTest(exception=exception), tempfile.TemporaryDirectory() as folder:
                click.render(Path(folder)/'source.wav', [0, .5, 1], 12)
                job={'duration':12,'fadr':{'sample_rate':48000,'beat_length_samples':24000,'beat_offset_samples':12000}}
                with patch.object(click, 'beat_times', side_effect=exception):
                    first=click.add_slot(job, folder)
                self.assertTrue(first['analysis_unavailable'])
                self.assertEqual(first['method'], 'Fadr fixed grid')
                self.assertIn('FALLBACK', first['review'])
                with patch.object(click, 'beat_times', return_value=([.2,.7,1.2], {})) as detect:
                    repaired=click.add_slot(job, folder)
                detect.assert_called_once()
                self.assertEqual(repaired['method'], 'recording beats')
                self.assertNotIn('analysis_unavailable', repaired)
                self.assertTrue((Path(folder)/first['file']).exists())
                self.assertEqual(len(job['slots']), 1)

    def test_recording_beats_follow_drift_instead_of_constant_grid(self):
        # Known attacks drift gradually away from a rigid 120 BPM clock.
        times=np.r_[.23,.23+np.cumsum(np.linspace(.48,.53,48))]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'drums.wav'
            click.render(path,times,26)
            with wave.open(str(path)) as audio:
                y=np.frombuffer(audio.readframes(audio.getnframes()),dtype='<i2').astype(np.float32)/32768
            beats,detail=click.beat_times(y,120,26)
        observed=np.array(beats)
        errors=[np.min(np.abs(observed-t)) for t in times[3:-3]]
        self.assertLess(np.percentile(errors,95),.045)
        self.assertGreater(abs(times[-4]-(times[0]+(len(times)-4)*.5)),.08)
        self.assertTrue(detail['detected_end']>20)

    def test_generated_audio_covers_song_and_is_cached_without_duplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            job={'duration':12,'slots':[],'fadr':{'sample_rate':48000,'beat_length_samples':24000,'beat_offset_samples':12000}}
            first=click.add_slot(job,folder)
            self.assertEqual(first['beats'][:2],[.25,.75])
            file=Path(folder)/first['file'];before=file.stat().st_mtime_ns
            with patch.object(click,'render',side_effect=AssertionError('Cache was not reused')):
                click.add_slot(job,folder)
            self.assertEqual(len(job['slots']),1)
            self.assertEqual(file.stat().st_mtime_ns,before)
            with wave.open(str(file)) as wav:
                self.assertEqual(wav.getnframes()/wav.getframerate(),12)
            job['fadr']['beat_offset_samples']=0
            changed=click.add_slot(job,folder)
            self.assertNotEqual(changed['file'],first['file'])
            self.assertTrue(file.exists(),'Keep old media for undo/restore')

    def test_invalid_grid_is_not_silently_installed(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):click.ensure_click({'duration':30},folder)


if __name__=='__main__':unittest.main()
