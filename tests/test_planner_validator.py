import pytest

from gradpath import snapshot, terms as T
from gradpath.contracts import GoalConstraints, PlanItem
from gradpath.fixtures import load_persona
from gradpath.rules import allocate
from gradpath.tools.audit import audit
from gradpath.tools.planner import diagnose, solve
from gradpath.tools.validator import validate

SNAP = snapshot.load()
AI = ["2110476", "2110477", "2110571", "2110572", "2110573", "2110574"]
PLANNABLE = ["y1-start", "y2-mid", "y3-base", "y3-retake-open", "y3-retake-passed", "y4-final"]


def goal_for(student, **kw):
    return GoalConstraints(horizon_end=T.end_of_year4(student.entry_year), **kw)


def plan_for(name, **kw):
    st = load_persona(name)
    goal = goal_for(st, **kw)
    r = solve(SNAP, st, goal)
    assert r["status"] == "PLAN", r
    return st, goal, r["candidate"]


@pytest.mark.parametrize("name", PLANNABLE)
@pytest.mark.parametrize("prefs", [[], AI])
def test_every_planner_output_passes_the_validator(name, prefs):
    st, goal, plan = plan_for(name, preferred_course_ids=prefs)
    v = validate(SNAP, st, goal, plan)
    assert v.valid, v.errors
    assert v.total_credits >= 138
    assert plan.solver["status"] == "OPTIMAL"


def test_preferred_courses_become_real_courses_and_the_rest_are_slots():
    st, goal, plan = plan_for("y3-base", preferred_course_ids=AI)
    courses = {i.course_id for t in plan.terms for i in t.items if i.course_id}
    assert set(AI) <= courses
    st, goal, plan = plan_for("y3-base")
    electives = [i for t in plan.terms for i in t.items if i.course_id and SNAP.courses[i.course_id]["kind"] != "required"]
    assert electives == []


def test_numbered_sequence_and_retake_order():
    st, goal, plan = plan_for("y3-base", preferred_course_ids=AI)
    when = {i.course_id: T.key(t.term) for t in plan.terms for i in t.items if i.course_id}
    assert when["2110476"] < when["2110477"]
    st, goal, plan = plan_for("y3-retake-open")
    term = next(t.term for t in plan.terms for i in t.items if i.course_id == "2110327")
    assert T.semester(term) == "2"
    st, goal, plan = plan_for("y3-retake-passed")
    assert all(i.course_id != "2603284" for t in plan.terms for i in t.items)


def _mutations(plan):
    """Yield (description, mutated plan) pairs that must all be rejected."""
    regular = [t for t in plan.terms if t.kind == "regular" and t.items]
    first, last = regular[0], regular[-1]

    p = plan.model_copy(deep=True)
    victim = next(i for i in p.terms[-1].items if i.course_id)
    p.terms[-1].items.remove(victim)
    yield "drop a required course", p

    p = plan.model_copy(deep=True)
    p.terms[0].items.extend(PlanItem(slot="FREE", credits=3, category="FREE") for _ in range(4))
    yield "exceed the cap", p

    p = plan.model_copy(deep=True)
    dup = next(i for i in p.terms[0].items if i.course_id)
    p.terms[-1].items.append(dup.model_copy())
    yield "schedule a course twice", p

    p = plan.model_copy(deep=True)
    p.terms[0].items.append(PlanItem(course_id="2110101", credits=3, category="ENG_BASIC"))
    yield "repeat a completed course", p

    p = plan.model_copy(deep=True)
    p.terms[0].items.append(PlanItem(course_id="9999999", credits=3, category="FREE"))
    yield "invent a course id", p


def test_mutated_plans_are_rejected():
    st, goal, plan = plan_for("y3-base", preferred_course_ids=AI)
    for what, mutated in _mutations(plan):
        mutated.plan_hash = mutated.compute_hash()
        assert not validate(SNAP, st, goal, mutated).valid, what


def test_prerequisite_order_violation_is_rejected():
    st, goal, plan = plan_for("y3-base", preferred_course_ids=AI)
    p = plan.model_copy(deep=True)
    loc = {i.course_id: (n, i) for n, t in enumerate(p.terms) for i in t.items if i.course_id}
    n476, i476 = loc["2110476"]
    n477, i477 = loc["2110477"]
    p.terms[n476].items.remove(i476)
    p.terms[n477].items.append(i476)   # same term as part II
    p.plan_hash = p.compute_hash()
    assert any("prerequisite 2110476" in e for e in validate(SNAP, st, goal, p).errors)


def test_tampered_plan_hash_is_rejected():
    st, goal, plan = plan_for("y4-final")
    plan.terms[0].items.pop()
    assert any("hash" in e for e in validate(SNAP, st, goal, plan).errors)


def test_low_cap_is_an_evidenced_blocker_with_witnessed_alternatives():
    st = load_persona("y3-base")
    goal = goal_for(st, default_cap=15)
    assert solve(SNAP, st, goal)["status"] == "INFEASIBLE"
    d = diagnose(SNAP, st, goal)
    kinds = {a["kind"] for a in d["alternatives"]}
    assert {"raise_caps", "allow_summer", "extend_horizon"} <= kinds
    raised = next(a for a in d["alternatives"] if a["kind"] == "raise_caps")["caps"]
    assert sum(raised.values()) - 15 * len(raised) == 2      # smallest increase that fits 49 remaining credits


def test_unknown_identity_data_needs_info():
    st = load_persona("y3-base")
    assert solve(SNAP, st, goal_for(st, must_take=["21105xx"]))["status"] == "NEED_INFO"
    st.records.append(st.records[0].model_copy(update={"course_id": "GEN-UNK-99", "category": None, "credits": 3}))
    assert solve(SNAP, st, goal_for(st))["status"] == "NEED_INFO"
    assert audit(SNAP, st)["unknown_completed_courses"] == ["GEN-UNK-99"]


def test_allocation_uses_small_courses_where_they_fit():
    courses = {"2110291": 1, "2110391": 1, "2110233": 1, "2110476": 3, "2110477": 3, "2110571": 3, "2110572": 3,
               "2110573": 3, "2110574": 3, "2110443": 3}
    totals, _ = allocate(SNAP, courses, [])
    assert totals["DEPT_ELECTIVE"] >= 18 and totals["FREE"] >= 6
