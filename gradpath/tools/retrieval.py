"""retrieve_courses tool: BM25 over the snapshot's courses, categories, unlisted options and regulations (D6).

Latin text is split into words; Thai text, which has no spaces, into character bigrams. A small topic table
expands common abbreviations ("AI", "ML") into the words used in course titles. Course descriptions, when a
snapshot has them, are indexed as data: their text is returned as a snippet and never followed as instructions.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from ..snapshot import Snapshot

_LATIN = re.compile(r"[a-z0-9]+")
_THAI = re.compile(r"[฀-๿]+")
K1, B = 1.5, 0.75
RELATIVE = 0.5

TOPICS = {
    "ai": "artificial intelligence neural network pattern recognition natural language",
    "ml": "machine learning neural network pattern recognition data mining",
    "machine learning": "neural network pattern recognition data mining artificial intelligence",
    "nlp": "natural language processing",
    "cv": "computer vision digital imaging",
    "systems": "parallel distributed systems architecture large scale computing cloud unix linux fault tolerant",
    "system": "parallel distributed systems architecture large scale computing cloud unix linux fault tolerant",
    "data": "data science mining warehouse engineering",
    "security": "computer security",
    "graphics": "computer graphics animation realtime",
    "hardware": "vlsi digital circuits architecture",
}
RULE_WORDS = {
    "max_credits_regular": "credit limit cap per regular semester term maximum load",
    "max_credits_summer": "credit limit cap per summer term maximum load",
    "overload": "credit limit exceed overload dean approval",
    "min_credits_regular": "minimum credits per regular term",
    "required_course_retake_grades": "retake required course failed grade",
    "elective_retake_rule": "retake elective failed grade",
}


def tokens(text: str) -> list[str]:
    text = text.lower()
    out = _LATIN.findall(text)
    for run in _THAI.findall(text):
        out += [run[i:i + 2] for i in range(max(1, len(run) - 1))]
    return out


@dataclass
class Passage:
    source_id: str
    course_id: str | None
    title: str
    text: str
    meta: dict


def passages(snap: Snapshot) -> list[Passage]:
    out = []
    for cid, c in snap.courses.items():
        title = f"{c['name_en']} / {c['name_th']}"
        desc = c.get("description") or ""
        out.append(Passage(f"course:{cid}", cid, title, desc,
                           {"credits": c["credits"], "kind": c["kind"], "categories": c["categories"],
                            "status": c["status"], "offered": c["offered"]["status"],
                            "prereqs": c["prereqs"]["status"]}))
    n = 0
    for cat in snap.data["categories"]:
        out.append(Passage(f"category:{cat['id']}", None, f"{cat['name_en']} / {cat['name_th']}",
                           f"category {cat['id']}, minimum {cat['min_credits']} credits",
                           {"min_credits": cat["min_credits"]}))
        for opt in cat.get("unlisted_options", []):
            n += 1
            out.append(Passage(f"unlisted:{n}", None, f"{opt['name_en']} / {opt.get('name_th', '')}".rstrip(" /"),
                               f"listed in category {cat['id']}; course code not published in the snapshot "
                               f"({opt['note']})", {"category": cat["id"], "status": opt["status"]}))
    for name, reg in snap.data["regulations"].items():
        out.append(Passage(f"rule:{name}", None, name.replace("_", " "),
                           f"{RULE_WORDS.get(name, '')}: value {reg['value']} ({reg['source']} "
                           f"{reg.get('location', '')})".strip(" :"),
                           {"status": reg["status"]}))
    return out


class Index:
    def __init__(self, snap: Snapshot):
        self.docs = passages(snap)
        self.tf = [Counter(tokens(f"{d.course_id or ''} {d.title} {d.text}")) for d in self.docs]
        self.lens = [sum(t.values()) for t in self.tf]
        self.avg = sum(self.lens) / len(self.lens)
        df = Counter(w for t in self.tf for w in t)
        n = len(self.docs)
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}

    def search(self, query: str, k: int = 6) -> list[tuple[float, Passage]]:
        q = query.lower()
        # Expand short topic queries only, so a specific title ("Software-Defined Systems I") keeps its own words.
        short = len(_LATIN.findall(q)) <= 3 and not _THAI.search(q)
        extra = " ".join(v for key, v in TOPICS.items() if short and re.search(rf"\b{re.escape(key)}\b", q))
        terms = tokens(f"{query} {extra}")
        scored = []
        for doc, tf, n in zip(self.docs, self.tf, self.lens):
            s = sum(self.idf.get(w, 0) * tf[w] * (K1 + 1) / (tf[w] + K1 * (1 - B + B * n / self.avg))
                    for w in set(terms) if w in tf)
            if doc.course_id and doc.course_id in query:
                s += 10
            if s > 0:
                scored.append((s, doc))
        scored.sort(key=lambda p: (-p[0], p[1].source_id))
        # Weak partial matches mislead more than they help: keep results within RELATIVE of the best score.
        return [p for p in scored[:k] if p[0] >= RELATIVE * scored[0][0]]


def retrieve(index: Index, query: str, k: int = 6) -> list[dict]:
    return [{"source_id": d.source_id, "course_id": d.course_id, "title": d.title,
             "snippet": d.text[:300], "score": round(s, 2), **d.meta} for s, d in index.search(query, k)]
