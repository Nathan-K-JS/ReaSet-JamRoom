"""Install missing importer dependencies using the launcher's Python."""
from importlib import metadata
from pathlib import Path
import subprocess
import struct
import sys


def probe(code):
    """Use a fresh process: failed native imports can poison this interpreter."""
    try:
        result = subprocess.run([sys.executable, '-c', code], capture_output=True,
                                text=True, timeout=120)
        return '' if result.returncode == 0 else (result.stderr or result.stdout or
                                                 f'Python exited {result.returncode}').strip()
    except subprocess.TimeoutExpired:
        return 'Audio runtime check timed out'


AUDIO_PROBE = '''import numpy as np
import numba
import librosa
y = np.zeros(22050 * 5, dtype=np.float32)
y[::11025] = 1
librosa.beat.beat_track(y=y, sr=22050, bpm=120, units="time")
'''


def repair_audio(error):
    if sys.platform == 'win32' and ('DLL load failed' in error or 'WinError 126' in error):
        subprocess.check_call(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                               '-File', str(Path(__file__).with_name('repair_audio_runtime.ps1')),
                               '-RuntimeArch', 'x64' if struct.calcsize('P') == 8 else 'x86'], timeout=300)
    else:
        # Replace potentially mixed/broken wheels using this launcher's Python.
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--force-reinstall',
                               '--no-cache-dir', '--only-binary=:all:', 'numba',
                               'librosa==0.11.0'], timeout=300)

def main():
    installed = False
    try:
        metadata.version('requests')
        metadata.version('numpy')
        if metadata.version('librosa') == '0.11.0':
            installed = True
    except metadata.PackageNotFoundError:
        pass
    if not installed:
        print('Installing audio analysis support for rehearsal clicks...', flush=True)
        subprocess.check_call([sys.executable,'-m','pip','install','-r',
                           str(Path(__file__).with_name('requirements-runtime.txt'))])
    core_error = probe('import requests; import numpy')
    if core_error:
        raise RuntimeError('Importer runtime is unavailable: ' + core_error)
    print('Checking recording beat detection...', flush=True)
    error = probe(AUDIO_PROBE)
    if error:
        print('Repairing audio runtime: ' + error, flush=True)
        try:
            repair_audio(error)
        except (OSError, subprocess.SubprocessError) as failure:
            print('Audio repair did not complete: ' + str(failure), flush=True)
        error = probe(AUDIO_PROBE)
    if error:
        print('WARNING: Recording beat detection is unavailable. Imports can use a labelled '
              'Fadr fixed-tempo click where beat metadata is available. Run JamRoom Update '
              'again to retry repair.\n' + error, flush=True)
    else:
        print('Recording beat detection passed.', flush=True)

if __name__ == '__main__':
    main()
