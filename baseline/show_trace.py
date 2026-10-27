"""Print a readable summary of the latest (or given) trace file.

Usage:
  python show_trace.py                 # latest trace in traces/
  python show_trace.py traces/xxx.jsonl
"""
import json
import sys
from pathlib import Path

path = Path(sys.argv[1]) if len(sys.argv) > 1 else max(
    (Path(__file__).parent / "traces").glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
print(f"trace: {path}\n")
for line in path.read_text(encoding="utf-8").splitlines():
    e = json.loads(line)
    s, t = e["state"], f"{e['t']:7.2f}s"
    if s == "ACT":
        calls = e["llm"].get("tool_calls") or []
        what = ", ".join(f"{c['function']['name']}({json.dumps(c['function'].get('arguments'))})" for c in calls)
        print(f"{t}  ACT        LLM -> {what or repr(e['llm'].get('content', ''))[:80]}")
    elif s == "TOOL":
        print(f"{t}  TOOL       {e['name']} -> {json.dumps(e['result'], ensure_ascii=False)[:110]}")
    elif s == "FINAL_GATE":
        g = e["gate"]
        print(f"{t}  FINAL_GATE valid={g['valid']} errors={g.get('errors')}")
    elif "result" in e:
        r = e["result"]
        print(f"{t}  {s:<10} terms={r.get('terms')} llm_calls={r['llm_calls']} "
              f"tool_calls={r['tool_calls']} revisions={r['revisions']} e2e={r['e2e_s']}s "
              f"{r.get('reason', '')}")
    else:
        print(f"{t}  {s}")
