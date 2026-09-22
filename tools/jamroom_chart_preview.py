"""Cached, local chart audition audio. No click, network or paid processing."""
import hashlib
import json
import shutil
import subprocess
import threading
import wave
from pathlib import Path

_lock = threading.Lock()
_states = {}


def prepare(folder, job):
    folder = Path(folder).resolve()
    originals = [p for p in folder.glob('source.*') if p.suffix.lower() in ('.m4a', '.mp3', '.wav', '.flac', '.ogg')]
    sources = originals[:1] or [folder / s['file'] for s in job.get('stems', [])
                               if str(s.get('slot', '')).upper() != 'CLICK' and 'click' not in s['file'].lower()]
    sources = [p.resolve() for p in sources if p.is_file() and p.resolve().is_relative_to(folder)]
    if not sources: raise ValueError('No cached song audio. You can still edit the chart.')
    duration = float(job['duration'])
    key = hashlib.sha256(json.dumps([(str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in sources]).encode()+str(duration).encode()).hexdigest()[:16]
    dest = folder / '.chart-preview' / key
    with _lock:
        if (dest / 'peaks.json').exists() and (dest / 'audio.wav').exists():
            return {'state':'ready', 'key':key, **json.loads((dest / 'peaks.json').read_text())}
        if key in _states: return dict(_states[key])
        _states[key] = {'state':'preparing', 'message':'Preparing full-song audio and waveform…', 'key':key}
        def work():
            try:
                dest.mkdir(parents=True, exist_ok=True)
                ff = shutil.which('ffmpeg')
                if not ff: raise ValueError('Install FFmpeg to audition cached audio.')
                cmd = [ff, '-v', 'error', '-y']
                for source in sources: cmd += ['-i', str(source)]
                # PCM has no encoder priming: chart zero equals decoded source zero.
                filters = ('amix=inputs=%d:normalize=1,' % len(sources)) if len(sources)>1 else ''
                cmd += ['-filter_complex', filters+'apad', '-t', str(duration), '-ar', '22050', '-ac', '1', '-c:a', 'pcm_s16le', str(dest / 'audio.part.wav')]
                result = subprocess.run(cmd, capture_output=True, timeout=300, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if result.returncode: raise ValueError(result.stderr.decode(errors='replace')[-500:])
                import numpy as np
                with wave.open(str(dest / 'audio.part.wav')) as wav:
                    frames = wav.getnframes(); rate = wav.getframerate()
                    if abs(frames/rate-duration) > .05: raise ValueError('Preview duration does not match song time.')
                    samples = np.frombuffer(wav.readframes(frames), dtype='<i2').astype(float)/32768
                peaks = [round(float(np.max(np.abs(a))),4) if len(a) else 0 for a in np.array_split(samples, min(12000,frames))]
                (dest / 'audio.part.wav').replace(dest / 'audio.wav')
                data = {'peaks':peaks, 'duration':duration, 'origin':0}
                (dest / 'peaks.json').write_text(json.dumps(data), encoding='utf-8')
                with _lock: _states.pop(key,None)
            except Exception as error:
                with _lock: _states[key]={'state':'error','message':str(error),'key':key}
        threading.Thread(target=work, daemon=True).start()
        return dict(_states[key])
