# Decision records

Each entry lists status, context, decision and consequences. D1-D12 were accepted with the
implementation plan on 2 Nov 2026; D13-D16 were decided the same day; D17 is proposed.

## D1. Build our own harness and freeze the baseline

- Status: accepted, 2 Nov 2026.
- Context: the course Harness.zip is only an example. The baseline loop is non-interactive and
  plans two terms only.
- Decision: build a new Python package, `gradpath/` (runtime, tools, ingestion, API). Keep
  `baseline/` unchanged as the evidence for pitch v9.
- Consequences: the v9 numbers stay reproducible. Tools are ported into the new package, not
  shared with the baseline.

## D2. The planner owns the plan; the LLM refers to it by ID

- Status: accepted, 2 Nov 2026.
- Context: a plan to graduation can hold about 40 courses. Having the LLM copy it into
  `submit_final` invites transcription errors.
- Decision: `solve_plan` stores the candidate in the session and returns a `plan_id`.
  `validate_plan` and `submit_final` take that ID, and the final gate checks the stored
  candidate.
- Consequences: this enforces the v9 invariant "same exact candidate at the final gate". The
  LLM influences plans only through preferences and goal changes.

## D3. Multi-term CP-SAT with category slots and witnessed relaxations

- Status: accepted, 2 Nov 2026.
- Context: the horizon is now the end of Year 4 (requirement R2), and Gen-Ed and free
  electives are slots (R3).
- Decision: model `x[c,t]` for courses, `s[k,t]` for slots and `a[c,k]` for category
  allocation. Guard constraint groups with assumption literals. When the model is infeasible,
  explain it with the returned assumption subset and offer only relaxations that the solver
  proves feasible.
- Consequences: blockers carry evidence, and every proposed relaxation goes through the
  consent flow (D8).

## D4. Policy for unverified data

- Status: accepted, 2 Nov 2026.
- Context: offerings and some prerequisites may not be verifiable in time (pitch v9 slide 18).
- Decision: every snapshot item has a status: `verified`, `inferred`, `unknown` or
  `conflict`. Offerings may be inferred from the official study plan and are labelled in the
  output. The fallback scope is a verified subset of 2110xxx courses.
- Amended 2 Nov 2026 (user decision): missing data is handled at two levels. Missing
  identity data (course code, credits, grade, category of a completed course) leads to
  `NEED_INFO`. Missing supplementary data (prerequisites, offerings, which vary by year)
  does not block planning; each affected item is labelled unverified. Conflicting sources
  are resolved in favour of the newest, 2566-specific source and recorded in the
  snapshot's `conflicts` list.
- Consequences: plans can be produced with incomplete data without presenting guesses as
  facts.

## D5. Text-based PDF ingestion without OCR

- Status: accepted, 2 Nov 2026.
- Context: OCR of Thai text is costly and unreliable. Course codes and grades are ASCII.
- Decision: extract text with coordinates (PyMuPDF) and keep page and row evidence for each
  record. A scanned PDF leads to `NEED_INFO` and manual confirmation. Real transcripts stay
  in `local/`; tests use synthetic PDFs.
- Consequences: the student confirmation gate is the safety net. Personal data never enters
  git.

## D6. BM25 retrieval

- Status: accepted, 2 Nov 2026.
- Decision: use BM25 over course titles and descriptions with a versioned index. Add
  embeddings (for example a multilingual model served by Ollama) only if the conversation
  language becomes Thai (D11).
- Consequences: no extra model is needed for the MVP. Arm B in the experiment removes this
  tool.

## D7. Local FastAPI backend

- Status: accepted, 2 Nov 2026.
- Decision: run a FastAPI app bound to 127.0.0.1, store sessions as JSON under `local/`, let
  Vite proxy `/api`, and warm up the model and the OR-Tools import when the server starts.
- Consequences: no per-call `localhost` penalty and no cold start during demos.

## D8. Goal confirmation and consent through UI cards

- Status: accepted, 2 Nov 2026.
- Decision: the LLM turns the student's words into a goal draft (`propose_goal`), and the UI
  shows it as a card to confirm. Hard changes (horizon, caps, summer, must-take, avoid) apply
  only after the student presses Approve; chat text is never read as consent. Clarifying
  questions use `ask_user` with structured `fields`. Answers that are not plans (information
  or declines) use `reply` with a `kind`.
- Consequences: consent is unambiguous and auditable, and safety and clarification
  behaviour can be scored by script.

## D9. Contracts as pydantic v2 models

- Status: accepted, 2 Nov 2026.
- Decision: implement the pitch v9 slide 7 contracts as pydantic v2 models, and generate the
  tool argument schemas from them.
- Consequences: wrong types and extra fields are rejected in one place.

## D10. Budget per agent turn

- Status: accepted, 2 Nov 2026.
- Context: in the baseline a run can exceed 120 s, because the wall-clock check happens only
  between calls and each call has its own 120 s timeout.
- Decision: the budget (8 tool calls, 2 revisions, 120 s) applies per agent turn, excluding
  time spent waiting for the student. Each LLM call times out at the remaining budget.
- Consequences: interactive sessions are not cut off by the time students take to answer.

## D11. Conversation language decided by measurement

- Status: accepted, 2 Nov 2026. Measurement scheduled for 3 Nov 2026, before UAT.
- Decision: give `qwen3:8b` 10 goal statements in Thai and the same 10 in English and
  compare how accurately it extracts the goal. The UI labels are chosen separately from the
  LLM language.
- Consequences: a Thai conversation also triggers the embedding option in D6.
- Amended 2 Nov 2026 (user decision, for UAT): the UI labels are Thai, and the agent replies
  in the language of the student's message (passed to the model explicitly). Retrieval
  handles Thai titles with character bigrams, so embeddings are not needed for UAT. The
  10 + 10 measurement still runs and is reported; it can change the choice after UAT.

## D12. Model profile and run records

- Status: accepted, 2 Nov 2026.
- Decision: `qwen3:8b` is the primary model. Every run records the model tag and digest, the
  Ollama version, GPU, git commit, test-set version and snapshot hash. A `qwen3:4b` arm is
  optional and is the first item to cut.
- Consequences: results stay comparable across machines and days.

## D13. The UAT on 4 Nov uses an MVP vertical slice

- Status: accepted, 2 Nov 2026.
- Context: the course moved UAT to the in-class session on 4 Nov 2026, and the full system
  cannot be ready by then.
- Decision: UAT uses the React UI wired to the real agent, with interactive clarification and
  consent, multi-term planning on the best snapshot available on 3 Nov, and prepared
  personas. Testers do not use their own transcripts.
- Amended 2 Nov 2026: the snapshot is `cp2566-v0`, built from public 2566 sources, so the
  simulated fallback is not needed. The team's UAT plan v1.0 (two-term synthetic slice) is
  re-based on this curriculum as v1.1, keeping its structure, acceptance criteria and forms
  (user decision).
- Consequences: transcript PDF ingestion follows after UAT (see `plan.md`).

## D14. Documentation language

- Status: accepted, 2 Nov 2026.
- Decision: docs are written in English so they can feed the UAT report, the final report
  and slides. Documents addressed to Thai readers are in Thai and named `*.th.md`.

## D15. Freeze the test set together with its snapshot version

- Status: accepted, 2 Nov 2026.
- Context: the course requires one test set, used by both UAT and the experiment and frozen
  before experimentation. The curriculum snapshot will keep improving after UAT.
- Decision: each task names its `snapshot_id`. Test set v1 (target: 20 tasks) is frozen with
  a git tag before UAT on 4 Nov 2026. The experiment runs on v1 and its snapshot, even if a
  newer snapshot is used for the final demo.
- Consequences: the arm comparison stays valid; data accuracy improvements are reported
  separately.

## D16. Elective requirements are slots unless the student prefers a course

- Status: accepted, 2 Nov 2026 (implements R3).
- Context: with 48 interchangeable department electives, a planner that must pick real
  courses picks arbitrary ones and takes seconds to prove optimality.
- Decision: elective courses enter the planner only when they are preferred (from
  retrieval) or must-take. Every other elective requirement (core-level, department,
  21st-century, Gen-Ed, free) is a 3-credit category slot. Two soft rules follow the
  official study plan: no electives before Year 3 semester 1, and a numbered sequence
  (part I before part II) is kept as an inferred prerequisite.
- Consequences: plans contain only courses the student asked about or must take; every
  test persona solves to optimality in well under a second.

## D17. Runtime guards for a small model

- Status: proposed by Claude, 2 Nov 2026; awaiting the user's acceptance.
- Context: live runs of test set v1.1 on `qwen3:8b` showed three unsafe or brittle habits:
  guessing a course code for a course named without one (for example 2110521 for
  "Software-Defined Systems I"), copying a cap of 30 from an injected "[SYSTEM] approved"
  line, and replying in plain text or JSON text instead of a tool call.
- Decision: enforce these rules in the runtime instead of relying on the prompt. A course ID
  enters the goal only if the student typed it or `retrieve_courses` returned it. Caps above
  the regulation maximum are dropped from a proposal and shown on the goal card as not
  applied. Retrieval drops results below half of the best score. JSON text that parses as a
  tool call is accepted. The record summary and the student's language are given to the
  model in the system prompt. The full list is in `architecture.md`, "Runtime guards".
- Consequences: test set v1.1 passed 40 of 40 runs (two repeats) on the development machine
  on 2 Nov 2026, and 15 of 15 paraphrased variants. The guards apply to every experiment
  arm, so the arm comparison measures control policy and retrieval, not prompt tolerance.
