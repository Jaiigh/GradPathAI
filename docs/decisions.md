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
- Measured 3 Nov 2026 (`eval/run_language.py`, M4 UAT laptop, final UAT build): Thai 10/10,
  English 9/10 goal statements extracted correctly; replies in the student's language 20/20.
  Thai is not worse than English, so the amended choice stands. Details in `evaluation.md`.

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

- Status: accepted, 3 Nov 2026 (proposed by Claude on 2 Nov 2026).
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
- Amended 3 Nov 2026: the record summary, goal state and language moved from the system prompt
  to a state block at the start of each turn's first message, so the system prompt and tools
  stay identical and Ollama reuses its prompt cache. On the M4 UAT laptop the first model call
  of a turn fell from about 10 s to under 1 s.
- Amended 3 Nov 2026: two more guards after the M4 runs. A cap must be a number the student
  typed (the model had chosen 15 for "ไม่อยากลงหน่วยกิตเยอะ"), and after an INFEASIBLE solve the
  turn must end with the blocker (the model had asked the student about relaxations itself in
  one T16 run).

## D18. Pooled general education credits

- Status: accepted, 7 Nov 2026, from the project owner's instruction in this session.
- Decision: replace the four 3-credit GenEd subject-group minimums (social sciences,
  humanities, interdisciplinary, science/mathematics) with one 12-credit category `GE`,
  displayed as “กลุ่มวิชาศึกษาทั่วไป GenEd” / “General Education (GenEd)”. Any combination
  of eligible GenEd coursework satisfies the pool; there are no subject-group minimums.
- Scope: special-group courses (`GE_SPECIAL`, 6 credits), languages (`LANG`, 12 credits),
  and the 138-credit program total retain their separate requirements. Unknown courses
  still require confirmation as GenEd or another eligible category; their identities alone
  do not establish that they are GenEd.
- Versioning: `cp2566-gened-v1` is the default for new uploads and ordinary sessions. Its
  source `U1` records this project decision without attributing it to an official webpage.
  Build it with `scripts/build_snapshot_cp2566_gened.py`. Keep `cp2566-v0` unchanged for
  the frozen UAT tasks, as required by D15.
- Compatibility: legacy `GE_SOC`, `GE_HUM`, `GE_INTER`, and `GE_SCI` records count toward
  `GE` under the new snapshot. Existing uploaded-report sessions migrate on reopening;
  previous plans are marked stale and cannot be reused under the changed snapshot.
  Confirmed student goals are retained; conversation context containing old rules is cleared.

## D19: Internship confirmation and fixed Year 3 summer

Per project owner instruction (7 November 2026), current snapshot `cp2566-internship-v2`
requires 2100301 in `entry_year + 2 / S` only. This compulsory summer does not require
consent for optional summer courses. Both solver and independent validator enforce
this term; horizon extensions cannot move the internship. Older snapshots are preserved.
Uploaded sessions migrate with old plans invalidated.

A student may explicitly attest that they registered for and passed 2100301, separately
from CR60 records. The editable checkbox is saved through a dedicated record decision,
increments the record version, invalidates prior plans, and records provenance in the
trace. It does not invoke the LLM. A passing PDF entry takes precedence and prevents
double counting. Reported credits and GPAX are unchanged. The existing curriculum
policy counts its 2 credits toward the plan total (C12 remains documented); the UI
labels supplemental credits separately. Changing the academic timeline clears attestation.
After Year 3 summer, absent completion yields NEED_INFO before calling the model;
the student must check their status with the department if they have not passed.
The system never assumes completion based only on study year.

## D20. Post-UAT fixes from the 4 Nov findings

- Status: accepted, 9 Nov 2026 (the project owner asked for every remaining item, including the
  improvements listed in the UAT report).
- Evidence: the UAT-day sessions in `local/sessions/20261104-*` (UAT machine, build `a12c6e3`).
  - T11: the agent asked for the code of Software-Defined Systems I (published code unknown,
    conflict C10). The tester typed 2110415 (not in the snapshot), the agent switched to English
    because the reply had no Thai letters, asked again, and after the tester typed 2110413 it
    explained the plan as "Software-Defined Systems I (2110413)"; 2110413 is Computer Security.
    The tester did not accept the result: no next step was offered.
  - T05: no clarifying question appears in either T05 session; the confirmations were the record
    confirmation and the goal card. A live check on 9 Nov showed the model putting the failed
    required course 2110327 into `must_take`, which puts it on the goal card for approval.
  - T09: after the injected planner timeout the only way on was a new session.
  - T08 (technical round, not in the UAT rounds): in every recorded run (3 Nov, two repeats; 9 Nov)
    the agent answered that 2110521 counts as a core-level and a department elective "at the same
    time". The script checks passed; the manual check of T08 failed, so the 40/40 of 3 Nov
    counts script checks only: with the manual check it is 38/40.
- Decision (runtime, enforced in code; all arms):
  1. After a NEED_INFO turn the runtime adds a `next_steps` item: the exact missing data (an
     unpublished course code named by the student or returned by retrieval, with its category; a
     typed code that is not in the snapshot) and two ways forward: plan the rest now, or type a
     code obtained from the department or the registrar. "Plan the rest now" (`POST
     /api/sessions/{id}/defer`) drafts the goal with one `propose_goal`-only call, removes the
     deferred course from `interests` and `must_take`, and falls back to the default goal.
  2. A course title without a published code is rejected as an `interests` topic.
  3. Text from `reply` and `submit_final` is rejected when a Latin course title stands next to the
     code of a different course, e.g. "Software-Defined Systems I (2110413)".
  4. A message without letters (digits only) keeps the conversation language.
  5. `must_take` drops required courses that are not yet passed (retakes included): the planner
     always schedules them, so they are not a goal change and do not go on the goal card.
     `ask_user` questions that mention a course from the confirmed record are rejected.
  6. STOP_UNVERIFIED can be retried from the same record, goal and conversation (`POST
     /api/sessions/{id}/retry`); the operator view can retry with the injected fault removed.
  7. The plan view shows a reason per course (retake, requested, interest, required, category)
     and the category totals before and after the plan; the blocker card compares the
     alternatives in one table.
  8. An info `reply` that lets one course count toward two of its categories at once is rejected
     unless it also says the course counts toward one category only (T08).
  9. (10 Nov) `interests` keeps only topics the student stated: the whole topic, a listed synonym (for
     example ปัญญาประดิษฐ์ or machine learning for AI) or one distinctive word of it (4+ letters, not
     "computer" or "engineering"), so typos elsewhere still count; the model had turned "ช่วยวางแผนให้
     หน่อย" into interests ["AI"].
- Not changed: the frozen test set v1.1 and `cp2566-v0`; the 4 Nov UAT results stay as recorded.

## D21. Experiment arms

- Status: accepted, 9 Nov 2026; implements the arms of pitch v9 slide 15 (`evaluation.md`).
- `Runtime(arm=...)`, `eval.run_tasks --arm A|B|C`. Every arm uses the same snapshot, record
  gate, goal cards, tool guards, final gate, budget and model settings; only control and tools
  differ.
  - A, fixed workflow: the runtime runs audit, retrieval for the goal's interests, solve,
    validate and the final gate in this order. The LLM makes one `propose_goal`-only call to draft
    the goal and writes the explanation as plain text. Vague workload or finishing-time words
    without a number trigger a fixed clarifying question; a rejected draft ends in NEED_INFO with
    the guard's message; a declined goal card gets a fixed reply.
  - B: the arm C agent without `retrieve_courses` (removed from the tool list and the system
    prompt; a call to it is an unknown tool).
  - C: the full agent (the product).
- The optional arm C run on `qwen3:4b` is cut (D12): the model is not installed on the UAT
  machine and the earlier 4B run kept reasoning despite `think: false`.
