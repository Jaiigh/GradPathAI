"""Versioned data contracts (pitch v9 slide 7, extended for multi-term plans; decision D9)."""
from __future__ import annotations

import hashlib
import json
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["verified", "inferred", "unknown", "conflict"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- student record
class Evidence(Strict):
    page: int | None = None
    row: int | None = None
    text: str | None = None
    line: int | None = None


class Record(Strict):
    course_id: str
    title: str | None = None
    credits: int | None = None
    grade: str | None = None
    term: str
    category: str | None = None   # student-confirmed category for courses outside the snapshot
    evidence: Evidence | None = None


class UnresolvedField(Strict):
    record_index: int
    field: Literal["course_id", "grade", "credits", "category", "term"]
    reason: str
    candidates: list[str] = []


class StudentState(Strict):
    student_ref: str
    record_version: int = 1
    source_kind: Literal["persona", "pdf", "csv"] = "persona"
    source_sha256: str | None = None
    snapshot_id: str
    entry_year: int
    next_term: str
    records: list[Record]
    unresolved: list[UnresolvedField] = []
    confirmed: bool = False
    internship_completed: bool = False  # explicit student attestation, separate from PDF
    report: dict | None = None  # non-identifying extraction metadata and reconciliation


# ---------------------------------------------------------------- goal
class ConsentRef(Strict):
    consent_id: str
    change: dict
    approved: bool
    at: str


class GoalConstraints(Strict):
    goal_version: int = 1
    horizon_end: str
    caps: dict[str, int] = {}          # term label -> cap; missing terms use the regulation maximum
    default_cap: int | None = None     # student-wide cap for regular terms, if the student gave one
    allow_summer: bool = False
    must_take: list[str] = []
    avoid: list[str] = []
    interests: list[str] = []          # soft
    preferred_course_ids: list[str] = []  # soft, usually from retrieval
    consent_refs: list[ConsentRef] = []
    confirmed: bool = False

    HARD_FIELDS: ClassVar[tuple[str, ...]] = ("horizon_end", "caps", "default_cap", "allow_summer", "must_take", "avoid")


# ---------------------------------------------------------------- plan
class PlanItem(Strict):
    course_id: str | None = None       # a real course, or None for a category slot
    slot: str | None = None            # category id when this is a slot
    credits: int
    category: str
    flags: list[str] = []              # e.g. offering_unverified, prereqs_unverified


class PlanTerm(Strict):
    term: str
    kind: Literal["regular", "summer"]
    cap: int
    items: list[PlanItem]

    @property
    def credits(self) -> int:
        return sum(i.credits for i in self.items)


class PlanCandidate(Strict):
    plan_id: str
    snapshot_id: str
    snapshot_hash: str
    record_version: int
    goal_version: int
    terms: list[PlanTerm]
    solver: dict = Field(default_factory=dict)
    plan_hash: str = ""

    def compute_hash(self) -> str:
        payload = {"terms": [t.model_dump() for t in self.terms], "snapshot_hash": self.snapshot_hash,
                   "record_version": self.record_version, "goal_version": self.goal_version}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


class ValidationResult(Strict):
    plan_hash: str
    snapshot_id: str
    record_version: int
    goal_version: int
    valid: bool
    errors: list[str]
    warnings: list[str]
    term_totals: dict[str, int]
    category_totals: dict[str, int]
    total_credits: int
