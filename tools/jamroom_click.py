"""Recording-relative rehearsal clicks; no project tempo-map changes. GPL-3.0."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import wave

import numpy as np

GENERATOR = 'recording-click-1'
RATE = 22050


def beat_times(audio, bpm, duration):
    import librosa
    if not np.isfinite(audio).all() or np.max(np.abs(audio), initial=0) < .00001:
        raise ValueError('No rhythmic audio available for click detection')
    # Fadr supplies a tempo prior, while detected attacks locate individual
    # beats. A single fixed BPM would drift against a live drummer.
    _, beats = librosa.beat.beat_track(y=audio, sr=RATE, hop_length=256,
                                      bpm=bpm if bpm and 30<=bpm<=300 else None,
                                      start_bpm=bpm or 120, trim=True, units='time')
    beats = np.asarray(beats, dtype=float)
    if len(beats) < 8:
        raise ValueError('Too few beats to generate a recording-following click')
    first, last = float(beats[0]), float(beats[-1])
    head = float(np.median(np.diff(beats[:9])))
    tail = float(np.median(np.diff(beats[-9:])))
    if min(head,tail) < .15 or max(head,tail) > 2:
        raise ValueError('Detected click pace is outside rehearsal limits')
    before = list(np.arange(first-head, -1e-6, -head)[::-1])
    after = list(np.arange(last+tail, duration, tail))
    times = [round(float(t),6) for t in before+list(beats)+after if 0<=t<duration]
    return times, {'detected_start':first,'detected_end':last,
                   'estimated_bpm':round(60/float(np.median(np.diff(beats))),2),
                   'extrapolated_beats':len(before)+len(after)}


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


def ensure_click(job, folder):
    folder = Path(folder)
    duration = float(job.get('duration') or 0)
    if not math.isfinite(duration) or not 0<duration<14400:
        raise ValueError('Recording duration is required for a click')
    fadr = job.get('fadr') or {}
    old = job.get('click') or {}
    candidates = [s['file'] for s in job.get('stems',[]) if s.get('fadr_name','').lower()=='drums']
    candidates += [s['file'] for s in job.get('slots',[]) if s.get('slot')=='DRUMS']
    source = job.get('source') or {}
    candidates += [source.get('audio_file','source.wav'),'source.m4a','source.wav']
    audio_path = next((folder/p for p in candidates if p and (folder/p).is_file()),None)
    signature=hashlib.sha256(json.dumps({'duration':duration,'fadr':fadr,
        'audio':(str(audio_path.relative_to(folder)),audio_path.stat().st_size,audio_path.stat().st_mtime_ns) if audio_path else None},sort_keys=True).encode()).hexdigest()
    if not old.get('analysis_unavailable') and old.get('generator')==GENERATOR and old.get('source_signature')==signature and (folder/old.get('file','missing')).is_file():
        return old
    method, detail = 'recording beats', {}
    times=None
    if audio_path:
        ffmpeg = shutil.which('ffmpeg')
        if not ffmpeg: raise ValueError('ffmpeg is required to generate clicks')
        data = subprocess.run([ffmpeg,'-v','error','-i',str(audio_path),'-t',str(duration),
                               '-ac','1','-ar',str(RATE),'-f','f32le','-'],capture_output=True,check=True)
        try:
            times,detail = beat_times(np.frombuffer(data.stdout,dtype='<f4'),float(fadr.get('tempo') or 120),duration)
        except ValueError as error:
            detail['fallback_reason']=str(error)
        except (ImportError, OSError) as error:
            detail.update(analysis_unavailable=True, fallback_reason=str(error))
    if times is None:
        # Old jobs can retain analysis without cached stems. Be explicit about
        # using a rigid estimate instead of claiming audio-following detection.
        sr=float(fadr.get('sample_rate') or 0)
        length=float(fadr.get('beat_length_samples') or 0)
        offset=fadr.get('beat_offset_samples')
        if sr<=0 or length<=0 or offset is None or not all(math.isfinite(x) for x in (sr,length,float(offset))):
            raise ValueError('Cached audio or Fadr beat metadata is required for a click')
        interval=length/sr
        if not .15<=interval<=2: raise ValueError('Invalid Fadr beat interval')
        times=np.arange((float(offset)/sr)%interval,duration,interval).tolist()
        method='Fadr fixed grid'
        detail.update(estimated_bpm=60/interval,extrapolated_beats=len(times))
    payload={'generator':GENERATOR,'duration':duration,'source_signature':signature,'beats':times,'method':method,**detail,
             'review':'Estimated click: listen against the recording before rehearsal. No bar accents are assumed.'}
    if detail.get('analysis_unavailable'):
        payload['review']='FALLBACK CLICK: recording beat detection is unavailable. This fixed-tempo click may drift. Run JamRoom Update to repair, then update click tracks only.'
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()[:16]
    relative='clicks/'+digest+'.wav'
    target=folder/relative;target.parent.mkdir(exist_ok=True)
    if not target.exists():
        temporary=target.with_suffix('.tmp.wav');render(temporary,times,duration);temporary.replace(target)
    payload['file']=relative
    job['click']=payload
    return payload


def add_slot(job, folder):
    click=ensure_click(job,folder)
    job['slots']=[s for s in job.get('slots',[]) if s.get('slot')!='CLICK']
    job['slots'].append({'slot':'CLICK','label':'Click','file':click['file']})
    return click
