"""Music-following rehearsal clicks with explicit quality and review evidence."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import wave
import numpy as np

from jamroom_beat_runtime import MODEL_VERSION, predict

GENERATOR = 'recording-click-2'
RATE = 22050


class ClickUnavailable(ValueError):
    pass


def decode_audio(path, duration):
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg: raise ClickUnavailable('ffmpeg is unavailable')
    data=subprocess.run([ffmpeg,'-v','error','-i',str(path),'-t',str(duration),
                         '-ac','1','-ar',str(RATE),'-f','f32le','-'],capture_output=True,check=True)
    return np.frombuffer(data.stdout,dtype='<f4').copy()


def render(path, times, duration):
    samples = np.zeros(int(round(duration*RATE)), dtype=np.float32)
    t = np.arange(int(RATE*.025))/RATE
    pulse = .55*np.sin(2*np.pi*1800*t)*np.exp(-t/0.005)
    pulse *= np.minimum(1,t/.0005)
    for time in times:
        start = int(round(time*RATE))
        if start < 0 or start >= len(samples):
            continue
        end = min(len(samples),start+len(pulse))
        samples[start:end] += pulse[:end-start]
    with wave.open(str(path),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(RATE)
        out.writeframes((np.clip(samples,-1,1)*32767).astype('<i2').tobytes())


def ensure_click(job, folder, log=print):
    from jamroom_beat import decode_activations
    from jamroom_click_quality import assess
    from jamroom_click_report import write_report
    folder=Path(folder)
    duration=float(job.get('duration') or 0)
    if not math.isfinite(duration) or not 0<duration<14400:
        raise ClickUnavailable('Recording duration is required for a click')
    stems=[s for s in job.get('stems',[]) if s.get('file') and s.get('slot')!='CLICK']
    sources=list(dict.fromkeys(s['file'] for s in stems))
    if not sources:
        sources=[s['file'] for s in job.get('slots',[]) if s.get('slot')!='CLICK']
    if not sources:
        source=job.get('source') or {}
        sources=[source.get('audio_file','source.wav')]
    if not sources or any(not (folder/p).is_file() for p in sources):
        raise ClickUnavailable('Cached recording/stems are missing; no tempo-only fallback will be generated')
    drumfiles=[s['file'] for s in stems if s.get('fadr_name','').lower()=='drums']
    drumfiles+= [s['file'] for s in job.get('slots',[]) if s.get('slot')=='DRUMS']
    signature=hashlib.sha256(json.dumps({'duration':duration,'model':MODEL_VERSION,
        'audio':[(p,(folder/p).stat().st_size,(folder/p).stat().st_mtime_ns) for p in sources]},sort_keys=True).encode()).hexdigest()
    old=job.get('click') or {}
    if (old.get('generator')==GENERATOR and old.get('source_signature')==signature
            and old.get('quality') and all((folder/old.get(key,'missing')).is_file()
                                          for key in ('file','report','review_audio','report_data'))):
        return old
    log('Building the analysis mix from cached music stems (excluding the click)...')
    mix=np.zeros(round(duration*RATE),np.float32);drums=np.zeros_like(mix)
    for path in sources:
        y=decode_audio(folder/path,duration);n=min(len(y),len(mix));mix[:n]+=y[:n]
        if path in drumfiles:drums[:n]+=y[:n]
    mix/=max(1,float(np.max(np.abs(mix))))
    if np.max(np.abs(mix))<1e-5: raise ClickUnavailable('Recording is silent')
    cache=folder/'clicks';cache.mkdir(exist_ok=True)
    raw=cache/('analysis-'+signature[:20]+'.npz')
    if raw.exists():
        with np.load(raw,allow_pickle=False) as saved:
            predictions=[{key:saved[str(i)+'_'+key] for key in ('beats','downbeats','beat_logits','downbeat_logits')} for i in range(3)]
    else:
        predictions=predict(mix,log)
        tmp=raw.with_suffix('.tmp')
        with tmp.open('wb') as output:
            np.savez_compressed(output,**{str(i)+'_'+k:v for i,p in enumerate(predictions) for k,v in p.items()})
        tmp.replace(raw)
    times,detail=decode_activations(predictions)
    quality=assess(times,detail,drums,duration)
    if not drumfiles:
        quality.update(status='needs_review',label='Needs click review: no independent drum stem available')
    payload={'generator':GENERATOR,'duration':duration,'source_signature':signature,
             'beats':np.round(times,6).tolist(),'method':'Music beat models with continuous pulse',
             'estimated_bpm':round(quality['median_bpm'],2),'quality':quality,
             'muted':quality['status']!='checks_passed','song':job.get('region_name') or folder.name,
             'review':quality['label'],'model':MODEL_VERSION}
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()[:16]
    target=cache/(digest+'.wav')
    if not target.exists():
        temporary=target.with_suffix('.tmp.wav');render(temporary,times,duration);temporary.replace(target)
    report,audio,metadata=write_report(cache,digest,mix,drums,target,payload)
    payload.update(file='clicks/'+target.name,report='clicks/'+report,review_audio='clicks/'+audio,report_data='clicks/'+metadata)
    job['click']=payload
    log(quality['label']+('; click item will be muted until reviewed.' if payload['muted'] else '.'))
    return payload


def add_slot(job, folder, log=print):
    job['slots']=[s for s in job.get('slots',[]) if s.get('slot')!='CLICK']
    try:
        click=ensure_click(job,folder,log)
    except (ImportError,OSError,ValueError,subprocess.SubprocessError) as error:
        # A missing model/runtime must not turn into a random grid or stop the
        # authorised stem/chart import. Keep this deficiency explicit.
        click={'generator':GENERATOR,'status':'unavailable','muted':True,
               'review':'NO CLICK: '+str(error),'quality':{'status':'unavailable'}}
        job['click']=click;log(click['review']);return click
    job['slots'].append({'slot':'CLICK','label':'Click','file':click['file']})
    return click
