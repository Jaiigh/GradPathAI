"""Language check (decision D11): the same 10 goal statements in Thai and in English, goal extraction compared.

Usage (from the repository root): .venv/bin/python -m eval.run_language [--repeat 2]
(Windows: .venv\\Scripts\\python.exe -m eval.run_language)
Each statement runs in a fresh y3-base session (entry 2567, next term 2569/2, normal end 2570/2) after the record is
confirmed. A statement is correct when the first answer is a goal card whose hard fields equal the expected ones
(fields not listed keep their defaults) and whose interests match the expected topic. Results go to
local/eval/language-<timestamp>.csv. These statements are not part of the test set.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import time

from gradpath import terms as T
from gradpath.runtime.agent import Runtime
from gradpath.runtime.prompts import THAI
from gradpath.runtime.session import LOCAL

PERSONA = "y3-base"
# id, Thai, English, expected hard fields, interest pattern (None: interests not checked)
CASES = [
    ("L01", "ช่วยวางแผนวิชาที่เหลือให้หน่อย ผมสนใจ machine learning",
     "Please plan my remaining courses. I'm interested in machine learning.",
     {}, r"machine|learning|\bml\b|\bai\b|artificial|แมชชีน|ปัญญา"),
    ("L02", "ขอลงไม่เกิน 18 หน่วยกิตต่อเทอมนะครับ",
     "I want at most 18 credits per term.",
     {"default_cap": 18}, None),
    ("L03", "ผมต้องลง 2110433 Computer Vision ให้ได้",
     "I must take 2110433 Computer Vision.",
     {"must_take": ["2110433"]}, None),
    ("L04", "ไม่เอา 2110479 นะ ไม่ชอบกราฟิกส์",
     "Please leave out 2110479, I don't like graphics.",
     {"avoid": ["2110479"]}, None),
    ("L05", "ขอแผนที่จบภายในเทอม 1 ปี 2570",
     "I want a plan that finishes by semester 1 of 2570.",
     {"horizon_end": "2570/1"}, None),
    ("L06", "เทอม 2570/1 ผมฝึกงาน ขอลงแค่ 12 หน่วยกิต",
     "In 2570/1 I have an internship, so only 12 credits that term.",
     {"caps": {"2570/1": 12}}, None),
    ("L07", "ลงซัมเมอร์ได้ แต่เทอมปกติไม่เกิน 15 หน่วยกิต",
     "Summer terms are fine, but no more than 15 credits in a regular term.",
     {"allow_summer": True, "default_cap": 15}, None),
    ("L08", "อยากเรียน 2110571 กับ 2110572 ทั้งสองตัว สนใจด้าน NLP",
     "I want to take both 2110571 and 2110572; I'm into NLP.",
     {"must_take": ["2110571", "2110572"]}, r"nlp|natural|language|ภาษา"),
    ("L09", "ไม่เกิน 20 หน่วยกิตต่อเทอม ไม่เอา 2110432 ชอบ data science",
     "At most 20 credits per term, no 2110432, and I like data science.",
     {"default_cap": 20, "avoid": ["2110432"]}, r"data|ข้อมูล"),
    ("L10", "จัดแผนสาย security ให้หน่อย ต้องได้ 2110413 และจบภายใน 2570/2",
     "Plan a security track for me; I must take 2110413 and finish by 2570/2.",
     {"must_take": ["2110413"]}, r"secur|ความปลอดภัย|ซีเคียว"),
]
DEFAULTS = {"caps": {}, "default_cap": None, "allow_summer": False, "must_take": [], "avoid": []}


def run_case(rt: Runtime, text: str, expected: dict, interest: str | None) -> dict:
    s = rt.create_session(persona=PERSONA)
    rt.record(s.session_id, [], True)
    t0 = time.time()
    s = rt.message(s.session_id, text)
    wall = round(time.time() - t0, 1)
    card = s.pending("goal")
    agent_texts = [i.text for i in s.items if i.role == "agent" and i.text]
    row = {"session_id": s.session_id, "outcome": s.outcome, "wall_s": wall, "answer": "goal_card" if card else
           next((i.kind for i in reversed(s.items) if i.role in ("agent", "system")), "none"),
           "reply_lang": ("th" if THAI.search(agent_texts[-1]) else "en") if agent_texts else None}
    errors = []
    if card is None:
        errors.append(f"no goal card ({row['answer']})")
    else:
        goal = card.data["goal"]
        want = {**DEFAULTS, "horizon_end": T.end_of_year4(s.student.entry_year), **expected}
        for field, value in want.items():
            got = goal.get(field)
            if isinstance(value, list):
                got, value = sorted(got or []), sorted(value)
            if got != value:
                errors.append(f"{field}: got {got!r}, want {value!r}")
        if interest and not any(re.search(interest, i, re.I) for i in goal.get("interests", [])):
            errors.append(f"interests {goal.get('interests')!r} do not match {interest!r}")
        row["goal"] = {k: v for k, v in goal.items() if v not in (None, [], {}, False)}
    row["errors"] = "; ".join(errors)
    row["correct"] = not errors
    return row


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--cases", default="", help="comma-separated case IDs, e.g. L01,L07")
    args = ap.parse_args(argv)
    ids = [c for c in args.cases.split(",") if c]
    rt, rows = Runtime(), []
    for rep in range(args.repeat):
        for cid, th, en, expected, interest in CASES:
            if ids and cid not in ids:
                continue
            for lang, text in (("th", th), ("en", en)):
                r = run_case(rt, text, expected, interest)
                r.update({"case": cid, "lang": lang, "repeat": rep + 1, "text": text,
                          "lang_ok": r["reply_lang"] in (None, lang)})
                rows.append(r)
                print(f"{cid} {lang} {'OK  ' if r['correct'] else 'MISS'} {r['wall_s']:5.1f}s {r['answer']}"
                      f"{' | ' + r['errors'] if r['errors'] else ''}", flush=True)
    print()
    for lang in ("th", "en"):
        sub = [r for r in rows if r["lang"] == lang]
        if sub:
            times = sorted(r["wall_s"] for r in sub)
            print(f"{lang}: {sum(r['correct'] for r in sub)}/{len(sub)} correct, reply language right "
                  f"{sum(r['lang_ok'] for r in sub)}/{len(sub)}, turn median {times[len(times) // 2]} s, "
                  f"max {times[-1]} s")
    out_dir = LOCAL / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"language-{time.strftime('%Y%m%d-%H%M%S')}.csv"
    cols = ["case", "lang", "repeat", "correct", "errors", "answer", "outcome", "reply_lang", "lang_ok", "wall_s",
            "text", "goal", "session_id"]
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"results: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
