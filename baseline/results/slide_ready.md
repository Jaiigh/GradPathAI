# GradPath baseline - slide-ready evidence

Run date: 28 October 2026  
Hardware detected: NVIDIA GeForce RTX 5070, 12,227 MiB VRAM

## Slide 11 - current measured result

| Metric | Result | Interpretation |
|---|---:|---|
| Task accuracy | Smoke 1/1 DONE | The supplied synthetic case matched the expected plan. The 20-task set is still pending. |
| End-to-end latency | 1.69 s | Offline scripted-model smoke run only; do not present this as qwen3 latency. |
| Tool calls | 3 | audit -> keyword retrieval -> CP-SAT solve |
| Final-gate revisions | 1 | The validator rejected a deliberately invalid first plan, then accepted the corrected plan. |
| GPU fit | Pending | Ollama and the qwen3 models were not available for this run. |

Recommended Slide 11 wording:

> Smoke 1/1 DONE (20-task set pending). The deterministic pipeline completed in 1.69 s in offline mock mode. qwen3:4b/qwen3:8b latency, throughput, and GPU-fit measurements remain pending an Ollama benchmark run.

## Slide 16 - existing evidence

> The baseline runs end to end on the supplied synthetic case: input verification -> audit -> keyword retrieval -> CP-SAT planning -> mandatory final gate -> DONE. The final plan matched the expected result (Term 1: C102; Term 2: E202). The validator rejected an invalid prerequisite order before accepting the corrected plan. Trace, timing, and plan hash were logged.

Measured details:

- Final state: `DONE`
- Expected-plan match: `true`
- Accepted plan: `[["C102"], ["E202"]]`
- LLM calls: 5 scripted calls
- Tool calls: 3
- Revisions: 1
- End-to-end time: 1.69 s
- Plan hash: `014c0caa374bd796`

## Next implementation

> Run qwen3:4b and qwen3:8b through Ollama, build the 20-task evaluation set, replace synthetic curriculum/transcript fixtures, add verified PDF ingestion and CLARIFY/consent dialogue, then move the loop into Harness M8/M9.

## Important scope note

The measured run is an offline smoke test with a scripted model and synthetic data. It proves tool orchestration, CP-SAT planning, and final-gate enforcement; it does not measure model quality or GPU performance.
