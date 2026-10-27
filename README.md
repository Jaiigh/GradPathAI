# GradPath

A React transcript-first planning prototype. Upload a local file into the left panel; GradPath acknowledges it in the chat, summarizes credit progress, then asks for planning goals.

The browser UI uses synthetic academic data for the credit summary — it does not parse or transmit the selected file. It is not academic advice or a production transcript parser.

## Run locally

```powershell
pnpm install
pnpm dev
```

Then open the local URL printed by Vite (normally `http://localhost:5173`).

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

The benchmark is kept separately from the React app in `baseline/`. From the
repository root, prepare its local Python environment once:

```powershell
py -3.11 -m venv baseline\.venv
baseline\.venv\Scripts\python.exe -m pip install -r baseline\requirements.txt
```

Run the offline smoke test first:

```powershell
baseline\.venv\Scripts\python.exe baseline\agent.py --mock
baseline\.venv\Scripts\python.exe baseline\show_trace.py
```

For the real slide metrics, install and start Ollama, download the two models,
then run the benchmark and end-to-end cases:

```powershell
ollama pull qwen3:4b
ollama pull qwen3:8b
baseline\.venv\Scripts\python.exe baseline\bench.py
baseline\.venv\Scripts\python.exe baseline\agent.py --model qwen3:8b
baseline\.venv\Scripts\python.exe baseline\agent.py --model qwen3:4b
baseline\.venv\Scripts\python.exe baseline\show_trace.py
```

Use `baseline/results/bench_summary.md` for the Slide 11 GPU row and
`baseline/results/baseline_results.csv` plus the latest file in
`baseline/traces/` for Slide 16. The baseline uses synthetic curriculum and
transcript fixtures; it does not evaluate the React interface or real PDF
ingestion.
