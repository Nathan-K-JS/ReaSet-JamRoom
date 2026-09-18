"""Measure cached final backing slots; never rewrite or dynamically compress audio."""
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess

GENERATOR = 'backing-loudness-1'
TARGET = -23.0
CEILING = -3.0


def sources(job, folder):
    folder = Path(folder).resolve()
    result = []
    for row in job.get('slots', []):
        if row['slot'] in ('CLICK', 'SKIP'):
            continue
        path = (folder / row['file']).resolve()
        if not path.is_relative_to(folder):
            raise ValueError('Backing source is outside its cached song folder')
        if not path.is_file():
            raise ValueError('Backing source missing: ' + row['file'])
        result.append((row['slot'], path))
    return sorted(result)


def fingerprint(job, folder):
    rows = [(slot, path.relative_to(Path(folder).resolve()).as_posix(),
             path.stat().st_size, path.stat().st_mtime_ns) for slot, path in sources(job, folder)]
    return hashlib.sha256(json.dumps([GENERATOR, TARGET, CEILING, rows]).encode()).hexdigest()


def scan(paths):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise ValueError('ffmpeg is required for volume matching')
    cmd = [ffmpeg, '-hide_banner', '-nostats', '-nostdin']
    for path in paths:
        cmd += ['-i', str(path)]
    # Floating-point summation retains over-unity peaks for measurement. Mono
    # and stereo files use one consistent stereo reference, never amix averaging.
    layout = ':channel_layouts=stereo' if len(paths) > 1 else ''
    filters = [f'[{i}:a:0]aformat=sample_fmts=dbl:sample_rates=48000{layout}[a{i}]'
               for i in range(len(paths))]
    inputs = ''.join(f'[a{i}]' for i in range(len(paths)))
    filters.append(inputs + f'amix=inputs={len(paths)}:normalize=0:duration=longest,'
                   'ebur128=peak=true:framelog=verbose[out]')
    cmd += ['-filter_complex', ';'.join(filters), '-map', '[out]', '-f', 'null', '-']
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
    if result.returncode:
        raise ValueError('Volume analysis failed: ' + result.stderr[-800:])
    integrated = re.findall(r'\bI:\s*([-+\w.]+)\s+LUFS', result.stderr)
    peaks = re.findall(r'\bPeak:\s*([-+\w.]+)\s+dBFS', result.stderr)
    if not integrated or not peaks:
        raise ValueError('ffmpeg did not return a loudness measurement')
    return float(integrated[-1]), float(peaks[-1])


def analyse(job, folder, log=lambda _: None):
    stamp = fingerprint(job, folder)
    previous = job.get('level') or {}
    if previous.get('revision') == stamp:
        return previous
    files = sources(job, folder)
    report = {'generator': GENERATOR, 'revision': stamp, 'target_lufs': TARGET,
              'ceiling_dbtp': CEILING, 'status': 'unavailable'}
    if not files:
        report['reason'] = 'No backing stems selected'
    else:
        log('Measuring backing volume (click excluded)...')
        loudness, peak = scan([path for _, path in files])
        # Separate returns can peak higher than a summed mix through cancellation.
        for _, path in files if len(files) > 1 else []:
            _, single_peak = scan([path])
            peak = max(peak, single_peak)
        if not math.isfinite(loudness) or loudness <= -65 or not math.isfinite(peak):
            report['reason'] = 'Backing is silent or too quiet to measure reliably'
        else:
            db = min(TARGET - loudness, CEILING - peak, 0.0)
            report.update(status='measured', integrated_lufs=loudness, peak_dbtp=peak,
                          gain=10 ** (db / 20), gain_db=db,
                          limited=db < TARGET - loudness - .05,
                          predicted_lufs=loudness + db)
            log(f'Matched starting level: {report["gain"]:.0%}' +
                (' (limited to preserve headroom)' if report['limited'] else ''))
    job['level'] = report
    return report


def request(job, folder, replace=False):
    report = dict(job['level'])
    report['files'] = [path.as_posix() for _, path in sources(job, folder)]
    report['replace'] = bool(replace)
    return report
