"""audit tool: where the bound student stands against the snapshot."""
from __future__ import annotations

from .. import terms as T
from ..contracts import GoalConstraints, StudentState
from ..rules import allocate, deficits, standing
from ..snapshot import Snapshot


def audit(snap: Snapshot, student: StudentState, goal: GoalConstraints | None = None) -> dict:
    st = standing(snap, student)
    fixed = [(cat, credits) for credits, cat in st.external.values()]
    totals, _ = allocate(snap, dict(st.completed), fixed)
    horizon = goal.horizon_end if goal else T.end_of_year4(student.entry_year)
    earned = sum(st.completed.values()) + sum(c for c, _ in st.external.values())
    return {
        "earned_credits": earned,
        "credits_to_graduate": max(0, snap.total_credits - earned),
        "missing_required": [c for c in snap.required_courses() if c not in st.completed],
        "must_retake": [c for c in st.failed if snap.courses[c]["kind"] == "required"],
        "category_deficits": {k: v for k, v in deficits(snap, totals).items() if v},
        "unknown_completed_courses": st.unknown_courses,
        "terms_left": T.span(student.next_term, horizon),
    }
