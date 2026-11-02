"""CP-SAT planner over every term from the next term to the goal horizon (decision D3).

Variables: x[c,t] course c in term t; s[k,t] number of slots of category k in term t;
a[c,k] course c counts toward category k. Hard rules: unique courses, required coverage,
prerequisites known to the snapshot, known offerings, caps, category minimums, must-take / avoid.
Soft: preferred courses that count toward a category, closeness to the official study-plan term,
balanced load, fewest credits. Elective courses enter the model only when preferred or must-take;
every other elective requirement is a category slot (requirement R3).
Unknown offerings and prerequisites do not constrain the plan; the items are flagged instead (D4).
"""
from __future__ import annotations

import uuid

from ortools.sat.python import cp_model

from .. import terms as T
from ..contracts import GoalConstraints, PlanCandidate, PlanItem, PlanTerm, StudentState
from ..rules import standing
from ..snapshot import Snapshot

W_PREF, W_PLAN, W_BAL, W_EARLY, W_SLOT, W_KEEP, W_SLACK = 1000, 10, 5, 20, 1, 2, 100_000
ELECTIVE_CATS = ("CORE_ELECTIVE", "DEPT_ELECTIVE", "MULTI_21C", "FREE")
TARGETED_SLOTS = ("CORE_ELECTIVE", "DEPT_ELECTIVE", "MULTI_21C")  # prefer a free-elective slot when either works


def _first_elective_term(snap: Snapshot, entry_year: int) -> str:
    """Earliest study-plan term with an elective, mapped to the student's calendar (Year 3/1 in CP 2566)."""
    for t in snap.data["study_plan"]:
        if any(i.get("slot") in ELECTIVE_CATS for i in t["items"]):
            return T.label(entry_year + t["year"] - 1, t["semester"])
    return T.label(entry_year, "1")


def term_caps(snap: Snapshot, goal: GoalConstraints, labels: list[str]) -> dict[str, int]:
    reg_max, summer_max = snap.regulation("max_credits_regular"), snap.regulation("max_credits_summer")
    caps = {}
    for t in labels:
        top = summer_max if T.is_summer(t) else reg_max
        base = summer_max if T.is_summer(t) else (goal.default_cap or reg_max)
        caps[t] = min(goal.caps.get(t, base), top)
    return caps


def _allowed(snap: Snapshot, goal: GoalConstraints, cid: str, term: str) -> bool:
    offered, sem = snap.offered_semesters(cid), T.semester(term)
    if offered is not None:
        if sem not in offered:
            return False
        return sem != "S" or goal.allow_summer or offered == ["S"]
    return sem != "S" or goal.allow_summer


def solve(snap: Snapshot, student: StudentState, goal: GoalConstraints, time_limit_s: float = 10.0,
          extra_cap: bool = False) -> dict:
    """Return a dict with status PLAN (+ candidate), INFEASIBLE, NEED_INFO or UNKNOWN.

    extra_cap=True lets regular-term caps rise up to the regulation maximum at a high cost; diagnose() uses it
    to find the smallest cap increase that makes the goal feasible.
    """
    st = standing(snap, student)
    if st.unknown_courses:
        return {"status": "NEED_INFO", "missing": [f"category of completed course {c}" for c in st.unknown_courses]}
    unknown_ids = [c for c in goal.must_take + goal.preferred_course_ids if c not in snap.courses]
    if unknown_ids:
        return {"status": "NEED_INFO", "missing": [f"course {c} is not in snapshot {snap.snapshot_id}" for c in unknown_ids]}
    labels = T.span(student.next_term, goal.horizon_end)
    if not labels:
        return {"status": "INFEASIBLE", "reason": "the horizon ends before the next term"}
    caps = term_caps(snap, goal, labels)
    reg_max = snap.regulation("max_credits_regular")
    pref = set(goal.preferred_course_ids) | set(goal.must_take)
    done = set(st.completed)
    cand = [c for c in snap.courses if c not in done and c not in goal.avoid
            and (snap.courses[c]["kind"] == "required" or c in pref)]
    required = [c for c in snap.required_courses() if c not in done]
    idx = {t: i for i, t in enumerate(labels)}
    slot_cats = snap.slot_categories()

    m = cp_model.CpModel()
    zero = m.NewConstant(0)
    x = {(c, t): m.NewBoolVar(f"x_{c}_{t}") for c in cand for t in labels if _allowed(snap, goal, c, t)}
    s = {(k, t): m.NewIntVar(0, caps[t] // snap.categories[k]["slot_credits"], f"s_{k}_{t}")
         for k in slot_cats for t in labels if not T.is_summer(t) or goal.allow_summer}

    def taken(c):
        return zero + sum(x[c, t] for t in labels if (c, t) in x)

    def load(t):
        return zero + sum(snap.courses[c]["credits"] * x[c, t] for c in cand if (c, t) in x) + \
            sum(snap.categories[k]["slot_credits"] * s[k, t] for k in slot_cats if (k, t) in s)

    for c in cand:
        m.Add(taken(c) <= 1)
    for c in dict.fromkeys(required + [c for c in goal.must_take if c not in done]):
        if not any((c, t) in x for t in labels):
            return {"status": "INFEASIBLE", "reason": f"{c} cannot be placed in any term of the horizon"}
        m.Add(taken(c) == 1)
    for c in cand:
        for p in snap.prereqs(c):
            if p in done:
                continue
            for t in labels:
                if (c, t) in x:
                    m.Add(x[c, t] <= zero + sum(x[p, u] for u in labels if idx[u] < idx[t] and (p, u) in x))

    slack = {}
    for t in labels:
        if extra_cap and not T.is_summer(t) and caps[t] < reg_max:
            slack[t] = m.NewIntVar(0, reg_max - caps[t], f"slack_{t}")
            m.Add(load(t) <= caps[t] + slack[t])
        else:
            m.Add(load(t) <= caps[t])

    a, cat_credit = {}, {k: [zero] for k in snap.categories}
    for c in list(done) + cand:
        if c not in done and not any((c, t) in x for t in labels):
            continue
        cats, credits = snap.courses[c]["categories"], snap.courses[c]["credits"]
        active = 1 if c in done else taken(c)
        if len(cats) == 1:
            cat_credit[cats[0]].append(credits * active)
            continue
        for k in cats:
            a[c, k] = m.NewBoolVar(f"a_{c}_{k}")
            cat_credit[k].append(credits * a[c, k])
        m.Add(sum(a[c, k] for k in cats) <= active)
    for credits, cat in st.external.values():
        cat_credit[cat].append(credits)
    for k, cat in snap.categories.items():
        slots = [cat["slot_credits"] * s[k, t] for t in labels if (k, t) in s]
        m.Add(sum(cat_credit[k]) + sum(slots) >= cat["min_credits"])

    plan_dev = []
    for c in required:
        pt = snap.courses[c]["plan_term"]
        want = T.label(student.entry_year + pt["year"] - 1, pt["semester"])
        target = 0 if T.key(want) < T.key(labels[0]) else idx.get(want, len(labels) - 1)
        plan_dev += [abs(idx[t] - target) * x[c, t] for t in labels if (c, t) in x]
    peak = m.NewIntVar(0, reg_max, "peak")
    for t in labels:
        if not T.is_summer(t):
            m.Add(peak >= load(t))
    total = sum(load(t) for t in labels)
    counted_pref = [a[c, k] for (c, k) in a if c in pref and c not in done] + \
        [taken(c) for c in cand if c in pref and len(snap.courses[c]["categories"]) == 1]
    first_elective = T.key(_first_elective_term(snap, student.entry_year))
    early = [v for (c, t), v in x.items() if snap.courses[c]["kind"] != "required" and T.key(t) < first_elective] + \
        [v for (k, t), v in s.items() if k in ELECTIVE_CATS and T.key(t) < first_elective]
    targeted = [v for (k, _), v in s.items() if k in TARGETED_SLOTS]
    kept = [a[c, snap.courses[c]["categories"][0]] for c in done if (c, snap.courses[c]["categories"][0]) in a]
    m.Maximize(W_PREF * (zero + sum(counted_pref)) - W_PLAN * (zero + sum(plan_dev)) - W_BAL * peak - total
               - W_EARLY * (zero + sum(early)) - W_SLOT * (zero + sum(targeted)) + W_KEEP * (zero + sum(kept))
               - W_SLACK * (zero + sum(slack.values())))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 42
    status = solver.Solve(m)
    if status == cp_model.INFEASIBLE:
        return {"status": "INFEASIBLE"}
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"status": "UNKNOWN", "reason": f"solver status {solver.StatusName(status)} within {time_limit_s}s"}

    out_terms = []
    for t in labels:
        items = []
        for c in cand:
            if (c, t) in x and solver.Value(x[c, t]):
                cats = snap.courses[c]["categories"]
                cat = cats[0] if len(cats) == 1 else next((k for k in cats if solver.Value(a[c, k])), "UNALLOCATED")
                items.append(PlanItem(course_id=c, credits=snap.courses[c]["credits"], category=cat,
                                      flags=snap.unverified_flags(c)))
        for k in slot_cats:
            for _ in range(solver.Value(s[k, t]) if (k, t) in s else 0):
                items.append(PlanItem(slot=k, credits=snap.categories[k]["slot_credits"], category=k))
        cap = caps[t] + (solver.Value(slack[t]) if t in slack else 0)
        out_terms.append(PlanTerm(term=t, kind="summer" if T.is_summer(t) else "regular", cap=cap, items=items))
    raised = {t: caps[t] + solver.Value(v) for t, v in slack.items() if solver.Value(v)}
    plan = PlanCandidate(plan_id=uuid.uuid4().hex[:8], snapshot_id=snap.snapshot_id, snapshot_hash=snap.content_hash,
                         record_version=student.record_version, goal_version=goal.goal_version, terms=out_terms,
                         solver={"status": solver.StatusName(status), "wall_s": round(solver.WallTime(), 3),
                                 "raised_caps": raised})
    plan.plan_hash = plan.compute_hash()
    return {"status": "PLAN", "candidate": plan}


def _next_regular(term: str) -> str:
    t = T.following(term)
    return T.following(t) if T.is_summer(t) else t


def diagnose(snap: Snapshot, student: StudentState, goal: GoalConstraints, time_limit_s: float = 10.0) -> dict:
    """Explain an infeasible goal with relaxations that the solver proves feasible (EVIDENCED_BLOCKER)."""
    alternatives = []
    r = solve(snap, student, goal, time_limit_s, extra_cap=True)
    if r["status"] == "PLAN" and r["candidate"].solver["raised_caps"]:
        alternatives.append({"kind": "raise_caps", "caps": r["candidate"].solver["raised_caps"]})
    if not goal.allow_summer:
        if solve(snap, student, goal.model_copy(update={"allow_summer": True}), time_limit_s)["status"] == "PLAN":
            alternatives.append({"kind": "allow_summer"})
    horizon = goal.horizon_end
    for _ in range(2):
        horizon = _next_regular(horizon)
        if solve(snap, student, goal.model_copy(update={"horizon_end": horizon}), time_limit_s)["status"] == "PLAN":
            alternatives.append({"kind": "extend_horizon", "horizon_end": horizon})
            break
    return {"status": "INFEASIBLE", "alternatives": alternatives,
            "modeled_constraints": ["unique", "required", "prerequisites (known)", "offerings (known)", "caps",
                                    "category minimums", "must_take", "avoid", "horizon"]}
