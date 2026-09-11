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


AUDIO_PROBE = ("import sys; sys.path.insert(0, " + repr(str(Path(__file__).resolve().parent)) +
               "); from jamroom_beat_runtime import check_runtime; check_runtime()")


def diagnostic(error):
    path=Path(__file__).resolve().parent.parent/'imports'/'.runtime'/'beat-runtime.log'
    try:
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('a',encoding='utf-8') as output: output.write(error+'\n')
    except OSError:
        print(error,flush=True)
    return path


def repair_audio(error):
    if sys.platform == 'win32' and ('DLL load failed' in error or 'WinError 126' in error):
        subprocess.check_call(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                               '-File', str(Path(__file__).with_name('repair_audio_runtime.ps1')),
                               '-RuntimeArch', 'x64' if struct.calcsize('P') == 8 else 'x86'], timeout=300)
    else:
        # Replace potentially mixed/broken wheels using this launcher's Python.
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--force-reinstall',
                               '--no-cache-dir', '--only-binary=:all:', '-r',
                               str(Path(__file__).with_name('requirements-runtime.txt'))], timeout=300)

def main():
    installed = False
    try:
        metadata.version('requests')
        metadata.version('numpy')
        if (metadata.version('beat-this') == '1.1.0' and metadata.version('torch') == '2.14.0'
                and metadata.version('torchaudio') == '2.11.0' and metadata.version('scipy')):
            installed = True
    except metadata.PackageNotFoundError:
        pass
    if not installed:
        print('Installing audio analysis support for rehearsal clicks...', flush=True)
        try:
            subprocess.check_call([sys.executable,'-m','pip','install','-r',
                               str(Path(__file__).with_name('requirements-runtime.txt'))])
        except (OSError,subprocess.SubprocessError) as error:
            print('Analysis package installation did not finish. Details: '+str(diagnostic(str(error))),flush=True)
    core_error = probe('import requests; import numpy')
    if core_error:
        raise RuntimeError('Importer runtime is unavailable: ' + core_error)
    try:
        from jamroom_beat_runtime import prepare_models
        prepare_models(lambda message:print(message,flush=True))
    except Exception as error:
        print('Beat model preparation did not finish. Details: '+str(diagnostic(str(error))),flush=True)
    print('Checking recording beat detection...', flush=True)
    error = probe(AUDIO_PROBE)
    if error:
        print('Beat analysis check failed; attempting runtime repair. Details: '+str(diagnostic(error)), flush=True)
        try:
            repair_audio(error)
        except (OSError, subprocess.SubprocessError) as failure:
            print('Audio repair did not complete. Details: '+str(diagnostic(str(failure))), flush=True)
        error = probe(AUDIO_PROBE)
    if error:
        print('WARNING: Beat analysis is unavailable. The updater can continue, but songs will '
              'import without a click until analysis works. No fixed-tempo fallback is used. '
              'Details: '+str(diagnostic(error)), flush=True)
    else:
        print('Recording beat detection passed.', flush=True)

if __name__ == '__main__':
    main()
