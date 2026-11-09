# Implementation plan

Approved on 2 Nov 2026 and revised the same day for the in-class UAT on 4 Nov (course slides,
week 13). Decisions D1-D15 are in `decisions.md`.

## Milestones

| Date | Milestone | Exit criteria |
|---|---|---|
| Mon 2 Nov | Docs, dev environment, decisions | done (see `status.md`) |
| Tue 3 Nov | UAT plan, test set v1, feedback form; MVP built | see "Tuesday 3 Nov" below |
| Wed 4 Nov, morning | MVP hardened; feature freeze at 10:00 | every UAT task passes twice on the UAT machine |
| Wed 4 Nov, 13:15-15:30 | In-class UAT: round 1 with group 4 (13:15-14:15), round 2 with group 7 (14:30-15:30) | feedback collected, traces saved |
| Thu 5 - Fri 6 Nov | UAT fixes; real CP 2566 snapshot; transcript PDF ingestion | done 7 Nov: text-layer CR60 ingestion (no OCR), D18, D19 |
| Sat 7 Nov, 23:59 | UAT report submitted on Discord | done |
| Sun 8 - Mon 9 Nov | UAT fixes (D20); experiment: arms A/B/C on frozen test set v1.1 | done 9 Nov: see `evaluation.md`, "Experiment results" |
| Tue 10 Nov | Final report, demo rehearsal (slides are not listed by the course; a 5-minute pitch is) | report in `docs/report/`; two clean rehearsals still to do |
| Wed 11 Nov | Final presentation: 5-minute pitch, live demo, final report | - |

## MVP scope for UAT (D13)

| Included | Deferred until after UAT |
|---|---|
| 4-5 prepared personas, each with a record review and confirmation step | transcript PDF upload and ingestion |
| Goal card, clarifying questions, consent card for hard changes | official prerequisites and offerings (not published) |
| Multi-term planning to the end of Year 4, with category slots | summer terms, if time runs out on Tuesday |
| Evidenced blocker with witnessed alternatives | embeddings and OCR |
| Out-of-scope declines; injected text treated as data | `qwen3:4b` arm |
| Traces and a run record per session | |

## Tuesday 3 Nov

1. UAT plan v1.1 as a Thai PDF: the team's v1.0 structure re-based on `cp2566-v0` (D13).
   Deliver test set v1.1 (`data/test_set.jsonl`) with it and freeze both with the snapshot
   version (D15) by Wed 12:00. Draft PDF and test set done on 2 Nov; rebuild the PDF after
   any test-set change so that its hashes match.
2. Language check (D11): 10 Thai and 10 English goal statements on `qwen3:8b`; choose the
   conversation language for UAT.
3. MVP build:
   - done on 2 Nov: contracts, `cp2566-v0` snapshot, personas, multi-term planner,
     independent validator, audit, 26 tests;
   - done on 2 Nov (night): runtime v2 (interactive state machine, sessions, `propose_goal` /
     `ask_user` / `reply`, `plan_id`, budget, faults, traces, run record), BM25 retrieval,
     FastAPI app, React UI (operator task picker, persona picker, record review, chat, goal,
     consent, plan, blocker and stop cards), test-set runner and scorer, UAT setup and check
     scripts; 43 tests; test set v1.1 at 40/40 PASS on the development machine;
   - still open: run `scripts/uat_check.py` on the UAT laptop.
4. Measure first-response and turn times on the UAT machine; set the Q3 limits.

## Curriculum data

A data collector is gathering the CP 2566 data from this priority list:

| Priority | Data |
|---|---|
| P0 | source register; program facts (total credits, minimum GPAX); categories with minimum credits; every required course (including those outside the department) and the 2110xxx electives, with prerequisites and descriptions; the 8-semester study plan; credit limits per regular and summer term; meaning of every grade |
| P1 | actual offerings over the last 2-3 years; Gen-Ed groups; co-requisites; remaining regulations; conflicting values (for example 45 vs 40 credits) |
| P2 | descriptions of electives outside the department |

Update 2 Nov 2026: the public sources below were enough to build `cp2566-v0`, so the user
dropped the separate data collection. Unknown items stay labelled (D4); conflicts are
resolved in favour of the newest 2566-specific source and recorded in the snapshot.

Public sources checked on 2 Nov 2026:

| Data | Found | Source | Status |
|---|---|---|---|
| Study plan, 8 semesters + Year-3 summer (138 credits) | yes | department page for the 2566 curriculum and its study-plan image | verified, with typos noted below |
| Category structure and minimums | yes, inconsistent | same page | conflict |
| Required courses with credits | yes | same page | verified except the conflicts below |
| Electives: 48 courses in the 2110xxx list, 5 in the core-elective group | yes | same page | verified list; one placeholder code (21105xx) |
| Credit limits | at most 22 per regular term, 9 per summer; more needs the dean's approval; no minimum stated | university regulation on higher-education study, B.E. 2566, clause 59 | verified |
| Retake rules | F/U/W in a required course must be retaken; in an elective, retaken or replaced | same regulation, clause 67 | verified |
| Graduation | GPAX at least 2.00 and every required course passed | same regulation | verified |
| Grades that earn credit | A to D and S; A to F count in GPA; grade points not stated | same regulation, definitions | verified (partial) |
| 21st-century skills group | 4 of 8 course codes, plus 2 multidisciplinary codes | Electrical Engineering 2566 curriculum (faculty-wide courses) | inferred |
| Elective descriptions, a few prerequisites | partial | CP curriculum document 2016 | inferred |
| Prerequisites | arrows in the study-plan image only | study-plan image | inferred |
| Gen-Ed course lists, actual offerings, co-requisites | no | - | unknown |

Conflicts on the 2566 page: total 138 vs 141 (sum of categories); basic engineering 15 vs
11 vs 12 (list sum); core 45 vs 40 vs 42 (list sum) vs 39 (image); 2110318 is 1 credit in
the plan but 3 in the core list; Exploring Engineering World is 2110111 (3 credits) in the
image and 2100111 (1 credit) in the text; 2110233 is in the basic-engineering list but not
in the plan; semester 4/1 is labelled 16 credits but its courses sum to 17; the 4/1 approved
elective shows code 2110101. The collector's remaining work: official prerequisites,
resolving these conflicts, Gen-Ed groups, 21st-century codes, and elective offerings.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Curriculum data late or incomplete | high | high | use the data as delivered, with status labels (D4); `cp-sim-v0` for UAT; verified 2110xxx subset |
| MVP unstable during UAT | medium | high | feature freeze Wed 10:00; two dry runs; model warm-up; recorded backup demo |
| `qwen3:8b` errors in multi-turn tool use | medium | medium | strict schemas, nudges, arm A behaviour as a fallback mode |
| Thai text extraction from the transcript | medium | medium | rely on ASCII course codes and grades; student confirmation gate |
| Too much work for the time left | high | high | cut lines below; update `status.md` daily |

## Cut lines

Cut in this order if the schedule slips: the `qwen3:4b` arm, embeddings, streaming progress
messages, summer terms, and finally PDF ingestion (falling back to persona or CSV records).
Applied on 9 Nov: the `qwen3:4b` arm and embeddings are cut; PDF ingestion was built (text layer).

## Open questions

- Week 13 lists the configuration comparison on 4 Nov. Are comparison results expected that
  day, or only in the final report? To confirm with the TA.
- Regulation values (credit caps, grade meanings): pending the curriculum data.
- Redacted transcript sample for the parser: pending.
