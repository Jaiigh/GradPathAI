"""Print a session trace compactly: python -m eval.show_trace <session_id or trace path> [--full]."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from gradpath.runtime.session import LOCAL


def main():
    arg = sys.argv[1]
    full = "--full" in sys.argv
    path = Path(arg) if arg.endswith(".jsonl") else LOCAL / "traces" / f"{arg}.jsonl"
    width = 10_000 if full else 220
    for line in path.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        ev = e.pop("event")
        if ev == "llm":
            calls = [f"{c['function']['name']}({json.dumps(c['function'].get('arguments'), ensure_ascii=False)})"
                     for c in e.get("tool_calls") or []]
            stats = e.get("stats") or {}
            print(f"  LLM[{stats.get('wall_s')}s] {e.get('content', '')[:width]!r} -> {'; '.join(calls)[:width]}")
        elif ev == "tool":
            print(f"    {e['name']} => {json.dumps(e['observation'], ensure_ascii=False)[:width]}")
        elif ev == "turn":
            print(f"  TURN {e['turn']}: {e['outcome']} llm={e['llm_calls']} tools={e['tool_calls']} "
                  f"rev={e['revisions']} {round((e['ended'] or 0) - e['started'], 2)}s")
        elif ev == "session_created":
            r = e["run_record"]
            print(f"SESSION {r['session_id']} task={r['task_id']} persona={r['persona']} fault={r['fault']} "
                  f"model={r['model']}@{r['digest']} commit={r['git_commit']}")
        else:
            print(f"{ev.upper()} {json.dumps(e, ensure_ascii=False)[:width]}")


if __name__ == "__main__":
    main()
