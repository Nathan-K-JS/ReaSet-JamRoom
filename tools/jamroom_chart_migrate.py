"""Lossless, explicit schema-2 page-cue conversion. No project/network writes."""
import copy
import math
import re


def effective_document(value, lyrics_curve='', chords_curve=''):
    """Match native section display; legacy lyric/chord curves never add together."""
    doc = copy.deepcopy(value)
    if doc.get('schema') == 3:
        return doc
    points = sorted((float(a), float(b)) for a, b in re.findall(r'([-\d.]+)=([-\d.]+)', lyrics_curve))
    duration = doc['duration']
    def mapped(t):
        if not points:
            return t
        a,b = points[0] if t <= points[0][0] else points[-1]
        delta = b-a
        for (a,b),(c,d) in zip(points,points[1:]):
            if a <= t <= c:
                f = (t-a)/max(.001,c-a)
                delta = b-a+((d-c)-(b-a))*f
                break
        return max(0,min(duration,t+delta))
    if lyrics_curve or chords_curve:
        doc['legacy_repairs'] = {'lyrics':lyrics_curve, 'chords':chords_curve}
    for section in doc['sections']:
        section['start'],section['end'] = mapped(section['start']),mapped(section['end'])
        for row in section.get('rows', []):
            for key in ('start','end','cue'):
                if key in row: row[key] = mapped(row[key])
            if row.get('page_cues'):
                row['page_cues'] = {col:mapped(t) for col,t in row['page_cues'].items()}
    return doc


def convert(value):
    doc = copy.deepcopy(value)
    if doc.get('schema') == 3 or not doc.get('sections'):
        return doc
    original = copy.deepcopy(value)
    result = []
    try:
        for si, section in enumerate(doc['sections']):
            part = dict(section, rows=[])
            result.append(part)
            last = section['start']
            for ri, row in enumerate(section.get('rows', [])):
                words, chords = row.get('text', ''), row.get('chord_line', '')
                anchors = row.get('anchors', [])
                width = max([len(words), len(chords)] + [a['offset']+len(a['symbol']) for a in anchors])
                begin = 0

                def piece(end):
                    nonlocal begin
                    if end <= begin:
                        return
                    r = copy.deepcopy(row)
                    r['id'] = row.get('id', f'legacy-{si}-{ri}') + (f'-col-{begin}' if begin else '')
                    r['source_row'] = row.get('id')
                    r['text'], r['chord_line'] = words[begin:end], chords[begin:end]
                    r['anchors'] = [dict(a, offset=a['offset']-begin) for a in anchors if begin <= a['offset'] < end]
                    r.pop('page_cues', None)
                    if begin:
                        r.pop('cue', None)
                        r.pop('timing_evidence', None)
                    part['rows'].append(r)
                    begin = end

                for raw, t in sorted(row.get('page_cues', {}).items(), key=lambda pair: int(pair[0])):
                    col = int(raw)
                    if not 0 <= col < max(1, width) or not isinstance(t, (int, float)) or not math.isfinite(t) or not last <= t < section['end']:
                        raise ValueError('A saved page cue conflicts with its section.')
                    if any(a['offset'] < col < a['offset']+a.get('width', len(a['symbol'])) for a in anchors) or 0 < col < len(words) and words[col-1:col+1].strip() == words[col-1:col+1]:
                        raise ValueError('A saved page cue cuts through a word or chord.')
                    piece(col)
                    if t == last:
                        if part['rows'] or col:
                            raise ValueError('Saved page cues share a time.')
                        continue
                    part['end'] = t
                    part = dict(section, id=section.get('id', f'legacy-{si}')+f'-cue-{ri}-{col}',
                                label=section['label']+' - continued', start=t, rows=[],
                                timing_status='checked', confidence='section checked')
                    result.append(part)
                    last = t
                if width:
                    piece(width)
                else:
                    r = copy.deepcopy(row)
                    r.pop('page_cues', None)
                    part['rows'].append(r)
        if result[0]['start'] > 0:
            result.insert(0, {'id':'legacy-opening','label':'Intro','start':0,'end':result[0]['start'],
                              'rows':[], 'kind':'instrumental','timing_status':'estimated'})
        doc.update(schema=3, sections=result, migration_snapshot=original)
        return doc
    except (ValueError, TypeError, KeyError) as exc:
        original['migration_issue'] = str(exc)
        return original
