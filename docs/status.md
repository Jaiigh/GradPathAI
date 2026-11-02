# Status log

Newest entries first.

## Handoff, 2 Nov 2026 (late)

- Committed through `0766e44` (snapshot, planner core, personas, tests). The next commit adds
  the build scripts, the snapshot source rows and the UAT v1.1 design.
- Next, in this recommended order (confirm with the user): (1) `data/test_set.jsonl` v1.1 and
  the UAT plan v1.1 as a Thai PDF, from the design in `evaluation.md` and the team's v1.0
  PDF; (2) runtime v2, API and React UI for the 4 Nov UAT; (3) language check (D11).
- Source PDFs, outside the repo in the parent `Final_Project` folder: pitch v9, course
  week-13 slides, team UAT plan v1.0 (`GradPath_Group2_UAT_Submission.pdf`).
- Data rebuild: `scripts/build_snapshot_cp2566.py` and `scripts/make_personas.py` reproduce
  the committed files byte for byte.

## 2 Nov 2026 (evening)

- Built `data/snapshots/cp2566-v0.json` from public 2566 sources: 93 courses, study plan of
  138 credits, regulation limits (22 per regular term, 9 per summer), 13 recorded conflicts
  (9 resolved, open ones labelled).
- Backend core in `gradpath/`: contracts, snapshot loader, multi-term CP-SAT planner with
  witnessed relaxations, independent validator, audit. Eight synthetic personas in
  `data/fixtures/personas/`. 26 tests pass; every persona solves to optimality in under
  0.2 s.
- Decisions: D4 amended (two-level missing-data policy), D13 amended (UAT on `cp2566-v0`;
  team UAT plan v1.0 re-based as v1.1), D15 accepted, D16 added (electives as slots unless
  preferred).
- Next: UAT plan v1.1 PDF and test set; runtime v2, API and UI for the 4 Nov UAT.

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
