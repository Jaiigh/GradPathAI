# GradPath baseline - evidence behind pitch v9

Status as of 2 November 2026. Source deck: `GradPath_Detailed_Engineering_Pitch_v9.pdf`
(slides 11, 16 and 17). Every run uses the synthetic smoke case from slide 10
(`data/case_ai_cap3.json`: C101 and G101 passed, C102 precedes E202, cap 3 credits/term).

## Measurement environment

- Runs of 28 October 2026 on NVIDIA GeForce RTX 5070 (12,227 MiB), Ollama 0.40.11.
- Shared settings: temperature 0, seed 42, num_ctx 8192, `think: false` requested.
- Benchmark (`bench.py`): 1 warm-up + 3 measured runs (mean), num_predict 256.
- End-to-end (`agent.py`): 1 run per model, num_predict 1200 per turn.
- Re-checked on 2 November 2026: `agent.py --mock` passes on Python 3.13.5 with
  OR-Tools 9.15.6755 and produces the same plan hash.
- Live re-check on the development machine on 2 November 2026 (RTX 5060 Ti 16 GB,
  Ollama 0.40.13, `qwen3:8b` ID `500a1f067a9f`, 8.2B Q4_K_M): DONE with the same plan;
  `think: false` was honored (15 / 20 / 32 / 85 generated tokens). The first call included a
  one-off 74 s cold start right after the model download, so this run is not a latency
  measurement.

## Slide 11 - model profiles

| Profile | Task accuracy | Case latency | GPU fit |
|---|---|---|---|
| qwen3:4b | Smoke 1/1 DONE (20-task set pending) | 32.2 s, 4 LLM / 2 tool calls | 100% GPU, 3.88 GB, 154.0 tok/s, TTFT 2.09 s |
| qwen3:8b | Smoke 1/1 DONE (20-task set pending) | 19.9 s, 4 LLM / 3 tool calls | 100% GPU, 6.31 GB, 100.6 tok/s, TTFT 2.10 s |

Sources: `bench_summary.md`, `bench_runs.csv`, `baseline_results.csv`.
Pick presented: qwen3:8b as the primary profile, qwen3:4b as the comparison arm.

## Slide 16 - baseline end-to-end

| Profile | Final state | End-to-end | LLM / tools | Observation |
|---|---|---|---|---|
| qwen3:8b | DONE, as expected | 19.9 s | 4 / 3 | audit -> retrieve -> solve -> submit; gate passed first try |
| qwen3:4b | DONE, as expected | 32.2 s | 4 / 2 | first turn returned no tool call (runtime nudged); skipped audit |
| mock (offline) | DONE, as expected | 1.69 s | 5 / 3 | gate rejected the deliberately wrong order, then accepted the corrected plan (1 revision) |

All three runs accepted `[["C102"], ["E202"]]` with plan hash `014c0caa374bd796`.

Component status as presented:

| Component | Status | Evidence |
|---|---|---|
| Agent runtime + state machine + final gate | Working | Traces; plan hash above |
| audit / retrieve / CP-SAT solve / validate | Working (synthetic data) | Mock trace: gate rejected the wrong order |
| Tool allowlist + strict arguments | Working | `tools.execute` rejects unknown tools and extra arguments; no automated test yet |
| Model benchmark (4B, 8B) | Done | Slide 11 |
| PDF ingestion, real CP snapshot, harness | Not yet | - |

Traces:

- `traces/smoke-01_qwen3-8b_20261028-112835.jsonl` (the slide 17 screenshot)
- `traces/smoke-01_qwen3-4b_20261028-112944.jsonl`
- `traces/smoke-01_mock_20261028-001001.jsonl`

## Caveats found when re-reading the traces (2 November 2026)

The recorded values stand, but they cannot be read as a like-for-like 4B vs 8B comparison
or as steady-state agent latency.

1. **qwen3:4b still reasoned although `think: false` was sent.** All four 4B responses
   carry reasoning text inside `content`; responses 2-4 end with `</think>`. Generated tokens
   per turn were 1200, 452, 592 and 1080, against 15, 20, 32 and 86 for 8B. The first 4B turn
   reached the 1200-token `num_predict` limit mid-reasoning, so it returned no tool call; this
   is the "first turn plain text" on slide 16. The 4B run therefore did not use the matched
   `think: false` setting listed on slide 11. Cause unverified: the model digest was not
   recorded, and `ollama show qwen3:4b` on the benchmark machine would identify the build.
2. **The 8B end-to-end time includes a cold model load** of 6.4 s in its first call
   (`load_duration`). The 4B first call loaded for 2.1 s.
3. **About 2.05 s of every LLM call falls outside Ollama's reported `total_duration`.**
   For 8B calls 2-4 the wall time was 2.30 / 2.42 / 2.94 s, while `total_duration` was
   0.26 / 0.36 / 0.86 s. The same ~2.1 s shows up as TTFT for both models in the
   benchmark. Across four calls this adds ~8.2 s to each end-to-end figure. Likely cause,
   reproduced on the development machine on 2 November 2026 (Ollama 0.40.13): `localhost`
   resolves to `::1` first, Ollama listens on IPv4 only, and each `urllib` request waits
   about 2 s before falling back to `127.0.0.1` (measured 2.01-2.04 s per request via
   `localhost` vs 0.001 s via `127.0.0.1`). A live run through `127.0.0.1` on that machine
   showed no gap: the wall time of its four calls (76.23 s) equals the sum of their
   `total_duration`. Not re-run on the benchmark machine; the code still defaults to
   `http://localhost:11434`.
4. **The first `solve_plan` call includes the OR-Tools import** (3.35 s of tool time in the
   8B run).

Approximate split of the two end-to-end runs:

| Profile | Model load | Overhead outside Ollama | Model compute | Tools | Total |
|---|---:|---:|---:|---:|---:|
| qwen3:8b | 6.4 s | 8.2 s | 1.9 s | 3.3 s | 19.9 s |
| qwen3:4b | 2.2 s | 8.2 s | 21.5 s | 0.3 s | 32.2 s |

## Scope change after the v9 presentation

Professor feedback: a plan must run to the end of Year 4 instead of stopping after two
terms. A student entering Year 1 gets 8 regular terms; a student who has finished Year 2
gets 4. This supersedes slide 2 ("At most two terms", with four-year optimization listed as
outside scope). The other criteria are unchanged: at least 16/20 tasks on the 8B profile,
arms A/B/C, UAT, 10 November (UAT + final report) and 11 November (final pitch + live demo).

## Corrections to earlier notes

- The previous baseline README cited "25 earlier code/protocol tests". The repository has
  no such tests, so the claim was removed.
- The previous version of this file reported mock-only numbers with GPU fit "pending". The
  measured values above replace it.
