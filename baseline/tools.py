"""GradPath deterministic tools: audit, retrieve_courses, solve_plan, validate_plan.

The LLM never sees or controls the student record, goal or rule snapshot directly:
the runtime binds them (Context) and the model only passes small arguments.
"""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import re
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------- context
@dataclass
class Context:
    rules: dict
    completed: dict          # course_id -> grade
    goal: dict
    snapshot_id: str = ""
    extras: dict = field(default_factory=dict)

    @classmethod
    def load(cls, rules_path: str | Path, transcript_csv: str | Path, goal: dict) -> "Context":
        rules = json.loads(Path(rules_path).read_text(encoding="utf-8"))
        completed = {}
        with open(transcript_csv, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["grade"].strip().upper() not in {"F", "W", "U"}:
                    completed[row["course_id"].strip()] = row["grade"].strip()
        return cls(rules=rules, completed=completed, goal=goal, snapshot_id=rules.get("snapshot_id", ""))

    @property
    def courses(self) -> dict:
        return self.rules["courses"]


def plan_hash(terms: list[list[str]], ctx: Context) -> str:
    payload = json.dumps({"terms": terms, "goal_version": ctx.goal.get("goal_version"),
                          "snapshot": ctx.snapshot_id}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ---------------------------------------------------------------- category allocation
def _allocate(course_ids: list[str], ctx: Context) -> tuple[bool, dict]:
    """Check category minimums; each course counts toward at most ONE permitted category.
    Brute force over multi-category courses (fine for small snapshots)."""
    mins = ctx.rules["category_minimums"]
    fixed, multi = {k: 0 for k in mins}, []
    for c in course_ids:
        cats = [k for k in ctx.courses[c]["categories"] if k in mins]
        if len(cats) == 1:
            fixed[cats[0]] += ctx.courses[c]["credits"]
        elif len(cats) > 1:
            multi.append((c, cats + [None]))
    best = dict(fixed)
    for choice in itertools.product(*[opts for _, opts in multi]) if multi else [()]:
        totals = dict(fixed)
        for (c, _), k in zip(multi, choice):
            if k:
                totals[k] += ctx.courses[c]["credits"]
        if all(totals[k] >= v for k, v in mins.items()):
            return True, totals
        best = totals
    return False, best


# ---------------------------------------------------------------- tools
def audit(ctx: Context) -> dict:
    done = list(ctx.completed)
    ok, totals = _allocate(done, ctx)
    mins = ctx.rules["category_minimums"]
    return {
        "completed": done,
        "missing_required": [c for c in ctx.rules["required_courses"] if c not in ctx.completed],
        "category_deficits": {k: max(0, v - totals.get(k, 0)) for k, v in mins.items()},
        "all_minimums_met": ok,
    }


def retrieve_courses(ctx: Context, query: str, k: int = 3) -> dict:
    """Keyword retrieval over course descriptions (baseline; swap for M15 RAG later)."""
    terms = re.findall(r"\w+", query.lower())
    hits = []
    for cid, c in ctx.courses.items():
        words = re.findall(r"\w+", f"{c['title']} {c['desc']}".lower())
        score = sum(words.count(t) for t in terms)
        if score:
            hits.append({"source_id": f"{ctx.snapshot_id}:{cid}", "course_id": cid,
                         "title": c["title"], "passage": c["desc"], "score": score})
    hits.sort(key=lambda h: -h["score"])
    return {"query": query, "results": hits[:k]}


def solve_plan(ctx: Context, preferred_course_ids: list[str] | None = None,
               time_limit_s: float = 10.0) -> dict:
    """CP-SAT over x[c,t]. Hard: unique, required, prereq order, cap, offering, categories.
    Soft: maximise preferred courses, then minimise total credits."""
    from ortools.sat.python import cp_model

    pref = set(preferred_course_ids or [])
    unknown_pref = sorted(pref - set(ctx.courses))
    terms = ctx.goal["terms"]
    T = range(len(terms))
    cand = [c for c in ctx.courses if c not in ctx.completed]

    def build(relax_cap=False, relax_finish=False):
        m = cp_model.CpModel()
        x = {(c, t): m.NewBoolVar(f"x_{c}_{t}") for c in cand for t in T}
        for c in cand:
            m.Add(sum(x[c, t] for t in T) <= 1)
            for t in T:
                if terms[t]["semester"] not in ctx.courses[c]["offered"]:
                    m.Add(x[c, t] == 0)
            for p in ctx.courses[c]["prereqs"]:
                if p in ctx.completed:
                    continue
                for t in T:
                    before = [x[p, s] for s in T if s < t] if p in cand else []
                    m.Add(x[c, t] <= sum(before)) if before else m.Add(x[c, t] == 0)
        for c in ctx.rules["required_courses"] + list(ctx.goal.get("must_take", [])):
            if c in cand and not relax_finish:
                m.Add(sum(x[c, t] for t in T) == 1)
        if not relax_cap:
            for t in T:
                m.Add(sum(ctx.courses[c]["credits"] * x[c, t] for c in cand) <= terms[t]["cap"])
        if ctx.goal.get("finish_by_horizon") and not relax_finish:
            mins = ctx.rules["category_minimums"]
            taken = {c: 1 for c in ctx.completed if c in ctx.courses}
            alloc = {}
            for c in list(taken) + cand:
                for k in ctx.courses[c]["categories"]:
                    if k in mins:
                        alloc[c, k] = m.NewBoolVar(f"a_{c}_{k}")
            for c in list(taken) + cand:
                ks = [alloc[c, k] for k in ctx.courses[c]["categories"] if (c, k) in alloc]
                if not ks:
                    continue
                active = 1 if c in taken else sum(x[c, t] for t in T)
                m.Add(sum(ks) <= active)
            for k, v in mins.items():
                m.Add(sum(ctx.courses[c]["credits"] * a for (c, kk), a in alloc.items() if kk == k) >= v)
        score = sum(100 * x[c, t] for c in cand if c in pref for t in T) \
            - sum(ctx.courses[c]["credits"] * x[c, t] for c in cand for t in T)
        m.Maximize(score)
        return m, x

    def run(**kw):
        m, x = build(**kw)
        s = cp_model.CpSolver()
        s.parameters.max_time_in_seconds = time_limit_s
        s.parameters.num_workers = 1
        s.parameters.random_seed = 42
        st = s.Solve(m)
        return st, s, x

    st, s, x = run()
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        plan = [[c for c in cand if s.Value(x[c, t])] for t in T]
        return {"status": "PLAN", "terms": plan,
                "preferred_scheduled": sorted(c for c in pref if any(c in p for p in plan)),
                "unknown_preferred_ids": unknown_pref}
    if st == cp_model.INFEASIBLE:
        conflicts = []
        if run(relax_cap=True)[0] in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            conflicts.append("term credit cap is too low for the required courses")
        if run(relax_finish=True)[0] in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            conflicts.append("requirements cannot all be completed within the horizon "
                             "(prerequisite order / offerings / categories)")
        return {"status": "INFEASIBLE", "scoped_conflicts": conflicts or ["unidentified combination"],
                "modeled_constraints": ["unique", "required", "prereq", "cap", "offering", "categories"]}
    return {"status": "UNKNOWN", "reason": f"solver status {s.StatusName(st)} within {time_limit_s}s"}


def validate_plan(ctx: Context, terms: list[list[str]]) -> dict:
    """Independent pure check (no solver). Recomputes everything from trusted context."""
    errors, gt = [], ctx.goal["terms"]
    if len(terms) != len(gt):
        errors.append(f"plan has {len(terms)} terms, goal has {len(gt)}")
    seen, scheduled_before = set(), set(ctx.completed)
    for t, courses in enumerate(terms[: len(gt)]):
        load = 0
        for c in courses:
            if c not in ctx.courses:
                errors.append(f"{c}: unknown course id"); continue
            if c in ctx.completed:
                errors.append(f"{c}: already completed")
            if c in seen:
                errors.append(f"{c}: scheduled twice")
            seen.add(c)
            if gt[t]["semester"] not in ctx.courses[c]["offered"]:
                errors.append(f"{c}: not offered in semester {gt[t]['semester']} ({gt[t]['label']})")
            for p in ctx.courses[c]["prereqs"]:
                if p not in scheduled_before:
                    errors.append(f"{c}: prerequisite {p} not completed before {gt[t]['label']}")
            load += ctx.courses[c]["credits"]
        if load > gt[t]["cap"]:
            errors.append(f"{gt[t]['label']}: {load} credits exceeds cap {gt[t]['cap']}")
        scheduled_before |= {c for c in courses if c in ctx.courses}
    for c in ctx.rules["required_courses"] + list(ctx.goal.get("must_take", [])):
        if c not in scheduled_before:
            errors.append(f"{c}: required course neither completed nor scheduled")
    ok_cat, totals = _allocate([c for c in scheduled_before if c in ctx.courses], ctx)
    if ctx.goal.get("finish_by_horizon") and not ok_cat:
        mins = ctx.rules["category_minimums"]
        errors.append("category minimums not met: " + ", ".join(
            f"{k} {totals.get(k, 0)}/{v}" for k, v in mins.items() if totals.get(k, 0) < v))
    return {"valid": not errors, "errors": errors,
            "recomputed_totals": {gt[i]["label"]: sum(ctx.courses[c]["credits"] for c in ts if c in ctx.courses)
                                  for i, ts in enumerate(terms[: len(gt)])},
            "plan_hash": plan_hash(terms, ctx), "snapshot_id": ctx.snapshot_id,
            "goal_version": ctx.goal.get("goal_version")}


# ---------------------------------------------------------------- schemas for the LLM
def _fn(name, desc, props, required):
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": {
        "type": "object", "properties": props, "required": required, "additionalProperties": False}}}


TERMS_SCHEMA = {"type": "array", "items": {"type": "array", "items": {"type": "string"}},
                "description": "One list of course IDs per term, in order."}

TOOL_SCHEMAS = [
    _fn("audit", "Return missing required courses and category deficits for the bound student.", {}, []),
    _fn("retrieve_courses", "Search course descriptions. Use to map interests (e.g. 'AI') to course IDs.",
        {"query": {"type": "string"}}, ["query"]),
    _fn("solve_plan", "Run the constraint planner. Pass course IDs the student prefers.",
        {"preferred_course_ids": {"type": "array", "items": {"type": "string"}}}, ["preferred_course_ids"]),
    _fn("validate_plan", "Check a draft plan and get errors to fix.", {"terms": TERMS_SCHEMA}, ["terms"]),
    _fn("submit_final", "Submit the final plan with a short explanation citing source IDs. "
        "Use status 'blocker' with an empty plan if no valid plan exists.",
        {"status": {"type": "string", "enum": ["plan", "blocker"]}, "terms": TERMS_SCHEMA,
         "explanation": {"type": "string"}}, ["status", "terms", "explanation"]),
]
ALLOWED_ARGS = {t["function"]["name"]: set(t["function"]["parameters"]["properties"]) for t in TOOL_SCHEMAS}


def execute(name: str, args: dict, ctx: Context) -> dict:
    """Allowlist + strict-argument dispatcher (M6/M7 role)."""
    if name not in ALLOWED_ARGS:
        return {"error": f"unknown tool '{name}'"}
    extra = set(args) - ALLOWED_ARGS[name]
    if extra:
        return {"error": f"unexpected arguments {sorted(extra)} for {name}"}
    if name == "audit":
        return audit(ctx)
    if name == "retrieve_courses":
        return retrieve_courses(ctx, str(args.get("query", "")))
    if name == "solve_plan":
        return solve_plan(ctx, list(args.get("preferred_course_ids") or []))
    if name == "validate_plan":
        return validate_plan(ctx, args.get("terms") or [])
    raise AssertionError(name)  # submit_final is handled by the runtime
