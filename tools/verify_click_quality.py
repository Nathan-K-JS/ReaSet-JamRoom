"""Audit real cached recordings without changing jobs or the REAPER project.

Generate through the production path, verify the rendered WAV, compare against
waveform-annotated reference windows and deliberately wrong controls. This is
not an assertion of listening approval or a general music benchmark.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import wave
import numpy as np
import jamroom_click as click
from jamroom_click_quality import reference_scores


def rendered_times(path):
    with wave.open(str(path)) as wav:
        assert wav.getnchannels()==1 and wav.getsampwidth()==2
        sr=wav.getframerate();audio=np.frombuffer(wav.readframes(wav.getnframes()),'<i2')
    samples=np.flatnonzero(abs(audio.astype(float))>300)
    first=np.r_[True,np.diff(samples)>sr*.1] if len(samples) else np.array([],bool)
    return samples[first]/sr


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('songs',nargs='+',type=Path)
    args=parser.parse_args()
    refs=json.loads(Path(__file__).with_name('click_reference_windows.json').read_text())
    output=Path('imports/.click-audit');output.mkdir(exist_ok=True)
    results=[]
    for folder in args.songs:
        original=(folder/'job.json').read_bytes();job=json.loads(original)
        old=copy.deepcopy(job.get('click') or {})
        generated=click.ensure_click(job,folder,lambda s:print(folder.name+': '+s,flush=True))
        job['slots']=[s for s in job.get('slots',[]) if s.get('slot')!='CLICK']
        job['slots'].append({'slot':'CLICK','label':'Click','file':generated['file']})
        beats=np.array(generated['beats']);wav=rendered_times(folder/generated['file'])
        assert len(wav)==len(beats) and np.max(abs(wav-beats))<.001,'Rendered click differs from analysed times'
        windows=[]
        for ref in refs:
            if ref['song']!=folder.name:continue
            source=folder/ref['audio_file']
            assert hashlib.sha256(source.read_bytes()).hexdigest()==ref['audio_sha256'],'Reference is for another recording'
            start,end=ref['start'],ref['end'];reference=np.array(ref['beats'])
            candidate=wav[(wav>=start)&(wav<end)]
            score=reference_scores(reference,candidate)
            assert score['f1']>=.95 and score['matched_p95_ms']<35,score
            controls={}
            for name,bad in [('shifted_150ms',candidate+.15),('half_speed',candidate[::2]),
                             ('double_speed',np.sort(np.r_[candidate,(candidate[1:]+candidate[:-1])/2])),
                             ('drift_8_percent',candidate[0]+(candidate-candidate[0])*1.08),
                             ('random',np.random.default_rng(42).uniform(start,end,len(candidate)))]:
                controls[name]=reference_scores(reference,bad)
                assert controls[name]['f1']<.9,(name,controls[name])
            previous=np.asarray(old.get('beats',[]));previous=previous[(previous>=start)&(previous<end)]
            windows.append({'start':start,'end':end,'new':score,'old':reference_scores(reference,previous),'negative_controls':controls})
        entry={'song':folder.name,'quality':generated['quality'],'reference_windows':windows,
               'rendered_click_matches':True,'report':str(folder/generated['report'])}
        results.append(entry)
        target=output/folder.name;target.mkdir(exist_ok=True)
        (target/'proposed-job.json').write_text(json.dumps(job,indent=2),encoding='utf-8')
        assert (folder/'job.json').read_bytes()==original,'Audit altered the cached job'
        (output/'production-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        print(folder.name+': '+generated['review'],flush=True)
    print('Audit passed for '+str(len(results))+' recordings. Reports retain flagged passages.',flush=True)


if __name__=='__main__':main()
