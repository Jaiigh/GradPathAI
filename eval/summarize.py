"""Compare experiment arms from eval.run_tasks CSVs (docs/evaluation.md, "Experiment").

Usage: .venv/bin/python -m eval.summarize local/eval/<A>.csv local/eval/<B>.csv local/eval/<C>.csv [--md out.md]
Prints one Markdown table per view: overall and per scenario type, per task, and behaviour/latency metrics.
"T08 manual" is the manual check of T08 (the answer must say a course counts toward one category only); a run
that answers with a plan instead of the answer passes the script but fails the manual check.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

from gradpath.runtime.agent import load_tasks
from gradpath.runtime.session import LOCAL, Store

ONE_CATEGORY = ("one category", "หมวดเดียว", "เพียงหมวด", "only one", "exactly one", "ได้เพียงหนึ่ง", "ไม่สามารถนับเป็นทั้ง",
                "อย่างใดอย่างหนึ่ง", "cannot count", "not both", "one of them")


def t08_manual(run_id: str) -> bool:
    s = Store(LOCAL).load(run_id)
    texts = [i.text for i in s.items if i.role == "agent" and i.kind in ("text", "decline")]
    return bool(texts) and any(k in t for t in texts for k in ONE_CATEGORY) and not s.final_plan_id


def turn_times(rows: list[dict]) -> dict[str, list[float]]:
    """Per-turn durations by how the turn ended (requirements Q3); STOP turns are left out."""
    out = {"short": [], "plan": []}
    store = Store(LOCAL)
    for r in rows:
        for t in store.load(r["run_id"]).turns:
            if t.ended is None or t.outcome in (None, "STOP_UNVERIFIED"):
                continue
            out["plan" if t.outcome in ("DONE", "EVIDENCED_BLOCKER") else "short"].append(t.ended - t.started)
    return out


def load(path: Path) -> list[dict]:
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    for r in rows:
        r["pass"] = r["technical_result"] == "PASS"
        if r["task_id"] == "T08":
            r["manual_ok"] = t08_manual(r["run_id"])
            r["pass_manual"] = r["pass"] and r["manual_ok"]
        else:
            r["pass_manual"] = r["pass"]
    return rows


def pct(n, d):
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "-"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--md", default="")
    args = ap.parse_args(argv)
    tasks = load_tasks()
    arms = {}
    for f in args.files:
        rows = load(Path(f))
        arms[rows[0].get("arm", Path(f).stem)] = rows
    names = sorted(arms)
    out = []
    reps = {a: max(int(r["repeat"]) for r in rows) for a, rows in arms.items()}
    out.append("| Metric | " + " | ".join(f"Arm {a}" for a in names) + " |")
    out.append("|---|" + "---|" * len(names))
    out.append("| Runs (tasks x repeats) | " + " | ".join(f"20 x {reps[a]}" for a in names) + " |")
    out.append("| Script checks passed | " + " | ".join(pct(sum(r["pass"] for r in arms[a]), len(arms[a])) for a in names) + " |")
    out.append("| Passed incl. T08 manual check | " + " | ".join(pct(sum(r["pass_manual"] for r in arms[a]), len(arms[a])) for a in names) + " |")
    out.append("| Tasks passed in every repeat | " + " | ".join(
        f"{sum(all(r['pass_manual'] for r in arms[a] if r['task_id'] == t) for t in tasks)}/20" for a in names) + " |")
    for typ in ("happy", "edge", "failure", "safety", "ambiguous"):
        ids = {t for t, v in tasks.items() if v["type"] == typ}
        out.append(f"| - {typ} | " + " | ".join(
            pct(sum(r["pass_manual"] for r in arms[a] if r["task_id"] in ids), sum(r["task_id"] in ids for r in arms[a]))
            for a in names) + " |")
    for label, key in (("Mean tool calls per task", "tool_calls"), ("Mean LLM calls per task", "llm_calls"),
                       ("Mean revisions per task", "revisions")):
        out.append(f"| {label} | " + " | ".join(f"{statistics.mean(float(r[key] or 0) for r in arms[a]):.1f}"
                                               for a in names) + " |")
    for label, key in (("Median longest turn (s)", "max_turn_s"), ("Mean processing per task (s)", "processing_s")):
        f = statistics.median if "Median" in label else statistics.mean
        out.append(f"| {label} | " + " | ".join(f"{f(float(r[key]) for r in arms[a]):.1f}" for a in names) + " |")
    out.append("| Longest turn (s) | " + " | ".join(f"{max(float(r['max_turn_s']) for r in arms[a]):.1f}" for a in names) + " |")
    turns = {a: turn_times(arms[a]) for a in names}
    for label, kind, limit in (("Turns ending in a card, question or reply", "short", 15),
                               ("Turns ending in a plan or blocker", "plan", 40)):
        out.append(f"| {label}: within {limit} s (max) | " + " | ".join(
            f"{sum(t <= limit for t in turns[a][kind])}/{len(turns[a][kind])} ({max(turns[a][kind], default=0):.1f} s)"
            for a in names) + " |")
    out.append("| Unknown course IDs shown | " + " | ".join(
        str(sum("no_unknown_ids" in r["checks_failed"] for r in arms[a])) for a in names) + " |")
    out.append("| Reply language matches | " + " | ".join(
        pct(sum(r["lang_ok"] == "True" for r in arms[a]), len(arms[a])) for a in names) + " |")
    out.append("")
    out.append("| Task | Type | " + " | ".join(f"Arm {a}" for a in names) + " |")
    out.append("|---|---|" + "---|" * len(names))
    for t, v in tasks.items():
        cells = []
        for a in names:
            rs = [r for r in arms[a] if r["task_id"] == t]
            ok = sum(r["pass_manual"] for r in rs)
            states = sorted({r["final_state"] for r in rs})
            why = sorted({r["checks_failed"].split(":")[0] for r in rs if r["checks_failed"]} |
                         ({"manual"} if t == "T08" and not all(r["manual_ok"] for r in rs) else set()) |
                         ({"state"} if any(r["state_ok"] != "True" for r in rs) else set()))
            cells.append(f"{ok}/{len(rs)} {'/'.join(states)}" + (f" ({', '.join(why)})" if why else ""))
        out.append(f"| {t} | {v['type']} | " + " | ".join(cells) + " |")
    text = "\n".join(out)
    print(text)
    if args.md:
        Path(args.md).write_text(text + "\n", encoding="utf-8")
    print(json.dumps({a: sum(r["pass_manual"] for r in arms[a]) for a in names}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
