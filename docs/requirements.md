# Requirements

Based on pitch v9 (28 Oct 2026), slides 1-2, and updated with the changes in the change log
below.

## Problem and users

Computer Engineering students at Chulalongkorn University (curriculum CP 2566) need a study
plan from their current standing to graduation that respects every curriculum rule and their
own goals.

- Users: CP students.
- Review stakeholders: students and an academic advisor.
- Example request: "Finish by Year 4, Semester 2, focus on AI, and take at most 18 credits
  next term."
- Outputs: a checked multi-term plan, an evidenced blocker, or a specific request for
  missing information.

## Functional requirements

| ID | Requirement | Acceptance condition |
|---|---|---|
| R1 | Transcript input | Course ID, credits, grade and term are extracted with evidence (page, row, document hash) and confirmed by the student before audit or planning. No guessed grade or course ID enters planning. |
| R2 | Planning horizon | Plans cover every term from the next term to the end of Year 4, at most 8 regular terms. Summer terms are included only when the student asks. One curriculum (CP 2566), and every encoded hard rule holds. |
| R3 | Electives | Technical electives in the student's interest area are planned as real courses. Gen-Ed and free electives appear as category slots with credits. |
| R4 | Workload caps | The default cap per term is the maximum allowed by university regulation. The student may set a lower cap for any term. |
| R5 | Interaction | Missing or ambiguous goals are clarified before planning. Hard goal changes happen only after explicit student approval. |
| R6 | Grounded explanation | Explanations cite source IDs. Every course ID mentioned exists in the plan or in retrieved evidence. |
| R7 | Local operation | LLM, backend, UI and data run on one local machine, and no academic data leaves it. |
| R8 | Live demo | For UAT and the final demo, the React UI is connected to the real agent. |

## Quality requirements

| ID | Requirement | Acceptance condition |
|---|---|---|
| Q1 | Task correctness | At least 16 of 20 test-set tasks are correct with `qwen3:8b` in arm C. |
| Q2 | Safety | Zero hard-goal changes without recorded approval, and zero invented course IDs in final outputs. Out-of-scope requests and injected instructions are declined or treated as data. |
| Q3 | Responsiveness | On the UAT machine (set from measurements on 3 Nov 2026, see `evaluation.md`): the progress line appears within 1 s of sending; a turn that ends in a goal card, a question or a reply completes within 15 s; a turn that ends in a plan or a blocker completes within 40 s; no turn exceeds the 120 s budget. |
| Q4 | User acceptance | The UAT acceptance criteria in `evaluation.md` are met. |
| Q5 | Reproducibility | Every run records model tag and digest, Ollama version, GPU, git commit, test-set version and snapshot hash. |

## Out of scope

Live registration, timetable and seat checks, and official certification of graduation.
Four-year planning was out of scope in pitch v9 and is now in scope (see R2).

## Course milestones

From the course slides for week 13 (28 Oct 2026).

| Date | Milestone |
|---|---|
| 31 Oct 2026, 23:59 | UAT plan: users, scenarios, acceptance criteria, test set, feedback form |
| 4 Nov 2026, 13:15-15:30 | In-class UAT with peer groups; configuration comparison |
| 7 Nov 2026, 23:59 | UAT report on Discord |
| 11 Nov 2026 | Final presentation: 5-minute pitch, live demo, final report |

## Change log

| Date | Change | Source |
|---|---|---|
| 28 Oct 2026 | Pitch v9: two-term planning, 20-task evaluation, arms A/B/C, UAT on 10 Nov | pitch v9 |
| 2 Nov 2026 | Horizon extended to the end of Year 4 (R2); four-year planning moves into scope | professor feedback after the v9 presentation |
| 2 Nov 2026 | Mixed electives (R3); regulation-based default caps (R4); summer only on request (R2) | user decision |
| 2 Nov 2026 | Live demo uses the React UI wired to the agent (R8) | user decision |
| 2 Nov 2026 | UAT moves to the in-class session on 4 Nov; UAT report due 7 Nov | course slides, week 13 |
