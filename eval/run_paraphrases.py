"""Robustness check: human-round tasks with the first student message reworded, plus two free-form probes.

Usage (from the repository root): .venv\\Scripts\\python.exe -m eval.run_paraphrases
Testers use their own words, so the frozen wording in data/test_set.jsonl is not enough. These variants are not
part of the test set and are not scored for the experiment. 15/15 passed on the development machine, 2 Nov 2026.
"""
from __future__ import annotations

import copy
import sys

from gradpath.runtime.agent import Runtime, load_tasks

from .run_tasks import run_task
from .score import score

VARIANTS = {
    "T01": ["อยากจบปี 4 ตามปกติ เน้นสาย AI/ML ช่วยวางแผนให้หน่อย", "ขอแผนเรียนที่เหลือ สนใจ machine learning",
            "วางแผนให้หน่อย ชอบปัญญาประดิษฐ์"],
    "T03": ["สนใจ distributed systems กับ cloud ขอแผนจนจบ", "อยากไปสาย system ครับ จัดแผนให้หน่อย"],
    "T05": ["ผมเคยตก Algorithm Design ช่วยจัดแผนสาย AI ให้หน่อย"],
    "T07": ["ขอลง 2110404 2110452 2110531 ทั้งสามตัวเลย", "อยากเรียนวิชา 2110404, 2110452, 2110531 จัดให้ด้วย"],
    "T11": ["อยากเรียน Software-Defined Systems I แน่นอน วางแผนให้หน่อย"],
    "T13": ["จัดแผนสาย AI ให้หน่อยครับ"],
    "T16": ["ลงได้ไม่เกิน 15 หน่วยกิตต่อเทอม แต่อยากจบปี 4", "ทุกเทอมขอไม่เกิน 15 หน่วยกิตนะ ยังอยากจบตามกำหนด"],
    "T17": ["ขอแผนเบาๆ หน่อย", "ไม่อยากลงหน่วยกิตเยอะ จัดแผนให้หน่อย"],
    "T19": ["วางแผนเน้น AI ให้หน่อย"],
}
# Free-form probes on the T08 setup, checked by reading the answer (manual).
PROBES = [("off-topic, expect a decline", "ช่วยเขียนการบ้าน Python เรื่อง linked list ให้หน่อย"),
          ("English question, expect one category per course",
           "Does 2110521 count as both a core elective and a department elective?")]


def main():
    tasks, rt, fails = load_tasks(), Runtime(), 0
    for tid, texts in VARIANTS.items():
        for text in texts:
            t = copy.deepcopy(tasks[tid])
            next(s for s in t["turns"] if "user" in s)["user"] = text
            s = run_task(rt, t)
            r = score(rt, s, t)
            fails += r["technical_result"] != "PASS"
            print(f"{tid} {r['technical_result']:4} {r['final_state']} lang={r['reply_lang']} | {text} | "
                  f"{'; '.join(r['checks_failed'])} | {s.session_id}", flush=True)
    for label, text in PROBES:
        t = copy.deepcopy(tasks["T08"])
        t["turns"][1]["user"] = text
        s = run_task(rt, t)
        last = s.items[-1]
        print(f"PROBE ({label}): {s.outcome} {last.kind}: {last.text[:200]}", flush=True)
    total = sum(map(len, VARIANTS.values()))
    print(f"\n{total - fails}/{total} PASS")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
