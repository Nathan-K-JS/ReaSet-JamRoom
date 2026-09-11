import json
from pathlib import Path
import tempfile
import unittest
import wave
from unittest.mock import patch

import numpy as np
import jamroom_click as click


class ClickTests(unittest.TestCase):
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
