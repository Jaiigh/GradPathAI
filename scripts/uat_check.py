"""UAT machine check (docs/dev-setup.md, "UAT machine"): run on the UAT laptop before each round.

Usage (from the repository root): .venv\\Scripts\\python.exe scripts\\uat_check.py [--tasks T01,T09,T17] [--quick]
Checks Ollama on 127.0.0.1, the qwen3:8b digest, GPU, model warm-up, the built UI, the frozen test set and
snapshot hashes, then runs the given tasks end to end and reports the turn times against the 120 s budget.
Exit code 0 only when every check passes.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gradpath.runtime import llm  # noqa: E402
from gradpath.runtime.agent import BUDGET, Runtime, _gpu, load_tasks  # noqa: E402
from gradpath.snapshot import load  # noqa: E402

ROUND_TASKS = "T01,T05,T09,T13,T17,T03,T07,T11,T16,T19"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default=ROUND_TASKS)
    ap.add_argument("--quick", action="store_true", help="skip the task runs")
    args = ap.parse_args()
    results = []

    def check(name, ok, detail=""):
        results.append(ok)
        print(f"[{'PASS' if ok else 'FAIL'}] {name}{': ' + str(detail) if detail else ''}", flush=True)

    info = llm.model_info()
    check("Ollama reachable at 127.0.0.1:11434", info["ollama_version"] is not None, info["ollama_version"])
    check(f"model {llm.MODEL} installed", bool(info["digest"]), info["digest"])
    check("GPU", _gpu() != "none", _gpu())
    try:
        check("model warm-up", True, f"{llm.warm_up()} s (cold start can take over a minute)")
        t = llm.warm_up()
        check("warm call under 5 s", t < 5, f"{t} s")
    except llm.ModelUnavailable as e:
        check("model warm-up", False, e)
    check("UI built (dist/index.html)", (ROOT / "dist" / "index.html").exists(), "run: corepack pnpm build")
    ts = ROOT / "data" / "test_set.jsonl"
    check("test set", ts.exists(), f"{len(load_tasks())} tasks, SHA-256 {hashlib.sha256(ts.read_bytes()).hexdigest()[:16]}")
    check("snapshot", True, f"cp2566-v0 content_hash {load().content_hash}")
    if not args.quick:
        from eval.run_tasks import run_task
        from eval.score import score
        rt = Runtime()
        tasks = load_tasks()
        for tid in [t for t in args.tasks.split(",") if t]:
            t0 = time.time()
            s = run_task(rt, tasks[tid])
            r = score(rt, s, tasks[tid])
            ok = r["technical_result"] == "PASS" and r["max_turn_s"] <= BUDGET["seconds"]
            check(f"task {tid}", ok, f"{r['final_state']}, longest turn {r['max_turn_s']} s, wall {time.time() - t0:.1f} s"
                  + (f", failed: {'; '.join(r['checks_failed'])}" if r["checks_failed"] else ""))
    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
