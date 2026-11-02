# Status log

Newest entries first.

## 2 Nov 2026

- Re-documented the pitch v9 baseline evidence, with the caveats found in the traces
  (`baseline/results/slide_ready.md`).
- Scope change: plans now run to the end of Year 4 (professor feedback after the v9
  presentation).
- Accepted decisions D1-D15 (`decisions.md`).
- Course schedule (week 13): in-class UAT on 4 Nov, UAT report due 7 Nov; plan revised
  (`plan.md`).
- Dev machine ready: baseline venv, frontend dependencies, Ollama 0.40.13 with `qwen3:8b`.
  Mock and live baseline runs pass.
- Findings: `localhost` costs about 2 s per Ollama call on Windows (use 127.0.0.1); the
  `qwen3:4b` run in pitch v9 kept reasoning despite `think: false`; demos need a warmed-up
  model.
- Shared the curriculum data priority list (P0/P1/P2, see `plan.md`) with a data
  collector. Completeness is not guaranteed; the snapshot will use whatever arrives.
- Checked public sources for CP 2566 (`plan.md`, "Curriculum data"): the study plan,
  required courses, elective lists and the registration, retake and graduation rules are
  public. Prerequisites, Gen-Ed lists and offerings are not, and the department page
  contradicts itself on several category totals and course credits.
- Open: UAT plan and test set v1 (needed before 4 Nov), conversation language (D11), redacted
  transcript sample.

## 28 Oct 2026

- Pitch v9 presented. The baseline runs end to end on `qwen3:8b` and `qwen3:4b` on a
  synthetic two-term case.
