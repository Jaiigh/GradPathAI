# Status log

Newest entries first.

## 9 Nov 2026

- Reviewed the 7 Nov commit (CR60 upload, D18, D19): the venv needed `pypdf` and
  `python-multipart`; 75 tests passed; test set v1.1 on that build, repeat 1: 20/20 (repeat 2 was
  disturbed by a parallel live test and stopped).
- Read the UAT-day sessions (`local/sessions/20261104-*`). Found: the T11 code mix-up (2110413
  explained as Software-Defined Systems I), a language switch after a digits-only reply, and three
  places where the submitted UAT report differs from the traces (T16 tester chose "extend horizon";
  T17 tester typed 13; T19 has no planning message). Also: T08 was answered wrongly in every run
  since 3 Nov (manual check).
- D20: NEED_INFO next steps and "plan the rest now", retry after a stop, course name/code check,
  one-category check, retakes kept off the goal card, language kept for digits, plan reasons and
  category totals, alternatives table. D21: experiment arms A and B. 93 tests.
- Experiment (see `evaluation.md`): A 38/40, B 18/40, C 40/40; paraphrases A 14/15, B 8/15, C 15/15.
  Q3 missed on this day (generation 12.1 vs 18.6 tokens/s on 3 Nov).
- `data/results_v1.1.csv` (`eval.fill_results`): 10 UAT rows from the forms and traces, 40 arm C rows.
- Final report: `docs/report/final_report.html` and `GradPath_Group2_Final_Report.pdf`. The roles of
  Techit and Chanon are left for the team to fill.
- Still open: commit (the user commits), re-measure turn times on the demo machine, two demo
  rehearsals, the 5-minute pitch.

## 7 Nov 2026

### 7 Nov 2026: GenEd rule update (D18)

- New default snapshot `cp2566-gened-v1`: one 12-credit “กลุ่มวิชาศึกษาทั่วไป GenEd”
  requirement replaces the four subject-group minimums. Audit, solver, validator, retrieval
  and upload-review options read the same snapshot. Total program credits remain 138.
- Existing uploaded records migrate when reopened; old category assignments count toward
  the pool, and previously displayed plans are marked stale. Frozen UAT tasks continue to
  use the unchanged `cp2566-v0` snapshot.
- Added regression checks for 12 credits from any single old group, the 3-credit shortfall
  case, final-validator rejection, migration, and the new category picker.

- Validation: 69 tests passed; production build passed; the existing uploaded report
  migrated successfully and its browser picker exposes one GenEd option. Ollama remains off.

### CR60 upload implementation

- Default student entry now uploads a complete text-readable CR60 PDF. Synthetic personas
  remain in `?operator`. New `gradpath/ingest/cr60.py` extracts academic rows from all pages,
  preserves attempts and leading-zero IDs, checks page order and CG/CGX, and retains page/row evidence.
- Imported records require explicit curriculum/profile confirmation and category decisions
  for earned courses outside the snapshot. Report/catalog credit disagreements need review;
  confirmed report credits feed the audit, solver and validator without silent substitution.
- New upload/source/replacement API routes keep files under gitignored `local/uploads/`.
  Replacing a report increments the record version, resets goals/model context, and marks old plans stale.
- Original PDFs remain local. Extracted session metadata omits identity headers, national IDs and birthdates.
- Added anonymized parser, PDF, reconciliation, consent, replacement and API tests. No student
  PDFs or extracted personal fixtures are committed. Scans and unsupported layouts remain out of scope.
- Corrected Node requirement to 22.13+ for the pinned pnpm release; added macOS run instructions.
- Validation: 60 automated tests passed; production UI built; desktop/mobile upload,
  confirmation, persistence and malformed-upload checks passed in a local Chrome session.
  Both supplied PDFs reconciled (43 rows / 113 credits and 44 rows / 104 credits).
- On the current M3 / 8 GB Mac, the default 8B model timed out. The 4B model loaded locally
  and passed T01 (goal 36.4 s, plan 89.2 s). This is a single smoke test, not the full
  evaluation; it falls short of the earlier UAT responsiveness targets. Documented the
  `GRADPATH_MODEL=qwen3:4b` launch option without changing the repository's 8B default.

## 3 Nov 2026 (evening)

- User decisions: D17 accepted; T18 change to 2571/1 confirmed; the UAT machine is the user's
  MacBook Air 15" M4 (24 GB). The UAT PDF is with the team (Discord); pages 11-15 will be
  filled on an iPad instead of printed.
- Mac setup: Ollama 0.40.14 through Homebrew (`brew services`), `qwen3:8b` `500a1f067a9f`,
  `scripts/uat_setup.sh`, Apple-silicon GPU line in the run record. `uat_check.py` 18/18.
- Speed: plan turns took 26-29 s because every turn re-read the whole prompt (about 10 s on
  the M4). The per-session state moved to a block at the start of each turn's first message,
  so the system prompt and tools are cached; plan turns now 13-29 s, goal turns 2-3 s.
- Two more runtime guards (D17 amended): caps must be numbers the student typed; after an
  INFEASIBLE solve the turn must end with the blocker. Prompt examples added for per-term caps
  and "leave out <code>". 45 tests.
- Final UAT build on the M4: test set v1.1 40/40 (two repeats), paraphrases 15/15, D11 Thai
  10/10 and English 9/10 (`eval/run_language.py`). Q3 limits set in `requirements.md`.
  `data/test_set.jsonl` and the snapshot did not change, so the PDF hashes still match.
- Found: the display turning off paused a run for 61 s; start the server under `caffeinate`.
- Next: commit, then the user tags `uat-v1.1` (by Wed 12:00). After the tag, on a separate
  branch: arms A and B and their runner, a script that fills `data/results_template.csv` from
  traces, transcript ingestion (waiting for the user's sample format). Still open: ask the TA
  about the arm comparison on 4 Nov; fill names into the LINE message.

## Handoff, 3 Nov 2026 (early)

- Committed through `2462970` (runtime v2, API, UI, test set v1.1). After it:
  `eval/run_paraphrases.py` (the 15 reworded human-round tasks and two probes; 15/15 on
  2 Nov) and this entry.
- Files outside git, in the parent `Final_Project` folder: the UAT plan v1.1 PDF, now named
  `GradPath_Group2_UAT.pdf` (15 pages; at the user's request, Appendix C is removed, and so
  are the footer date and the other dates of the plan's own revision; the list of changes
  from v1.0 is a comment at the top of the build script and in `evaluation.md`);
  `GradPath_UAT_v1.1/build_uat_plan.py` (writes that file; close the PDF viewer first, or it
  writes `*_new.pdf`); `GradPath_UAT_v1.1/line_message_uat.th.txt` (the team's UAT-day
  instructions, roles still to be filled with names).
- Waiting for the user: accept or change D17 (status proposed); confirm the T18 change to
  2571/1.
- Before the UAT: (1) set up the UAT laptop (`scripts\uat_setup.ps1`), run
  `scripts\uat_check.py` and `python -m eval.run_paraphrases` there, record GPU, VRAM and turn
  times (they set the Q3 limits in `requirements.md`); if the laptop is too slow, decide the
  fallback before the feature freeze, Wed 4 Nov 10:00; (2) ask the TA whether the
  configuration comparison (arms A/B/C) is expected on 4 Nov (`plan.md`, open questions;
  arms A and B are not built); (3) the D11 measurement (10 Thai + 10 English goal
  statements); (4) tag `uat-v1.1` by Wed 12:00 (the user tags); rebuild the PDF if the test
  set changes so its hashes match; (5) print pages 11-15 of the PDF.
- After the UAT: run T15 in the technical round, fill `data/results_template.csv` from the
  forms and `local/traces/`, fix and retest by 6 Nov, UAT report on Discord by 7 Nov 23:59;
  then follow `plan.md` (PDF ingestion, experiment arms, final report).

## 2 Nov 2026 (night)

- Test set v1.1 written (20 tasks: 4 per type and per family). T18 changed from "by 2571/2"
  to "by 2571/1", because 2571/2 is the normal end of Year 4 for y2-mid.
- Planner tie-break: requested courses fill their most specific category before a slot (T07
  had shown a core-elective slot next to three requested core-level electives).
- Runtime v2, retrieval, API and UI built and connected (R8). Live `qwen3:8b` on the
  development machine: 40/40 PASS over two repeats of the test set and 15/15 paraphrased
  variants of the human-round tasks; an off-topic request was declined; longest turn 4.7 s.
- Found in live runs and fixed in the runtime (D17, proposed): guessed course codes for
  courses without a published code, a cap of 30 copied from an injected "[SYSTEM]" line,
  replies in English after Thai input, and plain-text or JSON-text replies.
- D11 amended: Thai UI, replies in the student's language (user decision); the measurement is
  still to run.
- UAT machine: a laptop with an unknown GPU; setup and check scripts are ready
  (`docs/dev-setup.md`, "UAT machine").

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

2026-11-07: D19 implemented in `cp2566-internship-v2`. Added independent internship
attestation UI/API, fixed 2100301 to Year 3 summer in planner and validator, and
NEED_INFO for missing completion after that term. Uploaded v0/v1 sessions migrate
without assuming completion; obsolete plans are invalidated. Browser checks cover
save/reload/revoke with Ollama stopped. PDF credits and GPAX remain unchanged.
