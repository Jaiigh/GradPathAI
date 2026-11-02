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
- New backend (`gradpath/`): a root `.venv` with its own requirements will be added with the
  first backend code. Planned dependencies: ortools, fastapi, uvicorn, pydantic, pymupdf,
  pytest.

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

- `baseline/agent.py` appends to `baseline/results/baseline_results.csv` and writes a new
  trace on every run, including `--mock`. `baseline/` is frozen, so restore those files
  before committing.
- Git converts line endings to CRLF on checkout; "LF will be replaced by CRLF" warnings on
  `git add` are expected.
