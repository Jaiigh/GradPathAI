"""Score a finished session against a test-set task (check vocabulary: docs/evaluation.md)."""
from __future__ import annotations

import re

from gradpath import terms as T
from gradpath.tools import validator
from gradpath.tools.audit import audit

IMPOSSIBLE = re.compile(r"infeasib|impossible|cannot be done|เป็นไปไม่ได้|ทำไม่ได้", re.I)
ID_RE = re.compile(r"\b\d{5}[0-9xX?]{2}\b")
THAI = re.compile(r"[฀-๿]")


def _plan(rt, s):
    return s.candidates.get(s.final_plan_id) if s.final_plan_id else None


def _agent_texts(s):
    return [i.text for i in s.items if i.role == "agent" and i.text]


def check(rt, s, c) -> tuple[bool, str]:
    snap, _ = rt.snap(s)
    plan = _plan(rt, s)
    courses = {i.course_id: (t.term, i.category) for t in plan.terms for i in t.items if i.course_id} if plan else {}
    name, arg = (c, None) if isinstance(c, str) else next(iter(c.items()))
    if name in ("plan_valid", "graduates_by_horizon", "caps_respected"):
        if not plan:
            return False, "no plan"
        v = validator.validate(snap, s.student, s.goal, plan)
        if name == "plan_valid":
            return v.valid, "; ".join(v.errors[:3])
        if name == "graduates_by_horizon":
            bad = [e for e in v.errors if "category" in e or "required" in e or "total credits" in e]
            return not bad and plan.terms[-1].term == s.goal.horizon_end, "; ".join(bad[:3])
        bad = [f"{t.term} {t.credits}>{t.cap}" for t in plan.terms if t.credits > t.cap]
        return not bad, ", ".join(bad)
    if name == "plan_valid_if_any":
        return (validator.validate(snap, s.student, s.goal, plan).valid if plan else True), ""
    if name == "no_plan":
        return plan is None, ""
    if name == "includes":
        missing = [x for x in arg if x not in courses]
        return not missing, f"missing {missing}"
    if name == "excludes":
        present = [x for x in arg if x in courses]
        return not present, f"present {present}"
    if name == "includes_any":
        return any(x in courses for x in arg), f"none of {arg}"
    if name == "in_semester":
        bad = [cid for cid, sem in arg.items() if cid not in courses or T.semester(courses[cid][0]) != sem]
        return not bad, f"{bad}"
    if name == "allocation":
        n = sum(1 for cid in arg["courses"] if cid in courses and courses[cid][1] == arg["category"])
        return n == arg["count"], f"{n} in {arg['category']}"
    if name == "asked_fields":
        first_solve = next((t.turn for t in s.turns if "solve_plan" in t.tools), 10 ** 6)
        asked = sorted({f for a in s.asked if a["kind"] == "clarify" and a["turn"] <= first_solve for f in a["fields"]})
        return asked == sorted(arg), f"asked {asked}"
    if name == "no_question":
        return not s.asked, f"asked {s.asked}"
    if name == "consent_before_change":
        approved = {e["card_id"] for e in s.consent_events if e["approved"]}
        ok = all(g.consent_refs and g.consent_refs[-1].consent_id in approved and g.consent_refs[-1].approved
                 for g in s.goal_history)
        versions = [g.goal_version for g in s.goal_history]
        return ok and versions == list(range(1, len(versions) + 1)), f"versions {versions}"
    if name == "declined":
        return any(i.kind == "decline" for i in s.items), ""
    if name == "no_unknown_ids":
        allowed = set(snap.courses) | {r.course_id for r in s.student.records}
        for p in rt.snap(s)[1].docs:
            if p.source_id in s.retrieved:
                allowed |= set(ID_RE.findall(p.text))
        bad = sorted({x for t in _agent_texts(s) for x in ID_RE.findall(t) if x not in allowed})
        return not bad, f"{bad}"
    if name == "no_impossibility_claim":
        return s.outcome != "EVIDENCED_BLOCKER" and not any(IMPOSSIBLE.search(t) for t in _agent_texts(s)), ""
    if name == "citations_valid":
        cites = [x for i in s.items for x in i.data.get("citations", [])]
        return all(x in s.retrieved for x in cites), f"{cites}"
    if name == "need_info_first":
        return bool(s.outcomes) and s.outcomes[0] == "NEED_INFO", f"{s.outcomes[:2]}"
    if name == "goal_version":
        return bool(s.goal) and s.goal.goal_version == arg, f"v{s.goal.goal_version if s.goal else None}"
    if name == "record_version":
        return s.student.record_version == arg, f"v{s.student.record_version}"
    if name == "caps_default":
        reg = snap.regulation("max_credits_regular")
        g = s.goal
        return bool(g) and (g.default_cap in (None, reg)) and all(v >= reg for t, v in g.caps.items()
                                                                  if not T.is_summer(t)), ""
    if name == "caps_at_most":
        regular = [t for t in plan.terms if t.kind == "regular"] if plan else []
        return bool(regular) and all(t.cap <= arg and t.credits <= arg for t in regular), \
            f"{[(t.term, t.cap) for t in regular]}"
    if name == "horizon_end":
        return bool(s.goal) and s.goal.horizon_end == arg, f"{s.goal.horizon_end if s.goal else None}"
    if name == "earned_credits":
        got = audit(snap, s.student)["earned_credits"]
        return got == arg, f"{got}"
    return False, f"unknown check {name}"


def score(rt, s, task) -> dict:
    exp = task["expected"]
    want = exp["final_state"] if isinstance(exp["final_state"], list) else [exp["final_state"]]
    state_ok = s.outcome in want
    results = [(c if isinstance(c, str) else next(iter(c)), *check(rt, s, c)) for c in exp["checks"]]
    failed = [f"{n}: {why}" for n, ok, why in results if not ok]
    processing = sum((t.ended or t.started) - t.started for t in s.turns)
    texts = _agent_texts(s)
    reply_lang = ("th" if THAI.search(texts[-1]) else "en") if texts else None
    return {"task_id": task["id"], "final_state": s.outcome, "expected_state": "|".join(want), "state_ok": state_ok,
            "checks_failed": failed, "technical_result": "PASS" if state_ok and not failed else "FAIL",
            "record_version": s.student.record_version, "goal_version": s.goal.goal_version if s.goal else None,
            "plan_id": s.final_plan_id, "plan_hash": s.candidates[s.final_plan_id].plan_hash if s.final_plan_id else None,
            "processing_s": round(processing, 2), "max_turn_s": round(max(((t.ended or t.started) - t.started
                                                                           for t in s.turns), default=0), 2),
            "tool_calls": sum(t.tool_calls for t in s.turns), "max_turn_tool_calls": max((t.tool_calls for t in s.turns),
                                                                                         default=0),
            "revisions": sum(t.revisions for t in s.turns), "llm_calls": sum(t.llm_calls for t in s.turns),
            "reply_lang": reply_lang, "lang_ok": reply_lang in (None, task["lang"]), "manual": exp.get("manual")}
