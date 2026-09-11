"""Install missing importer dependencies using the launcher's Python."""
from importlib import metadata
from pathlib import Path
import subprocess
import sys

def main():
    try:
        metadata.version('requests')
        metadata.version('numpy')
        if metadata.version('librosa') == '0.11.0':
            return
    except metadata.PackageNotFoundError:
        pass
    print('Installing audio analysis support for rehearsal clicks...', flush=True)
    subprocess.check_call([sys.executable,'-m','pip','install','-r',
                           str(Path(__file__).with_name('requirements-runtime.txt'))])

if __name__ == '__main__':
    main()
