# GradPath

GradPath is a study-plan agent being built for Computer Engineering students. The target
system reads a transcript PDF, asks for missing goals, plans with a constraint solver, and
checks every plan at a mandatory final gate before showing it. Everything runs locally.

The repository has three parts:

- `gradpath/` - the backend: the CP 2566 rule snapshot, a multi-term CP-SAT planner, an
  independent validator, retrieval, the interactive agent runtime (state machine, goal and
  consent cards, final gate, budget, traces) and a FastAPI app bound to 127.0.0.1.
- `src/` - the React student interface (Thai), connected to the agent through the API.
- `baseline/` - the frozen pitch v9 baseline agent. Its results are the evidence for pitch v9
  slides 11, 16 and 17.

GradPath is not academic advice. The UAT build uses synthetic student personas, not real
transcripts.

Project documentation (requirements, architecture, decisions, plan, evaluation) is indexed
in `docs/README.md`.

## Status (2 November 2026)

- Working: the `cp2566-v0` snapshot built from public sources, planning every term to the end
  of Year 4, record review with NEED_INFO, goal and consent cards, evidenced blockers with
  solver-proven alternatives, fault injection for the UAT, traces and run records, and test
  set v1.1 (20 tasks) with an automatic runner.
- Not built yet: transcript PDF ingestion, experiment arms A and B, embeddings.

## Run GradPath

Prepare the environments once (Python 3.13, Node 20+ with corepack, Ollama with `qwen3:8b`);
`scripts\uat_setup.ps1` does the same on a fresh machine:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
corepack pnpm install
corepack pnpm build
ollama pull qwen3:8b
```

Start the server. It serves the built UI at `http://127.0.0.1:8000` and warms up the model:

```powershell
.venv\Scripts\python.exe -m gradpath.api
```

`http://127.0.0.1:8000/?operator` is the operator view, which starts a session from a
test-set task. For UI development, also run `corepack pnpm dev`; Vite proxies `/api` to the
server.

Tests, the test-set runner and the UAT machine check:

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m eval.run_tasks
.venv\Scripts\python.exe scripts\uat_check.py
```

## Run the Python baseline

The baseline is kept separately from the React app in `baseline/`. It needs Python 3.11 or
newer (re-checked with 3.13.5). From the repository root, prepare its local Python
environment once:

```powershell
py -3 -m venv baseline\.venv
baseline\.venv\Scripts\python.exe -m pip install -r baseline\requirements.txt
```

Run the offline smoke test first:

```powershell
baseline\.venv\Scripts\python.exe baseline\agent.py --mock
baseline\.venv\Scripts\python.exe baseline\show_trace.py
```

To reproduce the pitch measurements, install and start Ollama, download the two models,
then run the benchmark and end-to-end cases:

```powershell
ollama pull qwen3:4b
ollama pull qwen3:8b
baseline\.venv\Scripts\python.exe baseline\bench.py
baseline\.venv\Scripts\python.exe baseline\agent.py --model qwen3:8b
baseline\.venv\Scripts\python.exe baseline\agent.py --model qwen3:4b
baseline\.venv\Scripts\python.exe baseline\show_trace.py
```

Every `agent.py` run, including `--mock`, appends a row to
`baseline/results/baseline_results.csv` and writes a new trace to `baseline/traces/`. The
measured results, trace files and known caveats are summarized in
`baseline/results/slide_ready.md`. The baseline uses synthetic curriculum and transcript
fixtures; it does not evaluate the React interface or real PDF ingestion.
