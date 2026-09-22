"""Validation and provenance for authored schema-2 charts. GPL-3.0."""
import copy
import json
import math

STATES = {'estimated', 'matched', 'manual', 'checked'}


def validate(value, duration):
    def number(n):
        return isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n)
    if not number(duration) or duration <= 0 or not isinstance(value, dict):
        raise ValueError('Invalid chart duration')
    if len(json.dumps(value, ensure_ascii=False).encode('utf-8')) > 196608:
        raise ValueError('Chart is too large (192 KB limit)')
    doc = copy.deepcopy(value)
    sections = doc.get('sections')
    if doc.get('schema') != 2 or not isinstance(sections, list) or not 1 <= len(sections) <= 256:
        raise ValueError('Choose between 1 and 256 sections')
    if any(not isinstance(s, dict) for s in sections): raise ValueError('Invalid chart sections')
    offset = doc.get('timing_offset', 0)
    if not number(offset) or abs(offset) >= duration:
        raise ValueError('Invalid chart timing offset')
    ids, total = set(), 0
    for i, s in enumerate(sections):
        end = sections[i+1].get('start') if i+1 < len(sections) else duration
        start = s.get('start')
        if not number(start) or not number(end) or start < 0 or end <= start or end > duration or i == 0 and start != 0:
            raise ValueError('Section starts must increase from zero within the song')
        for obj, prefix in [(s, 'section')]:
            ident = obj.get('id')
            if not isinstance(ident, str) or not 1 <= len(ident) <= 100 or ident in ids:
                raise ValueError('Chart identities must be unique')
            ids.add(ident)
        if not isinstance(s.get('label'), str) or not 1 <= len(s['label'].strip()) <= 160:
            raise ValueError('Name each section')
        rows = s.get('rows')
        if not isinstance(rows, list): raise ValueError('Invalid chart lines')
        total += len(rows)
        if total > 4096: raise ValueError('Too many chart lines')
        s['end'] = end
        s['timing_status'] = s.get('timing_status') if s.get('timing_status') in STATES else 'estimated'
        s['confidence'] = 'section checked' if s['timing_status'] == 'checked' else 'estimated'
        s['progression'] = []
        s['kind'] = 'instrumental'
        if not number(s.get('repeat', 1)) or not 1 <= s.get('repeat', 1) <= 32:
            raise ValueError('Repeat must be between 1 and 32')
        for row in rows:
            if not isinstance(row, dict): raise ValueError('Invalid chart line')
            ident = row.get('id')
            if not isinstance(ident, str) or not 1 <= len(ident) <= 100 or ident in ids:
                raise ValueError('Chart identities must be unique')
            ids.add(ident)
            for key in ('text', 'chord_line'):
                if not isinstance(row.get(key, ''), str) or len(row.get(key, '')) > 8192:
                    raise ValueError('Chart line is too long')
            if row.get('text', '').strip(): s['kind'] = 'vocal'
            anchors = row.get('anchors', [])
            if not isinstance(anchors, list) or len(anchors) > 256: raise ValueError('Invalid chords')
            last = -1
            for a in anchors:
                if not isinstance(a, dict): raise ValueError('Invalid chord')
                col = a.get('offset')
                if not number(col) or int(col) != col or col < 0 or col > 8192 or col < last:
                    raise ValueError('Invalid chord position')
                if not isinstance(a.get('symbol'), str) or not 1 <= len(a['symbol']) <= 40:
                    raise ValueError('Invalid chord symbol')
                if not number(a.get('width', len(a['symbol']))) or not 1 <= a.get('width', len(a['symbol'])) <= 40:
                    raise ValueError('Invalid chord width')
                last = col
                s['progression'].append(a['symbol'])
            if 'cue' in row and (not number(row['cue']) or not start <= row['cue'] < end):
                row.pop('cue', None); row.pop('cue_confidence', None)
            cues = row.get('page_cues', {})
            if not isinstance(cues, dict): raise ValueError('Invalid page cues')
            row['page_cues'] = {k: v for k, v in cues.items() if str(k).isdigit() and int(k) <= 8192 and number(v) and start <= v < end}
        s['missing_source_chords'] = not s['progression'] and s['kind'] == 'instrumental'
    doc.update(duration=duration, authored=True, manual=True, source_preserved=False)
    return doc


def lyric_items(doc):
    """Fallback display uses authored words; evidence stays in the source job."""
    result = []
    for s in doc['sections']:
        text = '\n'.join(r.get('text', '') for r in s['rows'] if r.get('text', '').strip())
        if text: result.append({'start': s['start'], 'end': s['end'], 'text': text})
    return result
