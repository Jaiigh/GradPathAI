# GradPath

GradPath is a study-plan agent being built for Computer Engineering students. The target
system reads a transcript PDF, asks for missing goals, plans with a constraint solver, and
checks every plan at a mandatory final gate before showing it. Everything runs locally.

The repository currently has two separate parts:

- `src/` - a React prototype of the student interface. It shows synthetic data in the credit
  summary, does not parse or transmit the selected file, and is not connected to the agent yet.
- `baseline/` - a Python baseline agent (Ollama tool calling + OR-Tools CP-SAT) that runs one
  synthetic case end to end. Its results are the evidence for pitch v9 slides 11, 16 and 17.

Neither part is academic advice or a production transcript parser.

## Status (2 November 2026)

- Working on synthetic data: agent state machine, `audit`, keyword retrieval, CP-SAT planner,
  mandatory final gate, tool allowlist. Results and caveats: `baseline/results/slide_ready.md`.
- Not built yet: transcript PDF ingestion, a verified CP 2566 rule snapshot, interactive
  CLARIFY/consent, the connection between the React UI and the agent, the 20-task evaluation
  set, automated tests.
- Scope change after the v9 presentation: plans must run to the end of Year 4 (up to 8
  regular terms) instead of covering only the next two terms.

## Run the React prototype

```powershell
pnpm install
pnpm dev
```

Then open the local URL printed by Vite (normally `http://localhost:5173`). If `pnpm` is not
installed globally, `corepack pnpm install` and `corepack pnpm dev` use the version pinned in
`package.json`.

The equivalent commands also work if you prefer another package manager:

```powershell
npm install
npm run dev
```

```powershell
yarn
yarn dev
```

## Build

```powershell
pnpm build
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
