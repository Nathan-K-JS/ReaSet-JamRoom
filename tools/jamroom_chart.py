"""Structured, recording-relative performance charts. No network or REAPER IO.

GPL-3.0. Content/word anchors survive imperfect timing; estimated events are
explicitly identified. Blank LRC entries terminate vocals, never disappear.
"""
import copy
import difflib
import hashlib
import json
import math
import re

GENERATOR = "source-pages-3"
PARSER = 2
SCHEMA = 2
CH = re.compile(r"\[ch\](.*?)\[/ch\]", re.I)
HEADER = re.compile(r"^\s*\[?(lead break|guitar solo|intro|verse|chorus|pre[- ]?chorus|post[- ]?chorus|bridge|solo|outro|"
                    r"interlude|instrumental|refrain|break|hook|riff|ending|coda|tag)\b([^\]]*)\]?\s*$", re.I)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     separators=(",", ":")).encode()).hexdigest()


def norm(text):
    return " ".join(re.sub(r"[^\w ]", " ", text.casefold()).split())


def lyric_items(job):
    ly = job.get("lyrics") or {}
    if not ly.get("synced"):
        return []
    shift = ly.get("offset_override")
    if shift is None:
        shift = (ly.get("align") or {}).get("shift", 0) or 0
    duration = float(job.get("duration") or 0)
    lines = sorted(({"start": max(0., float(l["time"]) + float(shift)),
                     "text": str(l.get("text", ""))} for l in ly.get("lines", [])),
                   key=lambda l: l["start"])
    out = []
    for i, line in enumerate(lines):
        end = min(duration, line["start"] + 15,
                  lines[i + 1]["start"] if i + 1 < len(lines) else duration)
        if line["text"].strip() and end > line["start"]:
            out.append(dict(line, end=end))
    return out


def parse_chart(content, transpose=lambda x: x):
    """Source columns and source wording are inseparable. Never trim one alone."""
    lines = re.sub(r"\[/?tab\]", "", content, flags=re.I).replace("\r", "").expandtabs(8).split("\n")
    sections, current = [], None
    has_headers = any(HEADER.match(line) for line in lines)
    diagram = re.compile(r"^\s*[eBGDAE]\|", re.I)
    def new_section(label):
        repeat = re.search(r"\s+x\s*(\d+)\s*$", label, re.I)
        item = {"label": label[:repeat.start()].strip() if repeat else label,
                "rows": [], "repeat": min(32, max(1, int(repeat.group(1)))) if repeat else 1}
        sections.append(item)
        return item
    i = 0
    while i < len(lines):
        line = lines[i]
        header = HEADER.match(line)
        reference = re.match(r"^\s*repeat\s+(chorus|verse|bridge|intro|solo)(.*)$", line, re.I)
        if header or reference:
            m = header or reference
            current = new_section((m.group(1) + m.group(2)).strip().title())
            i += 1
            continue
        if current is None:
            if has_headers:
                i += 1
                continue
            current = new_section("Song")
        if diagram.match(line) or re.match(r"^[\s\u2191\u2193~^v]+$", line):
            repeat = re.search(r"\bx(\d+)", line)
            if repeat and current["rows"]:
                current["rows"][-1]["repeat"] = min(32, int(repeat.group(1)))
            i += 1
            continue
        if not line.strip():
            i += 1
            continue
        # Untagged no-chord instructions are musical content, too.
        line = re.sub(r"(?<![\w>])N\.C\.(?!\[/ch\])", "[ch]N.C.[/ch]", line)
        anchors, plain, last = [], "", 0
        for m in CH.finditer(line):
            plain += line[last:m.start()]
            anchors.append({"symbol": transpose(m.group(1).strip()), "offset": len(plain),
                            "width": len(m.group(1))})
            plain += m.group(1)
            last = m.end()
        plain += line[last:]
        if anchors:
            words = ""
            if i+1 < len(lines):
                nxt = lines[i+1]
                if (nxt.strip() and not CH.search(nxt) and not HEADER.match(nxt)
                        and not diagram.match(nxt) and not re.match(r"\s*(repeat|x\s*\d)", nxt, re.I)):
                    words = nxt
                    i += 1
            repeat = re.search(r"\bx\s*(\d+)", plain, re.I)
            row = {"text": words, "anchors": anchors, "repeat": 1, "chord_line": plain}
            if repeat:
                row["repeat"] = min(32, int(repeat.group(1)))
                # 'pattern x4, E' has a coda, not four repetitions of the coda.
                row["repeat_at"] = sum(a["offset"] < repeat.start() for a in anchors)
            current["rows"].append(row)
        elif re.fullmatch(r"\s*(?:x\s*|repeat\s+)(\d+)\s*", line, re.I):
            current["repeat"] = min(32, int(re.search(r"\d+", line).group()))
        elif not re.match(r"\s*(capo|tuning|key|https?:)", line, re.I):
            current["rows"].append({"text": line, "anchors": [], "repeat": 1})
        i += 1
    for si, section in enumerate(sections):
        section["id"] = "template-" + str(si)
        if not section["rows"]:
            family = re.sub(r"\d+", "", norm(section["label"])).strip()
            previous = next((x for x in reversed(sections[:si]) if x["rows"] and
                             re.sub(r"\d+", "", norm(x["label"])).strip() == family), None)
            if previous:
                section["rows"] = copy.deepcopy(previous["rows"])
                section["reference"] = previous["id"]
        section["kind"] = "vocal" if any(r["text"].strip() for r in section["rows"]) else "instrumental"
        for ri, row in enumerate(section["rows"]):
            row["id"] = f"source-{si}-{ri}"
    return sections


def _tokens(text):
    # Match across punctuation, hyphenated syllables and different line breaks.
    return re.findall(r"[a-z0-9]+", re.sub(r"['\u2019\-]", "", text.casefold()))


def source_sections(templates):
    """Headings can be wrong; words, columns and occurrence order cannot change."""
    sections, issues = [], []
    instrumental = re.compile(r"^(instrumental|solo|guitar solo|lead break|interlude|riff|break)\b", re.I)
    for ti, original in enumerate(templates):
        section = copy.deepcopy(original)
        section['template'] = ti
        vocal = [r for r in section['rows'] if _tokens(r['text'])]
        if not instrumental.match(section['label']) or not vocal:
            sections.append(section)
            continue
        words = [w for r in vocal for w in _tokens(r['text'])]
        labels = set()
        for candidate in templates:
            if instrumental.match(candidate['label']):
                continue
            other = [w for r in candidate['rows'] for w in _tokens(r['text'])]
            # Require a whole repeated passage, not a common phrase or a guess
            # based on harmony. Ambiguous verse/chorus matches stay unnamed.
            if len(vocal) >= 2 and len(words) >= 8 and other:
                if difflib.SequenceMatcher(None, words, other, autojunk=False).ratio() >= .9:
                    labels.add(re.sub(r'\s*\d+\s*$', '', candidate['label']).strip())
        label = next(iter(labels)) if len(labels) == 1 else 'Vocal section'
        first = next(i for i, r in enumerate(section['rows']) if _tokens(r['text']))
        if first:
            lead = copy.deepcopy(section)
            lead.update(rows=section['rows'][:first], kind='instrumental')
            sections.append(lead)
        section.update(rows=section['rows'][first:], label=label, kind='vocal',
                       source_label=original['label'], structure_confidence='inferred')
        sections.append(section)
        issues.append({'code':'heading_contains_vocals', 'row':vocal[0]['id'],
                       'message':f"{original['label']} contains lyrics; separated as {label}. Check the section name."})
    return sections, issues


def build_document(job, templates, detected, transpose=lambda x: x):
    if not templates:
        return _build_unscored_document(job, [], detected, transpose)
    duration = float(job.get("duration") or 0)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Recording duration is missing or invalid")
    sections, issues = source_sections(templates)
    source_words, source_owner = [], []
    for si, section in enumerate(sections):
        section.update(id=f"section-{si}", evidence="chart", confidence="estimated", event_timing="unresolved")
        for ri, row in enumerate(section["rows"]):
            row.setdefault("id", f"source-{si}-{ri}")
            for anchor in row["anchors"]:
                anchor["symbol"] = transpose(anchor["symbol"])
            tokens = _tokens(row["text"])
            source_words.extend(tokens)
            source_owner.extend([(si, ri)] * len(tokens))
        section["progression"] = [a["symbol"] for r in section["rows"] for a in r["anchors"]]
    lyrics = lyric_items(job)
    sung_words, sung_owner = [], []
    for li, line in enumerate(lyrics):
        tokens = _tokens(line["text"])
        sung_words.extend(tokens)
        sung_owner.extend([(li, ti, len(tokens)) for ti in range(len(tokens))])
    row_matches = {}
    # Ordered whole-song alignment disambiguates repeated choruses. It provides
    # cue estimates ONLY. The source rows/anchors above are never rewritten.
    matcher = difflib.SequenceMatcher(None, source_words, sung_words, autojunk=False)
    for block in matcher.get_matching_blocks():
        if block.size < 3:
            continue
        for k in range(block.size):
            si, ri = source_owner[block.a+k]
            li, ti, count = sung_owner[block.b+k]
            row_matches.setdefault((si, ri), []).append((li, ti, count))
    starts = [None] * len(sections)
    vocal_ends = {}
    matched_rows = 0
    for si, section in enumerate(sections):
        for ri, row in enumerate(section["rows"]):
            matches = row_matches.get((si, ri), [])
            if not matches:
                continue
            li, ti, count = matches[0]
            line = lyrics[li]
            cue = line["start"] + (line["end"]-line["start"]) * ti / max(1,count)
            row["cue"] = round(cue, 3)
            row["cue_confidence"] = "estimated"
            matched_rows += 1
            if starts[si] is None:
                starts[si] = cue
            vocal_ends[si] = lyrics[matches[-1][0]]["end"]
    # Keep every source section in order. Unlocated sections get explicit
    # estimated cues between neighbouring evidence, never a new lyric layout.
    if starts[0] is None:
        starts[0] = 0.
    for si in range(len(sections)):
        if starts[si] is not None:
            continue
        left = si-1
        right = next((k for k in range(si+1,len(sections)) if starts[k] is not None),len(sections))
        a = max(starts[left], vocal_ends.get(left, starts[left]))
        b = starts[right] if right < len(sections) else duration
        a = min(a, b-.1*(right-left))
        for k in range(si,right):
            starts[k] = a+(b-a)*(k-si)/max(1,right-si)
    if starts[0] > 0:
        # A chart without an intro is shown from the start; it doesn't invent
        # an audio-derived intro progression before its first written section.
        starts[0] = 0.
    for si, section in enumerate(sections):
        lower = starts[si-1]+.05 if si else 0.
        starts[si] = max(lower,min(float(starts[si]),duration-.05*(len(sections)-si)))
        section["start"] = round(starts[si],3)
    for si, section in enumerate(sections):
        section["end"] = sections[si+1]["start"] if si+1<len(sections) else duration
    # LRC line ends often mean "next lyric starts", not "singing stopped".
    # Do not manufacture a standalone instrumental page in that zero-width gap.
    # Keep its written passage on the preceding page, where it remains available
    # until the next vocal entrance. The section editor can split it again once
    # the musician supplies the missing boundary.
    grouped = []
    for section in sections:
        if grouped and section['kind'] == 'instrumental' and section['end']-section['start'] < 2:
            previous = grouped[-1]
            if section['rows']:
                section['rows'][0]['source_section'] = section['label']
            previous['rows'].extend(section['rows'])
            previous['progression'].extend(section['progression'])
            previous['end'] = section['end']
            previous['label'] += ' / ' + section['label']
            issues.append({'code':'unresolved_instrumental_boundary', 'section':previous['id'],
                           'message':'Instrumental boundary has no usable interval; passage kept with the preceding section. Split and tap its start if needed.'})
        else:
            grouped.append(section)
    sections = grouped
    source_count = len(source_words)
    matched_words = sum(len(matches) for matches in row_matches.values())
    if matched_words < source_count * .9:
        issues.append({'code':'unmatched_source_words', 'message':'Some chart words have no reliable recording match. Check the source version and page cues.'})
    if matched_words < len(sung_words) * .9:
        issues.append({'code':'unrepresented_recording_words', 'message':'Some timed recording words are absent from the chart. Check for missing passages or a different song version.'})
    for section in sections:
        if section['end']-section['start'] < 2:
            issues.append({'code':'short_section', 'section':section['id'], 'message':'Section lasts less than two seconds; check its boundary.'})
    doc = {"schema":SCHEMA,"generator":GENERATOR,"source_preserved":True,"duration":duration,
           "sections":sections,"templates":copy.deepcopy(templates),
           "source_hash":fingerprint(templates),"lyrics_hash":fingerprint(job.get("lyrics",{})),
           "alignment":{"matched_rows":matched_rows,"source_rows":sum(bool(r["text"].strip()) for s in sections for r in s["rows"]),
                        "purpose":"section cues only"},
           "review":{"status":"needs_review", "issues":issues,
                     "timing":"estimated", "message":"Source chord placement preserved. Section names and playback cues still need review; text matching does not verify musical timing."}}
    doc["revision"] = fingerprint(doc)
    # Precise views retain measured evidence, distinct from the authored chart.
    events = [dict(c) for c in detected if 0 <= c["start"] < c["end"] <= duration]
    validate_document(doc)
    return doc, events


def _build_unscored_document(job, templates, detected, transpose=lambda x: x):
    duration = float(job.get("duration") or max([c["end"] for c in detected] or [0]))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Recording duration is missing or invalid")
    lyrics = lyric_items(dict(job, duration=duration))
    templates = copy.deepcopy(templates)
    for template in templates:
        for row in template["rows"]:
            for anchor in row["anchors"]:
                anchor["symbol"] = transpose(anchor["symbol"])
    candidates = [(si, ri, row) for si, s in enumerate(templates)
                  for ri, row in enumerate(s["rows"]) if norm(row["text"])]
    rows = []
    for line in lyrics:
        scores = sorted([(difflib.SequenceMatcher(None, norm(line["text"]), norm(r["text"])).ratio(), si, ri, r)
                         for si, ri, r in candidates], key=lambda x: -x[0])
        best = scores[0] if scores and scores[0][0] >= .72 else None
        if best:
            # Identical words with conflicting harmony must not silently choose
            # an arbitrary chorus. Equal repeated templates are safe to reuse.
            tied = [x for x in scores if x[0] >= best[0] - .03]
            signatures = {tuple(a["symbol"] for a in x[3]["anchors"]) for x in tied}
            if len(signatures) > 1:
                best = None
        row = dict(line, anchors=[], template=None, row_index=-1, repeat=1)
        if best:
            score, si, ri, original = best
            row.update(template=si, row_index=ri, repeat=original.get("repeat", 1))
            # Columns only describe the printed wording. A fuzzy text match can
            # reuse a progression, but cannot establish new word positions.
            if norm(line["text"]) == norm(original["text"]):
                mapping = difflib.SequenceMatcher(None, original["text"], line["text"]).get_matching_blocks()
                for a in original["anchors"]:
                    at = min(len(original["text"]), a["offset"])
                    block = next((b for b in mapping if b.a <= at < b.a + b.size), None)
                    if at == len(original["text"]):
                        row["anchors"].append(dict(a, offset=len(line["text"])))
                    elif block:
                        row["anchors"].append(dict(a, offset=block.b+at-block.a))
                    else:
                        row["anchors"] = []
                        row["progression"] = [a["symbol"] for a in original["anchors"]]
                        break
            else:
                row["progression"] = [a["symbol"] for a in original["anchors"]]
        rows.append(row)

    # Short breathing gaps and source-template changes inside one verse are
    # not new musical sections. Keep line ends intact while grouping passages.
    def family(template):
        return re.sub(r"\s+\d+\b", "", norm(templates[template]["label"])) if template is not None else ""

    sections = []
    for row in rows:
        prev = sections[-1] if sections else None
        template = row["template"]
        same = prev and (family(prev["template"]) == family(template) or template is None)
        if (prev and prev["kind"] == "vocal" and same
                and row["start"] - prev["end"] < 4):
            prev["rows"].append(row)
            prev["end"] = row["end"]
        else:
            sections.append({"label": templates[template]["label"] if template is not None else "Vocal passage",
                             "template": template, "kind": "vocal", "start": row["start"], "end": row["end"],
                             "rows": [row], "confidence": "approximate"})
    gaps, end = [], 0
    for s in sections:
        if s["start"] - end > .5:
            gaps.append((end, s["start"]))
        end = s["end"]
    if duration - end > .5:
        gaps.append((end, duration))
    if not sections and not gaps:
        gaps = [(0, duration)]
    vocals = list(sections)
    instrumentals = [(i, s) for i, s in enumerate(templates) if s["kind"] == "instrumental" and s["rows"]]
    used = set()
    for start, end in gaps:
        prev = next((s for s in reversed(vocals) if s["end"] <= start and s["template"] is not None), None)
        nxt = next((s for s in vocals if s["start"] >= end and s["template"] is not None), None)
        possible = [(i, s) for i, s in instrumentals if i not in used and
                    (prev is None or i > prev["template"]) and
                    (nxt is None or (prev is not None and nxt["template"] <= prev["template"])
                     or i < nxt["template"])]
        # Without lyric evidence an instrumental chart still remains readable.
        if not lyrics and templates:
            possible = list(enumerate(templates))
        parts = possible or [(None, {"label": "Intro" if start == 0 else "Instrumental passage",
                                    "rows": [], "repeat": 1})]
        weights = [max(1, sum(len(r["anchors"]) * r.get("repeat", 1) for r in s["rows"]) * s.get("repeat", 1)) for _, s in parts]
        total, cursor = sum(weights), start
        for (idx, template), weight in zip(parts, weights):
            stop = cursor + (end - start) * weight / total
            s = {"label": template["label"], "kind": "instrumental", "template": idx,
                 "start": cursor, "end": stop, "rows": copy.deepcopy(template["rows"]),
                 "repeat": template.get("repeat", 1), "confidence": "approximate"}
            if idx is not None:
                used.add(idx)
            sections.append(s)
            cursor = stop
    sections.sort(key=lambda s: s["start"])
    if not lyrics and not templates and (job.get("lyrics") or {}).get("plain"):
        sections[0]["label"] = "Untimed lyrics"
        sections[0]["kind"] = "vocal"
        sections[0]["rows"] = [{"text": line, "anchors": [], "repeat": 1}
                                for line in job["lyrics"]["plain"].splitlines() if line.strip()]
    events = []
    for index, section in enumerate(sections):
        section["id"] = "section-" + str(index)
        seq = []
        for row in section["rows"]:
            seq.extend(([a["symbol"] for a in row.get("anchors", [])] or row.get("progression", [])) * row.get("repeat", 1))
        window = [c for c in detected if section["start"] <= float(c["start"]) < section["end"]]
        if not seq:
            # Preserve recording evidence as explicitly estimated harmony.
            seq = [c["chord"] for c in window]
            section["evidence"] = "detected" if seq else "unknown"
        else:
            section["evidence"] = "chart"
        section["progression"] = seq
        # Only exact ordered matches borrow measured times. Never spread
        # unmatched symbols to pretend to know individual chord timing.
        cursor = 0
        matched = []
        for symbol in seq * section.get("repeat", 1):
            found = next((j for j in range(cursor, len(window)) if window[j]["chord"] == symbol), None)
            if found is None:
                matched = []
                break
            matched.append(window[found]); cursor = found + 1
        section["event_timing"] = "detected" if matched else "unresolved"
        for c in matched:
            start = max(section["start"], float(c["start"]))
            end = min(section["end"], float(c["end"]))
            if end > start:
                events.append({"start": round(start, 3), "end": round(end, 3), "chord": c["chord"]})
    # Keep unlocated source sections available for manual assignment rather
    # than silently dropping chart content or forcing it into another passage.
    doc = {"schema": SCHEMA, "generator": GENERATOR, "duration": duration,
           "sections": sections, "templates": templates,
           "source_hash": fingerprint(templates), "lyrics_hash": fingerprint(job.get("lyrics", {}))}
    doc["revision"] = fingerprint(doc)
    return doc, events


def validate_document(doc):
    if doc.get("schema") != SCHEMA or not doc.get("sections"):
        raise ValueError("No usable song passages were generated")
    end = 0
    for section in doc["sections"]:
        a, b = section["start"], section["end"]
        if not all(math.isfinite(x) for x in (a, b)) or a < end - .001 or b <= a or b > doc["duration"] + .001:
            raise ValueError("Overlapping or invalid section boundaries")
        end = b
    return doc
