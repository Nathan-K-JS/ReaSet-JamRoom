"""Durable local listening copies. REAPER mixes; this service verifies and shares.

Only REAPER-published recording roots are discovered. HTTP callers cannot supply
filesystem paths. Originals are never deleted by this module. GPL-3.0.
"""
import copy
import ctypes
import html
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import threading
from urllib.parse import quote, urlparse

import requests

from jamroom_loudness import scan

ROOT = Path(__file__).resolve().parent.parent
TERMINAL = {'ready', 'failed', 'removed'}


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.new')
    with temp.open('w', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, allow_nan=False)
        f.flush(); os.fsync(f.fileno())
    os.replace(temp, path)


def probe(path, expected):
    ffprobe = shutil.which('ffprobe')
    if not ffprobe:
        raise ValueError('Install ffmpeg with JamRoom Setup before making listening copies')
    result = subprocess.run([ffprobe, '-v', 'error', '-select_streams', 'a:0',
                             '-show_entries', 'stream=channels,sample_rate,bits_per_sample:format=duration',
                             '-of', 'json', str(path)], capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise ValueError('Audio verification failed: ' + result.stderr[-400:])
    data = json.loads(result.stdout); stream = data['streams'][0]
    duration = float(data['format']['duration'])
    if stream['channels'] != 2 or int(stream['sample_rate']) != 48000 or abs(duration - expected) > .15:
        raise ValueError('Rendered audio has unexpected duration or channel format')
    if Path(path).suffix == '.wav' and stream['bits_per_sample'] != 24:
        raise ValueError('Rendered WAV is not 24-bit')
    return duration


def bind_worker_lifetime(proc):
    """A service crash must close its isolated REAPER, including during rendering."""
    if os.name != 'nt':
        raise ValueError('Listening render worker currently requires the Windows room PC')
    from ctypes import wintypes as w
    class Basic(ctypes.Structure):
        _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                    ('flags', w.DWORD), ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t),
                    ('active', w.DWORD), ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
    class IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ('ro', 'wo', 'oo', 'rt', 'wt', 'ot')]
    class Limits(ctypes.Structure):
        _fields_ = [('basic', Basic), ('io', IO), ('process_memory', ctypes.c_size_t),
                    ('job_memory', ctypes.c_size_t), ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    handle = kernel.CreateJobObjectW(None, None)
    limits = Limits(); limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not handle or not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)) or not kernel.AssignProcessToJobObject(handle, w.HANDLE(proc._handle)):
        proc.kill(); proc.wait()
        if handle: kernel.CloseHandle(handle)
        raise RuntimeError('Cannot isolate the REAPER render worker lifetime')
    return lambda: kernel.CloseHandle(handle)


def render(folder, cfg, resource):
    folder, resource = Path(folder), Path(resource)
    resource.mkdir(parents=True, exist_ok=True)
    ini = resource / 'reaper.ini'
    # Explicit private device/config, no copied startup actions or web surfaces.
    ini.write_text('[REAPER]\nwnd_state=2\nnosplash=1\nloadlastproj=0\nrenderclosewhendone=4\n'
                   '[audioconfig]\nmode=4\ndummy_srate=48000\ndummy_blocksize=1024\n', encoding='utf-8')
    script = folder / 'worker.lua'
    script.write_text('\n'.join('LISTEN_' + key + '=' + json.dumps(value.as_posix(), ensure_ascii=False)
                                for key, value in [('FOLDER', folder), ('ROOT', ROOT), ('RESOURCE', resource)]) +
                      '\ndofile(LISTEN_ROOT.."/tools/jamroom_listening_worker.lua")\n', encoding='utf-8')
    result = folder / 'render-result.json'
    result.unlink(missing_ok=True)
    startup = subprocess.STARTUPINFO(); startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW; startup.wShowWindow = 0
    exe = cfg.get('reaper_exe', 'C:/Program Files/REAPER (x64)/reaper.exe')
    proc = subprocess.Popen([exe, '-newinst', '-nosplash', '-noactivate', '-cfgfile', str(ini), str(script)],
                            startupinfo=startup, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    close = bind_worker_lifetime(proc)
    try:
        try:
            proc.wait(timeout=14400)
        except subprocess.TimeoutExpired:
            raise ValueError('Rendering timed out. Source takes are safe; retry or mix in REAPER.')
    finally:
        close()
        proc.wait(timeout=15)
    if not result.is_file():
        raise ValueError('REAPER worker did not complete. Check the REAPER installation, then retry.')
    receipt = json.loads(result.read_text(encoding='utf-8'))
    if not receipt.get('ok'):
        message = receipt.get('error', 'Rendering failed').split('\n')[0]
        raise ValueError(re.sub(r'^.*?\.lua:\d+: ', '', message))
    return receipt


class Listening:
    def __init__(self, config, home=None, paused=lambda: False):
        self.config = config
        self.home = Path(home or ROOT / 'imports' / '.listening')
        self.guard = threading.RLock(); self.stop = threading.Event()
        self.paused = paused; self.active = False; self.thread = None; self.error = ''
        self.home.mkdir(parents=True, exist_ok=True)
        self.index = self.home / 'index.json'
        self.data = json.loads(self.index.read_text(encoding='utf-8')) if self.index.exists() else {'roots': {}, 'jobs': {}}
        for job in self.data['jobs'].values():
            if job['state'] not in TERMINAL:
                job['state'] = 'queued'
        self._save()

    def _save(self):
        atomic(self.index, self.data)

    def start(self):
        if not self.thread:
            self.thread = threading.Thread(target=self._run, name='listening-copies', daemon=True)
            self.thread.start()

    def discover(self):
        cfg = self.config()
        web = cfg.get('reaper_web', 'http://localhost:8080').rstrip('/')
        try:
            response = requests.get(web + '/_/GET/PROJEXTSTATE/ReaSetRec/index', timeout=2)
            response.raise_for_status()
            fields = response.text.strip().split('\t')
            if len(fields) >= 4 and fields[0] == 'PROJEXTSTATE':
                index = Path(fields[-1])
                db = json.loads(index.read_text(encoding='utf-8'))
                if db.get('version') == 1 and db.get('project'):
                    with self.guard:
                        root = str(index.parent / 'Listening')
                        if self.data['roots'].get(db['project']) != root:
                            self.data['roots'][db['project']] = root
                            self._save()
        except (OSError, ValueError, requests.RequestException):
            pass  # Already discovered recordings remain available when REAPER is closed.
        with self.guard:
            for project, root in self.data['roots'].items():
                for path in Path(root).glob('*/request.json'):
                    key = project + ':' + path.parent.name
                    if key in self.data['jobs']:
                        continue
                    try:
                        req = json.loads(path.read_text(encoding='utf-8'))
                        if req.get('project') != project or req.get('id') != path.parent.name or req.get('version') != 1:
                            continue
                        self.data['jobs'][key] = {'key': key, 'id': req['id'], 'project': project,
                            'folder': str(path.parent), 'title': req['title'], 'created': req['created'],
                            'summary': 'With backing' if req.get('backing') else 'Recording only',
                            'state': 'queued', 'token': secrets.token_urlsafe(24), 'files': {}}
                        self._save()
                    except (OSError, ValueError, KeyError):
                        continue

    def listing(self):
        with self.guard:
            return {'error': self.error, 'jobs': [{k: copy.deepcopy(v) for k, v in row.items() if k != 'folder'}
                            for row in self.data['jobs'].values() if row['state'] != 'removed']}

    def change(self, key, **values):
        with self.guard:
            self.data['jobs'][key].update(values); self._save()

    def action(self, key, action):
        with self.guard:
            row = self.data['jobs'][key]
            if action == 'retry' and row['state'] == 'failed':
                row.update(state='queued', error='')
            elif action == 'revoke' and row['state'] in ('ready', 'failed'):
                row['token'] = secrets.token_urlsafe(24)
            elif action == 'remove' and row['state'] in TERMINAL:
                folder = Path(row['folder']); owned = []
                manifest = folder / 'media.json'
                if manifest.exists():
                    for item in json.loads(manifest.read_text(encoding='utf-8')):
                        path = folder / item
                        if not re.fullmatch(r'Media/[0-9]+\.[A-Za-z0-9]+', item) or path.resolve().parent != (folder/'Media').resolve():
                            raise ValueError('Listening media index needs attention; no files were removed')
                        owned.extend([path, path.with_name(path.name + '.new')])
                row.update(state='removed', token=secrets.token_urlsafe(24), files={})
                self._save()  # Revoke first, then unlink only verified private copy assets.
                for path in owned + [folder / name for name in ('mix.wav', 'mix.mp3', 'mix-pending.wav', 'mp3-pending.mp3')]:
                    path.unlink(missing_ok=True)
            else:
                raise ValueError('This copy is busy or the action is unavailable')
            self._save()
        return {'ok': True}

    def ready(self, token):
        with self.guard:
            for row in self.data['jobs'].values():
                if secrets.compare_digest(row['token'], token) and row['state'] in ('ready', 'failed') and row['files']:
                    return copy.deepcopy(row)
        raise ValueError('This listening link is unavailable or has been revoked')

    def _run(self):
        while not self.stop.is_set():
            try:
                self.discover()
                self.error = ''
                with self.guard:
                    key = next((k for k, row in self.data['jobs'].items() if row['state'] == 'queued'), None)
                    self.active = bool(key and not self.paused())
                if self.active:
                    try:
                        self.process(key)
                    except Exception as exc:
                        self.change(key, state='failed', error=str(exc))
                    finally:
                        self.active = False
            except Exception as exc:
                # Temporary storage/network failures must not end future discovery.
                self.active = False; self.error = 'Listening service needs attention: ' + str(exc)
            self.stop.wait(2)

    def process(self, key):
        with self.guard:
            row = copy.deepcopy(self.data['jobs'][key])
        folder = Path(row['folder']); req = json.loads((folder / 'request.json').read_text(encoding='utf-8'))
        expected = req['duration'] / req['rate']
        wav, mp3 = folder / 'mix.wav', folder / 'mix.mp3'
        cfg = self.config()
        if not wav.is_file():
            self.change(key, state='preparing', error='')
            # Simple, saved flat stereo template, independent of room/IEM faders.
            template = self.home / 'mix-template.json'
            if not template.exists():
                atomic(template, {str(n): {'gain': 1, 'pan': 0} for n in range(1, 15)})
            if 'mix' not in req:
                mix = json.loads(template.read_text(encoding='utf-8'))
                for setting in mix.values():
                    if not 0 <= setting['gain'] <= 4 or not -1 <= setting['pan'] <= 1:
                        raise ValueError('Listening mix template has an invalid gain or pan')
                req['mix'] = mix; atomic(folder / 'request.json', req)
            self.change(key, state='rendering')
            receipt = render(folder, cfg, self.home / 'worker')
            self.change(key, state='verifying', render=receipt)
            pending = folder / 'mix-pending.wav'
            probe(pending, expected)
            loud, peak = scan([pending])
            if not math.isfinite(loud) or loud <= -60 or not math.isfinite(peak) or peak > -.8:
                raise ValueError('Listening WAV failed loudness/peak verification; originals retained')
            os.replace(pending, wav)
            self.change(key, loudness=loud, peak=peak)
        probe(wav, expected)
        self.change(key, files={'wav': wav.stat().st_size}, state='encoding')
        if not mp3.is_file():
            ff = shutil.which('ffmpeg')
            if not ff:
                raise ValueError('WAV is ready. Install ffmpeg, then Retry to create the MP3.')
            pending = folder / 'mp3-pending.mp3'
            result = subprocess.run([ff, '-y', '-nostdin', '-v', 'error', '-i', str(wav),
                '-map_metadata', '-1', '-codec:a', 'libmp3lame', '-b:a', '256k', str(pending)],
                capture_output=True, text=True, timeout=14400)
            if result.returncode:
                raise ValueError('WAV is ready; MP3 encoding failed: ' + result.stderr[-400:])
            probe(pending, expected)
            _, peak = scan([pending])
            if not math.isfinite(peak) or peak > 0:
                raise ValueError('WAV is ready; encoded MP3 peaks exceeded headroom. Mix this take in REAPER.')
            os.replace(pending, mp3)
        probe(mp3, expected)
        files = {'wav': wav.stat().st_size, 'mp3': mp3.stat().st_size}
        atomic(folder / 'receipt.json', {'files': files, 'duration': expected, 'ready': True})
        self.change(key, state='ready', files=files, duration=expected, error='')


def serve_audio(handler, path, filename, download=False, head=False):
    """Safari/Chrome single byte ranges, including suffix ranges and HEAD probes."""
    size = path.stat().st_size; start, end = 0, size - 1
    value = handler.headers.get('Range')
    if value:
        match = re.fullmatch(r'bytes=(\d*)-(\d*)', value)
        if not match or not any(match.groups()):
            match = None
        else:
            a, b = match.groups()
            if a:
                start = int(a); end = min(int(b), end) if b else end
            else:
                start = max(0, size - int(b))
        if not match or start > end or start >= size:
            handler.send_response(416); handler.send_header('Content-Range', f'bytes */{size}')
            handler.send_header('Content-Length', '0'); handler.end_headers(); return
    handler.send_response(206 if value else 200)
    handler.send_header('Content-Type', 'audio/mpeg' if path.suffix == '.mp3' else 'audio/wav')
    handler.send_header('Content-Length', str(end - start + 1))
    handler.send_header('Accept-Ranges', 'bytes')
    handler.send_header('Cache-Control', 'no-store')
    handler.send_header('X-Content-Type-Options', 'nosniff')
    if value: handler.send_header('Content-Range', f'bytes {start}-{end}/{size}')
    if download:
        clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename).strip(' .')[:150]
        handler.send_header('Content-Disposition', f"attachment; filename=\"JamRoom{path.suffix}\"; filename*=UTF-8''{quote(clean + path.suffix)}")
    handler.end_headers()
    if head: return
    with path.open('rb') as source:
        source.seek(start); remaining = end - start + 1
        while remaining:
            data = source.read(min(65536, remaining))
            if not data: break
            try: handler.wfile.write(data)
            except (ConnectionError, OSError): break
            remaining -= len(data)


def public_page(row, link):
    title = html.escape(row['title']); token = row['token']
    kind = 'mp3' if 'mp3' in row['files'] else 'wav'
    downloads = ''.join(f'<a class="button {"primary" if ext == "mp3" else ""}" download href="/listen/{token}/download.{ext}">Download {ext.upper()} <small>{size/1048576:.1f} MB</small></a>' for ext, size in sorted(row['files'].items()))
    return (ROOT / 'tools' / 'listening.html').read_text(encoding='utf-8').replace('%%LINK%%', html.escape(link, quote=True)).replace('%%TITLE%%', title).replace('%%TOKEN%%', token).replace('%%KIND%%', kind).replace('%%DOWNLOADS%%', downloads).replace('%%DATE%%', html.escape(row['created']))


def handle_get(handler, service, lan, head=False):
    path = urlparse(handler.path).path
    if path == '/recordings':
        handler._send(200, (ROOT / 'tools' / 'listening-copies.html').read_bytes(), 'text/html'); return True
    if path == '/api/listening':
        handler._send(200, service.listing()); return True
    match = re.fullmatch(r'/listen/([A-Za-z0-9_-]{20,64})(?:/(audio\.(?:wav|mp3)|download\.(?:wav|mp3)|qr.svg))?', path)
    if not match: return False
    try:
        row = service.ready(match[1]); part = match[2]
        host = handler.headers.get('Host', '')
        if not re.fullmatch(r'[A-Za-z0-9.\-]+(?::\d+)?', host): raise ValueError('Invalid room address')
        base = (lan() or 'http://' + host) if host.split(':')[0] in ('localhost', '127.0.0.1') else 'http://' + host
        if part == 'qr.svg':
            import qrcode
            import qrcode.image.svg
            host = handler.headers.get('Host', '')
            if not re.fullmatch(r'[A-Za-z0-9.\-]+(?::\d+)?', host): raise ValueError('Invalid room address')
            base = lan() if host.split(':')[0] in ('localhost', '127.0.0.1') else 'http://' + host
            if not base: raise ValueError('Connect the room PC to Wi-Fi, then reopen this page')
            import io
            output = io.BytesIO()
            qrcode.make(base + '/listen/' + row['token'], image_factory=qrcode.image.svg.SvgPathImage, border=4).save(output)
            handler._send(200, output.getvalue(), 'image/svg+xml')
        elif part:
            kind = part.rsplit('.', 1)[1]
            if kind not in row['files']: raise ValueError('This format is not ready')
            serve_audio(handler, Path(row['folder']) / ('mix.' + kind), row['title'], part.startswith('download'), head)
        else:
            handler._send(200, public_page(row, base + '/listen/' + row['token']).encode('utf-8'), 'text/html')
    except (ValueError, OSError):
        handler._send(404, {'error': 'Listening copy unavailable. Ask the host for a current link.'})
    return True
