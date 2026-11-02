# Development setup

Verified on the development machine on 2 Nov 2026: Windows 11, NVIDIA RTX 5060 Ti 16 GB
(driver 610.88), Python 3.13.5, Node 22.18.0, pnpm 11.25.0 through corepack, Ollama 0.40.13,
`qwen3:8b` (ID `500a1f067a9f`, 8.2B, Q4_K_M).

## Frontend

```powershell
corepack pnpm install
corepack pnpm dev        # Vite dev server, normally http://localhost:5173
corepack pnpm build
```

`corepack` uses the pnpm version pinned in `package.json`; no global pnpm install is needed.

## Python

- Baseline: `baseline\.venv` (Python 3.13.5 + OR-Tools 9.15.6755), created with
  `py -3 -m venv baseline\.venv` and
  `baseline\.venv\Scripts\python.exe -m pip install -r baseline\requirements.txt`.
- Backend (`gradpath/`): root `.venv` (Python 3.13.5) with `requirements.txt`, created with
  `py -3 -m venv .venv` and `.venv\Scripts\python.exe -m pip install -r requirements.txt`.
  Run the tests with `.venv\Scripts\python.exe -m pytest -q`.

## GradPath server

- Start: `.venv\Scripts\python.exe -m gradpath.api` (127.0.0.1:8000). It serves the built UI
  from `dist/` (run `corepack pnpm build` first; restart the server after a rebuild) and warms
  up the model and the planner at startup. `/api/health` reports the warm-up, model digest,
  GPU, git commit and test-set hash.
- UI development: also run `corepack pnpm dev`; `vite.config.js` proxies `/api` to the
  server.
- Operator view: `http://127.0.0.1:8000/?operator` lists the UAT tasks by round; starting a
  task binds its persona, fault and snapshot overlay. The operator panel (bottom right) shows
  the run record and turn timings and links to the tester view of the same session.
- Sessions and traces go to `local/sessions/` and `local/traces/` (gitignored); runner results
  go to `local/eval/`.

## UAT machine

The UAT runs on a laptop whose GPU was not known on 2 Nov 2026. On that laptop:

1. Install Python 3.13, Node 20+ and Ollama, then clone the repository at the `uat-v1.1` tag.
2. Run `powershell -ExecutionPolicy Bypass -File scripts\uat_setup.ps1` (venv, dependencies,
   UI build, `ollama pull qwen3:8b`, tests, quick check).
3. `.venv\Scripts\python.exe scripts\uat_check.py` runs the ten human-round tasks end to end
   and fails if any task fails or a turn exceeds 120 s. Record the GPU, VRAM and turn times
   from its output; they set the Q3 limits.
4. Before each round: Ollama running, server started (model warm), `?operator` open, one
   task run once. If `qwen3:8b` is too slow on the laptop GPU, fall back to running the
   server on the development machine; decide before the feature freeze (Wed 4 Nov, 10:00).

On the development machine (RTX 5060 Ti 16 GB) on 2 Nov 2026 the check passed 18/18, and a
warm agent turn took 1.4-4.7 s.

## Ollama

- Installed per user (`winget install Ollama.Ollama`) under
  `%LOCALAPPDATA%\Programs\Ollama`. Terminals opened before the install may not find
  `ollama` on PATH; open a new terminal.
- Model: `ollama pull qwen3:8b`.
- Use `http://127.0.0.1:11434`. Through `localhost`, every request from Python `urllib` took
  2.01-2.04 s, against 0.001 s through 127.0.0.1, because `localhost` resolves to `::1` first
  and Ollama listens on IPv4 only.
- `think: false` is honoured by this `qwen3:8b` build. After any model update, check again
  that responses carry no reasoning text in `content` (in pitch v9, the `qwen3:4b` build
  ignored the setting).
- Cold start: the first call after a fresh download took 74 s. Warm the model up before
  demos and timing runs.
- Record the model ID (`ollama list`) and `/api/version` in every run record.

## Pitfalls

- Reading PDFs: `pdftoppm` (poppler) is not installed, so page rendering fails. Extract text
  with PyMuPDF in a scratch environment (`pip install pymupdf`); it is not a project
  dependency.
- Shell heredocs that contain a single quote fail in this environment; write scripts to a
  file instead.

- `baseline/agent.py` appends to `baseline/results/baseline_results.csv` and writes a new
  trace on every run, including `--mock`. `baseline/` is frozen, so restore those files
  before committing.
- Git converts line endings to CRLF on checkout; "LF will be replaced by CRLF" warnings on
  `git add` are expected.
