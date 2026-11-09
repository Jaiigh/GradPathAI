"""Run test-set tasks end to end against the live agent with a scripted student, then score them.

Usage (from the repository root):
  .venv\\Scripts\\python.exe -m eval.run_tasks                     # all 20 tasks
  .venv\\Scripts\\python.exe -m eval.run_tasks --tasks T01,T17 --repeat 2
  .venv/bin/python -m eval.run_tasks --arm A --repeat 2         # experiment arm A, B or C (default C)
Results go to local/eval/<timestamp>-arm<X>.csv (plus one session JSON and trace per run in local/).
The scripted student applies the task's steps in order; a goal or blocker card that no step answers gets the
task's `defaults` (data/test_set.jsonl, scripts/make_test_set.py).
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

from gradpath.runtime.agent import Runtime, load_tasks
from gradpath.runtime.session import LOCAL

from .score import score

MAX_STEPS = 16


def run_task(rt: Runtime, task: dict):
    s = rt.create_session(task_id=task["id"])
    steps = list(task["turns"])
    defaults = task.get("defaults", {})
    for _ in range(MAX_STEPS):
        card = s.pending("goal") or s.pending("blocker")
        nxt = steps[0] if steps else None
        dec = nxt.get("decision") if nxt else None
        if dec and dec["card"] == "record":
            steps.pop(0)
            if not s.student.confirmed:
                rt.record(s.session_id, dec.get("resolve", []), dec.get("confirm", True))
        elif card and dec and dec["card"] == card.kind:
            steps.pop(0)
            if card.kind == "goal":
                rt.goal_decision(s.session_id, card.card_id, dec["approve"])
            else:
                rt.blocker_decision(s.session_id, card.card_id, choose=dec.get("choose"), decline=dec.get("decline", False))
        elif card:
            policy = defaults.get(f"{card.kind}_card", "decline")
            if card.kind == "goal":
                rt.goal_decision(s.session_id, card.card_id, policy == "approve")
            else:
                rt.blocker_decision(s.session_id, card.card_id, decline=True)
        elif nxt and "user" in nxt:
            steps.pop(0)
            rt.message(s.session_id, nxt["user"])
        elif dec:
            steps.pop(0)      # the card this step answers never appeared; the score shows the consequence
        elif s.queued and not s.student.confirmed and not s.student.unresolved:
            rt.record(s.session_id, [], True)
        else:
            break
    return s


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--arm", default="C", choices=["A", "B", "C"], help="experiment arm (docs/evaluation.md)")
    args = ap.parse_args(argv)
    tasks = load_tasks()
    ids = [t for t in args.tasks.split(",") if t] or list(tasks)
    rt = Runtime(arm=args.arm)
    out_dir = LOCAL / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{time.strftime('%Y%m%d-%H%M%S')}-arm{args.arm}.csv"
    rows = []
    for rep in range(args.repeat):
        for tid in ids:
            t0 = time.time()
            s = run_task(rt, tasks[tid])
            r = score(rt, s, tasks[tid])
            r.update({"arm": args.arm, "run_id": s.session_id, "repeat": rep + 1, "wall_s": round(time.time() - t0, 1),
                      "build_id": s.run_record.get("git_commit"), "model_digest": s.run_record.get("digest"),
                      "test_set_sha256": s.run_record.get("test_set_sha256"), "snapshot_hash": s.snapshot_hash,
                      "trace_path": str(rt.store.trace_path(s.session_id))})
            rows.append(r)
            print(f"{tid} rep{rep + 1}: {r['technical_result']:4} state={r['final_state']} "
                  f"turn_max={r['max_turn_s']}s tools={r['tool_calls']} lang={r['reply_lang']} "
                  f"{'; '.join(r['checks_failed'])}", flush=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: "; ".join(v) if isinstance(v, list) else v for k, v in r.items()})
    passed = sum(r["technical_result"] == "PASS" for r in rows)
    print(f"\n{passed}/{len(rows)} PASS; results in {out}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
