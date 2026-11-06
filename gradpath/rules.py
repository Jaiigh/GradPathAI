"""Plain-Python rule evaluation shared by audit and the validator (never by the planner).

Keeping the validator free of planner code is what makes the final gate an independent check.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import StudentState
from .snapshot import Snapshot

# Fill order for flexible courses: most restrictive category first.
FLEX_ORDER = ("CORE_ELECTIVE", "MULTI_21C", "DEPT_ELECTIVE", "FREE")


@dataclass
class Standing:
    completed: dict[str, int] = field(default_factory=dict)       # course_id -> credits (earned once)
    external: dict[str, tuple[int, str]] = field(default_factory=dict)  # course_id -> (credits, category)
    failed: list[str] = field(default_factory=list)               # attempted, never passed
    unknown_courses: list[str] = field(default_factory=list)      # outside the snapshot, no category


def standing(snap: Snapshot, student: StudentState) -> Standing:
    st = Standing()
    attempted = set()
    for r in student.records:
        attempted.add(r.course_id)
        if not snap.earns_credit(r.grade):
            continue
        if r.course_id in snap.courses:
            st.completed[r.course_id] = r.credits if r.credits is not None else snap.courses[r.course_id]["credits"]
        elif r.category and r.credits is not None:
            st.external[r.course_id] = (r.credits, snap.category_id(r.category))
        else:
            st.unknown_courses.append(r.course_id)
    if snap.data["policy"].get("internship") and student.internship_completed:
        st.completed.setdefault("2100301", snap.courses["2100301"]["credits"])
    passed = set(st.completed) | set(st.external)
    st.failed = sorted(c for c in attempted - passed if c in snap.courses)
    return st


def allowed_categories(snap: Snapshot, course_id: str) -> list[str]:
    return list(snap.courses[course_id]["categories"])


def _min_cover(items: list[tuple[str, int]], need: int) -> list[str]:
    """Smallest-total subset of (course, credits) reaching at least `need` credits; all items if none does."""
    if need <= 0:
        return []
    top = need + max(c for _, c in items) if items else 0
    best: dict[int, list[str]] = {0: []}
    for cid, credits in sorted(items, key=lambda i: (-i[1], i[0])):
        for total, chosen in sorted(best.items(), reverse=True):
            nt = total + credits
            if nt <= top and nt not in best:
                best[nt] = chosen + [cid]
    reach = [t for t in best if t >= need]
    return best[min(reach)] if reach else [cid for cid, _ in items]


def allocate(snap: Snapshot, courses: dict[str, int], fixed: list[tuple[str, int]]) -> tuple[dict[str, int], dict[str, str]]:
    """Assign each course's credits to one permitted category; fixed items (slots, external records) count as given.

    Categories are filled in FLEX_ORDER with the smallest-total subset of the remaining flexible courses, and every
    leftover goes to free electives. This is exact for this curriculum's nested categories (core-level electives may
    count as department electives, and every flexible course may count as a free elective).
    """
    mins = {k: c["min_credits"] for k, c in snap.categories.items()}
    totals = {k: 0 for k in mins}
    assignment: dict[str, str] = {}
    for cat, credits in fixed:
        cat = snap.category_id(cat)
        totals[cat] = totals.get(cat, 0) + credits
    flexible = {}
    for cid, credits in courses.items():
        cats = allowed_categories(snap, cid)
        if len(cats) == 1:
            totals[cats[0]] += credits
            assignment[cid] = cats[0]
        else:
            flexible[cid] = (credits, cats)
    for cat in FLEX_ORDER:
        if cat not in mins:
            continue
        pool = [(cid, cr) for cid, (cr, cats) in flexible.items() if cid not in assignment and cat in cats]
        chosen = [cid for cid, _ in pool] if cat == "FREE" else _min_cover(pool, mins[cat] - totals[cat])
        for cid in chosen:
            totals[cat] += flexible[cid][0]
            assignment[cid] = cat
    return totals, assignment


def deficits(snap: Snapshot, totals: dict[str, int]) -> dict[str, int]:
    return {k: max(0, c["min_credits"] - totals.get(k, 0)) for k, c in snap.categories.items()}


def internship_info(snap: Snapshot, student: StudentState) -> dict | None:
    if not snap.data["policy"].get("internship"):
        return None
    from . import terms as T
    term = T.label(student.entry_year + 2, "S")
    reported = any(r.course_id == "2100301" and snap.earns_credit(r.grade) for r in student.records)
    completed = reported or student.internship_completed
    overdue = T.key(student.next_term) > T.key(term) and not completed
    return {"term": term, "reported": reported, "completed": completed,
            "attested": student.internship_completed, "needs_review": overdue,
            "supplemental_credits": 2 if student.internship_completed and not reported else 0,
            "message": (f"ไม่พบผลผ่านวิชา 2100301 ซึ่งต้องลงซัมเมอร์ปี 3 ({term}) และพ้นเทอมนี้แล้ว "
                        "กรุณายืนยันว่าลงทะเบียนและผ่านแล้ว หากยังไม่ผ่านให้ตรวจสอบกับภาควิชา ระบบจะไม่ย้ายเทอมให้อัตโนมัติ") if overdue else
                       f"วิชา 2100301 ต้องลงซัมเมอร์ปี 3 ({term}) เท่านั้น ไม่สามารถเปลี่ยนเทอมได้"}
