"""Independent plan validator (the final gate). Plain Python; shares no code with the planner."""
from __future__ import annotations

from .. import terms as T
from ..contracts import GoalConstraints, PlanCandidate, StudentState, ValidationResult
from ..rules import allocate, deficits, standing
from ..snapshot import Snapshot


def validate(snap: Snapshot, student: StudentState, goal: GoalConstraints, plan: PlanCandidate) -> ValidationResult:
    errors, warnings = [], []
    st = standing(snap, student)
    if plan.snapshot_hash != snap.content_hash:
        errors.append("plan was built on a different snapshot")
    if plan.record_version != student.record_version:
        errors.append(f"plan record version {plan.record_version} != current {student.record_version}")
    if plan.goal_version != goal.goal_version:
        errors.append(f"plan goal version {plan.goal_version} != current {goal.goal_version}")
    if plan.compute_hash() != plan.plan_hash:
        errors.append("plan hash does not match plan content")
    if st.unknown_courses:
        errors.append(f"completed courses without a confirmed category: {st.unknown_courses}")

    expected_terms = T.span(student.next_term, goal.horizon_end)
    if [t.term for t in plan.terms] != expected_terms:
        errors.append(f"plan terms {[t.term for t in plan.terms]} != horizon terms {expected_terms}")

    reg_max, summer_max = snap.regulation("max_credits_regular"), snap.regulation("max_credits_summer")
    seen, done_before, planned_courses, slots = set(), set(st.completed), {}, []
    term_totals, unverified = {}, {}
    for pt in plan.terms:
        sem = T.semester(pt.term)
        allowed_cap = goal.caps.get(pt.term, summer_max if sem == "S" else (goal.default_cap or reg_max))
        allowed_cap = min(allowed_cap, summer_max if sem == "S" else reg_max)
        load = 0
        for it in pt.items:
            load += it.credits
            if it.course_id is None:
                cat = snap.categories.get(it.slot or "")
                if not cat or "slot_credits" not in cat or it.credits != cat["slot_credits"]:
                    errors.append(f"{pt.term}: invalid slot {it.slot}")
                elif sem == "S" and not goal.allow_summer:
                    errors.append(f"{pt.term}: summer slot without the student's consent to use summer")
                slots.append((it.slot, it.credits))
                continue
            c = it.course_id
            if c not in snap.courses:
                errors.append(f"{c}: unknown course id")
                continue
            if c == "2100301" and snap.data["policy"].get("internship"):
                fixed_term = T.label(student.entry_year + 2, "S")
                if pt.term != fixed_term:
                    errors.append(f"2100301: must be in Year 3 summer {fixed_term}; cannot move term")
            info = snap.courses[c]
            if it.credits != info["credits"]:
                errors.append(f"{c}: {it.credits} credits in plan, {info['credits']} in snapshot")
            if c in st.completed:
                errors.append(f"{c}: already completed")
            if c in seen:
                errors.append(f"{c}: scheduled twice")
            if c in goal.avoid:
                errors.append(f"{c}: the goal says to avoid this course")
            seen.add(c)
            offered = snap.offered_semesters(c)
            if offered is not None and sem not in offered:
                errors.append(f"{c}: not offered in semester {sem} ({pt.term})")
            if sem == "S" and not goal.allow_summer and offered != ["S"]:
                errors.append(f"{c}: placed in summer {pt.term} without the student's consent to use summer")
            for p in snap.prereqs(c):
                if p not in done_before:
                    errors.append(f"{c}: prerequisite {p} not completed before {pt.term}")
            for flag in snap.unverified_flags(c):
                unverified.setdefault(flag, []).append(c)
            if info["status"] == "conflict":
                warnings.append(f"{c}: sources disagree ({'; '.join(info['notes'])})")
            planned_courses[c] = info["credits"]
        if load > allowed_cap:
            errors.append(f"{pt.term}: {load} credits exceeds cap {allowed_cap}")
        term_totals[pt.term] = load
        done_before |= {it.course_id for it in pt.items if it.course_id}

    for c in snap.required_courses() + goal.must_take:
        if c not in st.completed and c not in planned_courses:
            errors.append(f"{c}: required course neither completed nor planned")
    fixed = list(st.external.values())
    fixed = [(cat, credits) for credits, cat in fixed] + slots
    totals, _ = allocate(snap, {**st.completed, **planned_courses}, fixed)
    for k, short in deficits(snap, totals).items():
        if short:
            errors.append(f"category {k}: {totals.get(k, 0)}/{snap.categories[k]['min_credits']} credits")
    total = sum(st.completed.values()) + sum(c for c, _ in st.external.values()) + sum(term_totals.values())
    if total < snap.total_credits:
        errors.append(f"total credits {total} < {snap.total_credits}")
    for flag, courses in sorted(unverified.items()):
        warnings.append(f"{len(courses)} planned courses: {flag.replace('_', ' ')}")
    return ValidationResult(plan_hash=plan.plan_hash, snapshot_id=snap.snapshot_id, record_version=student.record_version,
                            goal_version=goal.goal_version, valid=not errors, errors=errors,
                            warnings=sorted(set(warnings)), term_totals=term_totals, category_totals=totals,
                            total_credits=total)
