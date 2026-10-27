"""GradPath baseline agent: one case, end to end, through Ollama tool calling.

States: VERIFY_INPUT -> CLARIFY -> ACT (tool loop) -> FINAL_GATE -> DONE
        any -> WAIT_USER (here: reported as NEED_INFO, baseline is non-interactive)
        budget / timeout / UNKNOWN -> STOP_UNVERIFIED

Usage:
  python agent.py --model qwen3:8b
  python agent.py --model qwen3:4b
  python agent.py --mock            # offline smoke test, no Ollama needed
"""
from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from tools import TOOL_SCHEMAS, Context, execute, solve_plan, validate_plan

HERE = Path(__file__).parent
BUDGET = {"max_tool_calls": 8, "max_revisions": 2, "max_seconds": 120}
OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 8192, "num_predict": 1200}

SYSTEM = """You are GradPath, a study-plan agent for Computer Engineering students.
The student record, goal and curriculum snapshot are already bound by the runtime; you cannot change them.
Work only through tools:
1. audit - see what is missing.
2. retrieve_courses - map the student's interests to course IDs (cite source_id).
3. solve_plan - pass the preferred course IDs; the planner enforces all hard rules.
4. submit_final - submit the planner's terms exactly, with a 1-3 sentence explanation citing source IDs.
If solve_plan returns INFEASIBLE, submit_final with status "blocker", empty terms, and explain the scoped conflict.
Never invent course IDs. Do not answer in plain text; always call a tool."""


# ---------------------------------------------------------------- LLM clients
class OllamaLLM:
    def __init__(self, model: str, host: str = "http://localhost:11434"):
        self.model, self.host, self.use_think = model, host.rstrip("/"), True

    def chat(self, messages: list[dict]) -> tuple[dict, dict]:
        body = {"model": self.model, "messages": messages, "tools": TOOL_SCHEMAS,
                "stream": False, "options": OPTIONS, "keep_alive": "10m"}
        if self.use_think:
            body["think"] = False
        req = urllib.request.Request(f"{self.host}/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=BUDGET["max_seconds"]) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            if self.use_think and e.code == 400:      # older Ollama without `think`
                self.use_think = False
                return self.chat(messages)
            raise
        stats = {k: data.get(k) for k in ("total_duration", "load_duration", "prompt_eval_count",
                                          "prompt_eval_duration", "eval_count", "eval_duration")}
        return data["message"], stats


class MockLLM:
    """Scripted 'model' for an offline smoke test of the runtime, tools and gate."""
    model = "mock"

    def __init__(self):
        self.script = [
            ("audit", {}),
            ("retrieve_courses", {"query": "AI"}),
            ("solve_plan", {"preferred_course_ids": ["E202"]}),
            ("submit_final", {"status": "plan", "terms": [["E202"], ["C102"]],      # wrong order on purpose
                              "explanation": "AI course first."}),
            ("submit_final", {"status": "plan", "terms": [["C102"], ["E202"]],
                              "explanation": "C102 is required and is the prerequisite of E202 "
                                             "(synthetic-v1:E202), which matches the AI interest."}),
        ]

    def chat(self, messages):
        name, args = self.script.pop(0)
        return {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": name, "arguments": args}}]}, {}


# ---------------------------------------------------------------- runtime
def run_case(llm, case: dict, ctx: Context, trace_path: Path) -> dict:
    t0 = time.perf_counter()
    trace = open(trace_path, "w", encoding="utf-8")
    counters = {"llm_calls": 0, "tool_calls": 0, "revisions": 0, "llm_s": 0.0, "tool_s": 0.0}

    def log(state, **kw):
        trace.write(json.dumps({"t": round(time.perf_counter() - t0, 3), "state": state, **kw},
                               ensure_ascii=False) + "\n")

    def finish(state, **kw):
        res = {"final_state": state, **counters, "e2e_s": round(time.perf_counter() - t0, 2), **kw}
        log(state, result=res); trace.close()
        return res

    # VERIFY_INPUT
    unknown = [c for c in ctx.completed if c not in ctx.courses]
    log("VERIFY_INPUT", completed=list(ctx.completed), unknown_ids=unknown)
    if unknown:
        return finish("NEED_INFO", reason=f"transcript course IDs not in snapshot: {unknown}")
    # CLARIFY (baseline goal is pre-structured; check it is complete)
    g = ctx.goal
    missing = [k for k in ("terms",) if not g.get(k)] + \
              [f"cap for {t.get('label')}" for t in g.get("terms", []) if "cap" not in t]
    log("CLARIFY", goal=g, missing=missing)
    if missing:
        return finish("NEED_INFO", reason=f"goal incomplete: {missing}")

    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"{case['request']}\n\nPlanning terms: "
                 + ", ".join(f"{t['label']} (cap {t['cap']} credits)" for t in g["terms"])}]
    nudged = False
    while True:  # ACT
        if time.perf_counter() - t0 > BUDGET["max_seconds"]:
            return finish("STOP_UNVERIFIED", reason="wall-clock budget exceeded")
        ts = time.perf_counter()
        msg, stats = llm.chat(messages)
        counters["llm_calls"] += 1; counters["llm_s"] += time.perf_counter() - ts
        log("ACT", llm=msg, stats=stats)
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            if nudged:
                return finish("STOP_UNVERIFIED", reason="model answered without a tool call twice")
            nudged = True
            messages.append({"role": "user", "content": "Call a tool or submit_final. Do not answer in text."})
            continue
        for call in calls:
            name = call["function"]["name"]
            args = call["function"].get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"_unparsed": args}
            if name == "submit_final":
                # FINAL_GATE: runtime always checks the exact submitted output
                status, terms = args.get("status"), args.get("terms") or []
                if status == "blocker":
                    check = solve_plan(ctx, [])            # blocker must be witnessed by the solver
                    ok = check["status"] == "INFEASIBLE"
                    gate = {"valid": ok, "errors": [] if ok else ["solver found a feasible plan; not a blocker"]}
                else:
                    gate = validate_plan(ctx, terms)
                log("FINAL_GATE", submitted=args, gate=gate)
                if gate["valid"]:
                    return finish("DONE" if status == "plan" else "EVIDENCED_BLOCKER",
                                  status=status, terms=terms, explanation=args.get("explanation", ""),
                                  plan_hash=gate.get("plan_hash"))
                counters["revisions"] += 1
                if counters["revisions"] > BUDGET["max_revisions"]:
                    return finish("STOP_UNVERIFIED", reason="revision budget exceeded", last_gate=gate)
                result = {"final_gate": "rejected", "errors": gate["errors"],
                          "instruction": "Fix these errors and call submit_final again."}
            else:
                counters["tool_calls"] += 1
                if counters["tool_calls"] > BUDGET["max_tool_calls"]:
                    return finish("STOP_UNVERIFIED", reason="tool-call budget exceeded")
                ts = time.perf_counter()
                result = execute(name, args, ctx)
                counters["tool_s"] += time.perf_counter() - ts
                log("TOOL", name=name, args=args, result=result)
                if name == "solve_plan" and result.get("status") == "UNKNOWN":
                    return finish("STOP_UNVERIFIED", reason=result["reason"])
            messages.append({"role": "tool", "tool_name": name,
                             "content": json.dumps(result, ensure_ascii=False)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3:8b")
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--case", default=str(HERE / "data/case_ai_cap3.json"))
    ap.add_argument("--rules", default=str(HERE / "data/rules_snapshot.json"))
    ap.add_argument("--transcript", default=str(HERE / "data/transcript_synthetic.csv"))
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()

    case = json.loads(Path(a.case).read_text(encoding="utf-8"))
    ctx = Context.load(a.rules, a.transcript, case["goal"])
    llm = MockLLM() if a.mock else OllamaLLM(a.model, a.host)
    (HERE / "traces").mkdir(exist_ok=True); (HERE / "results").mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    trace_path = HERE / "traces" / f"{case['case_id']}_{llm.model.replace(':', '-')}_{stamp}.jsonl"

    res = run_case(llm, case, ctx, trace_path)
    exp = case.get("expected", {})
    res["matches_expected"] = (res.get("status") == exp.get("status") and res.get("terms") == exp.get("terms"))

    print(json.dumps(res, indent=2, ensure_ascii=False))
    print(f"\ntrace: {trace_path}")
    out = HERE / "results" / "baseline_results.csv"
    new = not out.exists()
    with open(out, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "model", "case", "final_state", "matches_expected", "terms",
                        "llm_calls", "tool_calls", "revisions", "e2e_s", "llm_s", "tool_s"])
        w.writerow([stamp, llm.model, case["case_id"], res["final_state"], res["matches_expected"],
                    json.dumps(res.get("terms")), res["llm_calls"], res["tool_calls"], res["revisions"],
                    res["e2e_s"], round(res["llm_s"], 2), round(res["tool_s"], 3)])


if __name__ == "__main__":
    main()
