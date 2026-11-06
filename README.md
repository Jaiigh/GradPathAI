# GradPath

GradPath is a study-plan agent being built for Computer Engineering students. The target
system reads a CR60 grade-report PDF, asks for missing goals, plans with a constraint solver, and
checks every plan at a mandatory final gate before showing it. Everything runs locally.

The repository has three parts:

- `gradpath/` - the backend: the CP 2566 rule snapshot, a multi-term CP-SAT planner, an
  independent validator, retrieval, the interactive agent runtime (state machine, goal and
  consent cards, final gate, budget, traces) and a FastAPI app bound to 127.0.0.1.
- `src/` - the React student interface (Thai), connected to the agent through the API.
- `baseline/` - the frozen pitch v9 baseline agent. Its results are the evidence for pitch v9
  slides 11, 16 and 17.

GradPath is a planning aid, not official graduation certification. The default interface
accepts real CR60 PDFs; synthetic student personas remain in the operator/UAT view.

## Upload a grade report

Upload the complete, text-readable English Chulalongkorn CR60 / Student Grade Report PDF
(up to 10 MB and 20 pages). The importer reads all semesters, preserves every attempt and
leading-zero course code, and checks earned credits against the printed CG/CGX summaries.
Scanned, password-protected, incomplete and unsupported layouts are rejected with an explanation.

Review the extracted coursework, confirm the CP 2566 curriculum, admission year and planning
start term, and assign confirmed curriculum categories to earned courses outside the catalog.
An unknown category stays unresolved; the app does not guess that it is a free elective.
Unreadable grades and disagreements between report and catalog credits require review.
Credit-summary mismatches block confirmation. Report credits are retained when confirmed.
In-progress courses are not assumed passed; use the latest report of completed coursework.

The PDF is parsed locally without an LLM. The original lives in `local/uploads/`, academic
records in `local/sessions/`, and traces in `local/traces/` (all gitignored). Identity headers,
national IDs and birthdates are excluded from the extracted session data and model context.
Replacing a report replaces its entire coursework history, increments the record version,
and invalidates earlier plans and goals. PDF links point to the current report.

## Run on macOS

The Python backend and model both run on your machine. After installing Python 3.12 or 3.13,
Node 22.13+ (Node 24 recommended), and Ollama:

```bash
python3.12 -m venv .venv  # python3.13 also works
.venv/bin/python -m pip install -r requirements.txt
corepack pnpm install
corepack pnpm build
ollama pull qwen3:8b
.venv/bin/python -m gradpath.api
```

Keep Ollama running (the desktop app, or `ollama serve` in another terminal), then open
http://127.0.0.1:8000. For later launches, only Ollama and the last command are needed.
On macOS, `caffeinate -dims .venv/bin/python -m gradpath.api` prevents sleep during a demo.
Upload/review works even when the model is unavailable; conversational planning requires it.
The default model endpoint is `http://127.0.0.1:11434`; `GRADPATH_OLLAMA` can override it,
so retain the default for local-only operation. `GRADPATH_MODEL` defaults to `qwen3:8b`.

On an 8 GB Mac, use the smaller local model:

```bash
ollama pull qwen3:4b
GRADPATH_MODEL=qwen3:4b .venv/bin/python -m gradpath.api
```

On the tested M3 / 8 GB machine (7 Nov 2026), `qwen3:8b` timed out; `qwen3:4b` passed the
T01 end-to-end planning smoke test (goal turn 36 s, plan turn 89 s). This is one smoke test,
not a full evaluation of the smaller model, and does not meet the documented UAT latency targets.

Project documentation (requirements, architecture, decisions, plan, evaluation) is indexed
in `docs/README.md`.

## Status (7 November 2026)

- Working: the `cp2566-v0` snapshot built from public sources, planning every term to the end
  of Year 4, record review with NEED_INFO, goal and consent cards, evidenced blockers with
  solver-proven alternatives, fault injection for the UAT, traces and run records, and test
  set v1.1 (20 tasks) with an automatic runner.
- Working: text-based CR60 PDF upload, full coursework extraction, credit reconciliation,
  category/profile review, source-page links, and report replacement.
- Not built yet: scanned-PDF OCR, arbitrary transcript layouts, experiment arms A and B, embeddings.

## Run GradPath

Prepare the environments once (Python 3.12/3.13, Node 22.13+ with corepack, Ollama with `qwen3:8b`);
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

## GenEd requirement

The current default snapshot, `cp2566-gened-v1`, pools general education into **12 credits**
under **กลุ่มวิชาศึกษาทั่วไป GenEd**. Social science, humanities, interdisciplinary, and
science/mathematics credits no longer have separate minimums. Legacy category assignments
are combined automatically. Special-group courses and foreign languages remain separate;
the program total remains 138 credits. Existing uploaded-report sessions upgrade when
reopened and mark old plans stale. Frozen UAT tasks retain `cp2566-v0` for reproducibility.
The change follows the project owner's 7 Nov instruction (D18); rebuild the new snapshot
with `.venv/bin/python scripts/build_snapshot_cp2566_gened.py`.

Internship: the current `cp2566-internship-v2` snapshot fixes 2100301 to Year 3 summer.
The records panel supports a separate, reversible confirmation of registration and
successful internship completion when CR60 omits the course. Save with “บันทึกสถานะฝึกงาน”.
This works without Ollama; it does not change the PDF credit total or GPAX. After the
fixed term, missing confirmation requires review rather than automatic rescheduling.
