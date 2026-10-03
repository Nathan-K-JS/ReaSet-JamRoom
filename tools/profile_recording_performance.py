"""Profile synthetic library work in a fresh, private Dummy Audio REAPER process.

Windows only. No live projects/configuration, web endpoints or transport actions.
Artifacts are retained in a newly allocated temporary directory for inspection.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import wave


ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reaper', type=Path, default=Path('C:/Program Files/REAPER (x64)/reaper.exe'))
    parser.add_argument('--sws', type=Path, required=True, help='SWS DLL to copy into the private resource directory')
    parser.add_argument('--baseline-ref', default='ee51aac', help='Git revision to compare, read only')
    args = parser.parse_args()
    if os.name != 'nt' or not args.reaper.is_file() or not args.sws.is_file():
        parser.error('Requires Windows, an installed REAPER executable and an SWS DLL')
    folder = Path(tempfile.mkdtemp(prefix='reaset-performance-')).resolve()
    print(f'Isolated artifacts: {folder}', flush=True)
    resource = folder / 'resource'
    (resource / 'UserPlugins').mkdir(parents=True)
    shutil.copyfile(args.sws, resource / 'UserPlugins' / args.sws.name)
    ini = resource / 'reaper.ini'
    ini.write_text('[REAPER]\nwnd_state=2\nnosplash=1\nloadlastproj=0\n'
                   '[audioconfig]\nmode=4\ndummy_srate=48000\ndummy_blocksize=1024\n', encoding='utf-8')
    # Copy code only. The Apply pointer and job must never use the checkout's tools/.
    code = folder / 'code'
    (code / 'tools').mkdir(parents=True)
    (code / 'Requirements').mkdir()
    for path in (ROOT / 'Requirements').glob('*.lua'):
        shutil.copyfile(path, code / 'Requirements' / path.name)
    shutil.copyfile(ROOT / 'tools/jamroom_import_apply.lua', code / 'tools/jamroom_import_apply.lua')
    baseline = subprocess.run(['git', 'show', f'{args.baseline_ref}:Requirements/ReaSet_RecordingCore.lua'],
                              cwd=ROOT, capture_output=True, check=True).stdout
    (folder / 'baseline.lua').write_bytes(baseline)
    with wave.open(str(folder / 'silence.wav'), 'wb') as wav:
        wav.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
        wav.writeframes(bytes(48000 * 2 * 210))
    # 46 tracks, 52 songs, 380 audio items and 8,008 chart items. All generated.
    rows = ['<REAPER_PROJECT 0.1 7.78 1', 'TEMPO 120', 'SAMPLERATE 48000', 'MASTER_VOLUME 0']
    for i in range(52):
        rows += [f'MARKER {i+1} {i*240} "Dummy song {i+1}" 1', f'MARKER {i+1} {i*240+210} "" 0']
    slots = [('DRUMS','PB DRUMS'), ('PERC_FX','PB PERC/FX'), ('BASS','PB BASS'),
             ('GTR1','PB GTR 1'), ('GTR2','PB GTR 2'), ('KEYS','PB KEYS'),
             ('BVS','PB BVs'), ('LEAD_VOX','PB LEAD VOX'), ('CLICK','PB CLICK'), ('EXTRA','PB EXTRA')]
    for slot, name in slots:
        rows += ['<TRACK', f'NAME "{name}"', 'ISBUS 1 1', 'MAINSEND 0', '>',
                 '<TRACK', f'NAME "[JR:{slot}] Dummy"', 'ISBUS 2 -1', 'MAINSEND 0']
        for i in range(38):
            rows += ['<ITEM', f'POSITION {i*240}', 'LENGTH 210', 'VOLPAN 1 0 1 -1',
                     '<SOURCE WAVE', f'FILE "{(folder / "silence.wav").as_posix()}"', '>', '>']
        rows += ['>']
    for name in ('lyrics', 'chords'):
        rows += ['<TRACK', f'NAME "{name}"', 'MAINSEND 0']
        for i in range(4004):
            rows += ['<ITEM', f'POSITION {(i%52)*240+(i//52)*2}', 'LENGTH 1',
                     '<NOTES', '|Synthetic chart text', '>', '>']
        rows += ['>']
    for i in range(24):
        rows += ['<TRACK', f'NAME "Unused {i}"', 'MAINSEND 0', '>']
    rows += ['>']
    (folder / 'dummy.RPP').write_text('\n'.join(rows)+'\n', encoding='utf-8')
    job = folder / 'job'
    job.mkdir()
    (code / 'tools/jamroom_pending_job.txt').write_text(job.as_posix(), encoding='utf-8')
    stem_rows = []
    for slot, _ in slots:
        stem = job / (slot + '.wav')
        shutil.copyfile(folder / 'silence.wav', stem)
        stem_rows.append('{slot='+json.dumps(slot)+',label="Dummy",file='+json.dumps(stem.as_posix())+'}')
    (job / 'job_for_reaper.lua').write_text(
        'local lines,chords={},{}\nfor i=1,100 do lines[i]={t=i*2,text="Dummy lyric"};'
        'chords[i]={s=i*2,e=i*2+1,name="C"}end\n'
        'return {region_name="Synthetic import",duration=210,lyrics_lines=lines,chords=chords,'
        'slots={'+','.join(stem_rows)+'}}\n',
        encoding='utf-8')
    wrapper = folder / 'worker.lua'
    wrapper.write_text('PROFILE_FOLDER='+json.dumps(folder.as_posix())+'\n'
                       'dofile('+json.dumps((ROOT/'tools/profile_recording_performance.lua').as_posix())+')\n',
                       encoding='utf-8')
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    proc = subprocess.Popen([str(args.reaper), '-newinst', '-nosplash', '-noactivate', '-cfgfile', str(ini), str(wrapper)],
                            startupinfo=startup, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    print(f'Private REAPER PID: {proc.pid}', flush=True)
    report = None
    try:
        deadline = time.monotonic() + 180
        while proc.poll() is None and time.monotonic() < deadline:
            try:
                report = json.loads((folder / 'result.json').read_text(encoding='utf-8'))
                if 'ok' in report:
                    # Allow normal Quit; on failure close only our worker below.
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        pass
                    break
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            time.sleep(.25)
    finally:
        # Only the process created above; never enumerate/kill other REAPERs.
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=15)
    report = json.loads((folder / 'result.json').read_text(encoding='utf-8'))
    print(json.dumps(report, indent=2))
    if not report.get('ok'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
