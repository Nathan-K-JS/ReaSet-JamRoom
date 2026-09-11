import json
from pathlib import Path
import tempfile
import unittest
import wave
from unittest.mock import patch
import numpy as np

import jamroom_click as click
from jamroom_beat import decode_activations
from jamroom_click_quality import reference_scores, assess


def predictions(beats,duration,drop_alternate=False):
    result=[]
    for i in range(3):
        b=np.asarray(beats)[::2] if drop_alternate and i else np.asarray(beats)
        logits=np.full(round(duration*50)+1,-8.,dtype=np.float32)
        for t in b: logits[max(0,round(t*50)-1):round(t*50)+2]=8
        result.append({'beats':b,'downbeats':b[::4],'beat_logits':logits,'downbeat_logits':logits.copy()})
    return result


class ClickTests(unittest.TestCase):
    def test_review_waveform_keeps_audio_clock_at_end_of_long_song(self):
        from jamroom_click_report import write_report
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); duration=301
            drums=np.zeros(duration*click.RATE,np.float32)
            drums[300*click.RATE]=1
            click.render(root/'click.wav',[300],duration)
            _,_,metadata=write_report(root,'review',drums,drums,root/'click.wav',
                                      {'beats':[300],'quality':{}})
            data=json.loads((root/metadata).read_text())
            shown_time=int(np.argmax(data['envelope']))/data['envelope_rate']
            self.assertLess(abs(shown_time-300),.011)

    def test_missing_runtime_never_creates_a_tempo_only_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            click.render(Path(folder)/'source.wav',np.arange(.2,12,.5),12)
            job={'duration':12,'fadr':{'tempo':120,'sample_rate':44100,'beat_length_samples':22050,'beat_offset_samples':0}}
            with patch.object(click,'predict',side_effect=ImportError('DLL load failed')):
                result=click.add_slot(job,folder,lambda x:None)
            self.assertEqual(result['status'],'unavailable')
            self.assertNotIn('file',result)
            self.assertEqual(job['slots'],[])

    def test_cache_reuse_does_not_depend_on_fadr_tempo_and_keeps_old_files(self):
        with tempfile.TemporaryDirectory() as folder:
            beats=np.arange(.2,12,.5)
            click.render(Path(folder)/'drums.wav',beats,12)
            job={'duration':12,'stems':[{'file':'drums.wav','fadr_name':'drums'}],'fadr':{'tempo':30}}
            with patch.object(click,'predict',return_value=predictions(beats,12)):
                first=click.add_slot(job,folder,lambda x:None)
            job['fadr']['tempo']=270
            with patch.object(click,'predict',side_effect=AssertionError('Cache not reused')):
                second=click.add_slot(job,folder,lambda x:None)
            self.assertEqual(first['file'],second['file'])
            self.assertEqual(len(job['slots']),1)
            self.assertTrue((Path(folder)/second['report']).is_file())
            with wave.open(str(Path(folder)/second['file'])) as wav:
                self.assertEqual(wav.getnframes()/wav.getframerate(),12)

    def test_decoder_follows_gradual_tempo_change_without_fill_phase_jumps(self):
        beats=np.r_[.2,.2+np.cumsum(np.linspace(.49,.55,80))]
        pred=predictions(beats,46)
        # Extra strong offbeat activations simulate a fill; true model beats
        # still establish the pulse before and after it.
        for p in pred:
            for t in beats[30:35]+.18:p['beat_logits'][round(t*50)]=10
        observed,_=decode_activations(pred)
        score=reference_scores(beats,observed)
        self.assertGreater(score['f1'],.98)
        self.assertLess(score['matched_p95_ms'],25)

    def test_reference_metric_rejects_half_double_shifted_and_random_clicks(self):
        refs=json.loads(Path(__file__).with_name('click_reference_windows.json').read_text())
        for window in refs:
            b=np.array(window['beats']);tempo=np.median(np.diff(b))
            for bad in [b[::2],np.sort(np.r_[b,b[:-1]+tempo/2]),b+.15,
                        np.random.default_rng(42).uniform(window['start'],window['end'],len(b)),
                        b[0]+np.arange(len(b))*tempo*1.08]:
                with self.subTest(song=window['song'],candidate=bad):
                    self.assertLess(reference_scores(b,bad)['f1'],.9)
            self.assertEqual(reference_scores(b,b)['f1'],1)

    def test_missing_recording_is_not_replaced_with_metadata_grid(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(click.ClickUnavailable):
                click.ensure_click({'duration':30,'fadr':{'tempo':120}},folder)

    def test_whole_recording_gate_rejects_wrong_tempo_phase_and_a_bad_passage(self):
        reference=np.arange(.2,36,.5)
        observed,detail=decode_activations(predictions(reference,36))
        # Drum-like low sine attacks with noise snares, deliberately different
        # from the rendered click sound. Quiet and syncopated extra hits occur.
        audio=np.zeros(36*22050,np.float32);rng=np.random.default_rng(8)
        for i,b in enumerate(reference):
            t=np.arange(1800)/22050
            pulse=(np.sin(2*np.pi*65*t) if i%2==0 else rng.normal(0,.4,len(t)))*np.exp(-t/.015)
            start=round(b*22050);audio[start:start+len(t)]+=pulse[:min(len(t),len(audio)-start)]
        self.assertEqual(assess(observed,detail,audio,36)['status'],'checks_passed')
        bad_passage=observed.copy();bad_passage[(bad_passage>=12)&(bad_passage<24)]+=.15
        for bad in [observed+.15,observed[::2],np.sort(np.r_[observed,(observed[:-1]+observed[1:])/2]),bad_passage]:
            self.assertEqual(assess(bad,detail,audio,36)['status'],'needs_review')


if __name__=='__main__':unittest.main()
