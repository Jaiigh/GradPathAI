"""Fill the results table (columns of data/results_template.csv) from the UAT feedback and the session traces.

Human rows: data/uat_feedback_v1.1.csv (Q1, Q5, Q6 from the 4 Nov forms, as in the UAT report appendix) joined with
the UAT-day session of each task in local/sessions/ (the latest 4 Nov session of that task with a student message, or
the only one). Each human session is also scored against its scripted task; testers typed their own words, so a
FAIL there means "the tester took a different path", which the notes column explains.
Technical rows: one scripted run CSV from eval.run_tasks (default: the newest arm C file in local/eval/).

Usage: .venv/bin/python -m eval.fill_results [--tech local/eval/<file>.csv] [--out data/results_v1.1.csv]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from gradpath.runtime.agent import Runtime, load_tasks
from gradpath.runtime.session import LOCAL, Store
from gradpath.snapshot import ROOT

from .score import score

UAT_DAY = "20261104-"
COLUMNS = (ROOT / "data" / "results_template.csv").read_text(encoding="utf-8").strip().split(",")


class NoLLM:
    model = "none"

    def chat(self, *a, **k):
        raise RuntimeError("fill_results never calls the model")


def uat_session(store: Store, task_id: str):
    found = []
    for path in sorted(store.sessions_dir.glob(f"{UAT_DAY}*.json")):
        s = store.load(path.stem)
        if s.task_id == task_id:
            found.append(s)
    with_msgs = [s for s in found if any(i.role == "student" for i in s.items)]
    return (with_msgs or found or [None])[-1], len(found)


def human_rows(rt: Runtime) -> list[dict]:
    tasks = load_tasks()
    rows = []
    feedback = list(csv.DictReader(open(ROOT / "data" / "uat_feedback_v1.1.csv", encoding="utf-8")))
    for f in feedback:
        s, attempts = uat_session(rt.store, f["task_id"])
        row = {c: "" for c in COLUMNS}
        row.update(round=f["round"], participant_id=f["participant_id"], task_id=f["task_id"], mode="human",
                   q1_accepted=f["q1_accepted"], q1_reason=f["q1_reason"], q5_clarity=f["q5_clarity"],
                   q6_helpfulness=f["q6_helpfulness"])
        if s is None:
            row["notes"] = "no session found"
            rows.append(row)
            continue
        rt.sessions[s.session_id] = s
        r = score(rt, s, tasks[f["task_id"]])
        plan = s.candidates.get(s.final_plan_id) if s.final_plan_id else None
        said = " / ".join(i.text for i in s.items if i.role == "student")
        row.update(run_id=s.session_id, build_id=s.run_record.get("git_commit"),
                   model_digest=s.run_record.get("digest"), test_set_sha256=s.run_record.get("test_set_sha256"),
                   snapshot_hash=s.snapshot_hash, record_version=s.student.record_version,
                   goal_version=s.goal.goal_version if s.goal else "", final_state=s.outcome or "",
                   plan_id=s.final_plan_id or "", plan_hash=plan.plan_hash if plan else "",
                   gate_valid="yes" if s.final_plan_id else "", checks_failed="; ".join(r["checks_failed"]),
                   technical_result=r["technical_result"], processing_s=r["processing_s"],
                   tool_calls=r["tool_calls"], revisions=r["revisions"],
                   trace_path=str(rt.store.trace_path(s.session_id).relative_to(ROOT)),
                   notes=f"{attempts} UAT-day session(s) for this task; tester typed: {said or '(nothing)'}; "
                         f"outcomes {s.outcomes}")
        rows.append(row)
    return rows


def tech_rows(path: Path) -> list[dict]:
    rows = []
    for t in csv.DictReader(open(path, encoding="utf-8")):
        row = {c: "" for c in COLUMNS}
        row.update({k: t[k] for k in COLUMNS if k in t})
        row.update(round="tech", participant_id="scripted", mode=f"scripted arm {t.get('arm', 'C')}",
                   gate_valid="yes" if t.get("plan_id") else "",
                   trace_path=str(Path(t["trace_path"]).relative_to(ROOT)) if t.get("trace_path") else "",
                   notes=f"repeat {t.get('repeat')}; max turn {t.get('max_turn_s')} s; manual: {t.get('manual') or '-'}")
        rows.append(row)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tech", default="")
    ap.add_argument("--out", default=str(ROOT / "data" / "results_v1.1.csv"))
    args = ap.parse_args(argv)
    rt = Runtime(llm=NoLLM(), store=Store(LOCAL))
    tech = Path(args.tech) if args.tech else max((LOCAL / "eval").glob("*-armC.csv"), default=None)
    rows = human_rows(rt) + (tech_rows(tech) if tech else [])
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    human = [r for r in rows if r["mode"] == "human"]
    print(f"{len(human)} human rows ({sum(r['q1_accepted'] == 'yes' for r in human)} accepted), "
          f"{len(rows) - len(human)} technical rows from {tech}; written to {args.out}")
    print(json.dumps({r["task_id"]: [r["final_state"], r["technical_result"]] for r in human}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
