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

GENERATOR = "sections-1"
SCHEMA = 2
CH = re.compile(r"\[ch\](.*?)\[/ch\]", re.I)
HEADER = re.compile(r"^\s*\[?(lead break|guitar solo|intro|verse|chorus|pre[- ]?chorus|bridge|solo|outro|"
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
    """Retain headings, lyrics, columns and explicit repeats. Empty named
    sections reference preceding content; ambiguous instructions are retained.
    """
    lines = re.sub(r"\[/?tab\]", "", content, flags=re.I).replace("\r", "").split("\n")
    sections, current = [], None

    def section(label):
        repeat = re.search(r"\s+x\s*(\d+)\s*$", label, re.I)
        s = {"label": label[:repeat.start()].strip() if repeat else label, "rows": [],
             "repeat": max(1,min(32,int(repeat.group(1)) )) if repeat else 1}
        sections.append(s)
        return s

    i = 0
    while i < len(lines):
        line = lines[i]
        header = HEADER.match(line)
        repeat_ref = re.match(r"^\s*(?:repeat\s+)(chorus|verse|bridge|intro|solo)(.*)$", line, re.I)
        if header or repeat_ref:
            m = header or repeat_ref
            current = section((m.group(1) + m.group(2)).strip().title())
            i += 1
            continue
        if not line.strip():
            i += 1
            continue
        if current is None:
            current = section("Passage")
        anchors, plain, last = [], "", 0
        for m in CH.finditer(line):
            plain += line[last:m.start()]
            anchors.append({"symbol": transpose(m.group(1).strip()), "offset": len(plain)})
            plain += m.group(1)
            last = m.end()
        plain += line[last:]
        if anchors:
            words = ""
            if i + 1 < len(lines):
                nxt = lines[i + 1]
                if nxt.strip() and not CH.search(nxt) and not HEADER.match(nxt) and not re.match(r"\s*(repeat|x\s*\d)", nxt, re.I):
                    words = nxt
                    i += 1
            repeat = re.search(r"(?:\bx\s*|\brepeat\s+)(\d+)\b", plain, re.I)
            current["rows"].append({"text": words, "anchors": anchors,
                                    "repeat": min(32, int(repeat.group(1))) if repeat else 1})
        elif re.fullmatch(r"\s*(?:x\s*|repeat\s+)(\d+)\s*", line, re.I):
            current["repeat"] = min(32, int(re.search(r"\d+", line).group()))
        elif not re.match(r"\s*(capo|tuning|key|https?:|e\||b\||g\||d\||a\||E\|)", line):
            current["rows"].append({"text": line, "anchors": [], "repeat": 1})
        i += 1
    for i, s in enumerate(sections):
        s["id"] = "template-" + str(i)
        if not s["rows"]:
            base = re.sub(r"\d+|\bx\b", "", norm(s["label"])).strip()
            previous = next((p for p in reversed(sections[:i]) if p["rows"] and
                             re.sub(r"\d+|\bx\b", "", norm(p["label"])).strip() == base), None)
            if previous:
                s["rows"] = copy.deepcopy(previous["rows"])
                s["reference"] = previous["id"]
        s["kind"] = "vocal" if any(r["text"].strip() for r in s["rows"]) else "instrumental"
    return sections


def build_document(job, templates, detected, transpose=lambda x: x):
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
