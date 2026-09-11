"""A portable, synchronized waveform and listening report, no web dependencies."""
import html
import json
import wave
from pathlib import Path
import numpy as np


def render_html(data, audio, title):
    template=Path(__file__).with_name('click_review.html').read_text(encoding='utf-8')
    return (template.replace('__DATA__',json.dumps(data).replace('<','\\u003c'))
            .replace('__AUDIO__',html.escape(audio)).replace('__TITLE__',html.escape(title)))


def write_report(folder, stem, mix, drums, click, payload, sr=22050):
    with wave.open(str(click)) as wav:
        pulse=np.frombuffer(wav.readframes(wav.getnframes()),'<i2').astype(np.float32)/32768
    n=len(pulse);music=np.zeros(n,np.float32);music[:min(n,len(mix))]=mix[:n]
    # One file/clock: left holds music, right holds click. The report mixes
    # these to both speakers, with separate level controls, without drift.
    stereo=np.column_stack([music*.7,pulse*.7])
    audio=folder/(stem+'-review.wav')
    with wave.open(str(audio),'wb') as wav:
        wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(sr)
        wav.writeframes((np.clip(stereo,-1,1)*32767).astype('<i2').tobytes())
    step=round(sr*.01);pad=(-len(drums))%step
    envelope=np.max(abs(np.pad(drums,(0,pad)).reshape(-1,step)),axis=1) if len(drums) else np.zeros(1)
    envelope/=max(float(envelope.max()),1e-9)
    data={'beats':payload['beats'],'quality':payload['quality'],
          'envelope_rate':sr/step,'envelope':np.round(envelope,3).tolist()}
    report=render_html(data,audio.name,payload.get('song','Song'))
    target=folder/(stem+'-review.html');target.write_text(report,encoding='utf-8')
    metadata=folder/(stem+'-review.json');metadata.write_text(json.dumps(data),encoding='utf-8')
    return target.name,audio.name,metadata.name
