"""Rule snapshot: loading, content hash and lookups (decision D4: every item carries a status)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = ROOT / "data" / "snapshots"
DEFAULT_SNAPSHOT = "cp2566-internship-v2"
LEGACY_GENED = {"GE_SOC", "GE_HUM", "GE_INTER", "GE_SCI"}


@dataclass
class Snapshot:
    data: dict
    content_hash: str
    categories: dict = field(init=False)
    courses: dict = field(init=False)

    def __post_init__(self):
        self.categories = {c["id"]: c for c in self.data["categories"]}
        self.courses = self.data["courses"]

    @property
    def snapshot_id(self) -> str:
        return self.data["snapshot_id"]

    @property
    def total_credits(self) -> int:
        return self.data["program"]["total_credits"]

    def regulation(self, name: str):
        return self.data["regulations"][name]["value"]

    def required_courses(self) -> list[str]:
        return [c for c, v in self.courses.items() if v["kind"] == "required"]

    def slot_categories(self) -> list[str]:
        return [k for k, c in self.categories.items() if "slot_credits" in c]

    def category_id(self, category: str | None) -> str | None:
        """Old subject-group credits retain their meaning under the pooled revision."""
        return "GE" if "GE" in self.categories and category in LEGACY_GENED else category

    def earns_credit(self, grade: str | None) -> bool:
        return grade in self.regulation("earned_credit_grades")

    def offered_semesters(self, course_id: str) -> list[str] | None:
        """Semesters from the snapshot, or None when unknown (planning allowed, flagged unverified)."""
        o = self.courses[course_id]["offered"]
        return None if o["status"] == "unknown" else o["semesters"]

    def prereqs(self, course_id: str) -> list[str]:
        p = self.courses[course_id]["prereqs"]
        return [] if p["status"] == "unknown" else list(p["all_of"])

    def unverified_flags(self, course_id: str) -> list[str]:
        c = self.courses[course_id]
        flags = []
        if c["offered"]["status"] != "verified":
            flags.append("offering_unverified")
        if c["prereqs"]["status"] != "verified":
            flags.append("prereqs_unverified")
        return flags


def content_hash(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def load(snapshot_id: str = DEFAULT_SNAPSHOT, overlay: dict | None = None) -> Snapshot:
    """Load a snapshot; an overlay (used by test variants) is deep-merged into courses before hashing."""
    data = json.loads((SNAPSHOT_DIR / f"{snapshot_id}.json").read_text(encoding="utf-8"))
    if overlay:
        for cid, patch in overlay.get("courses", {}).items():
            data["courses"].setdefault(cid, {}).update(patch)
        data["snapshot_id"] = overlay.get("snapshot_id", data["snapshot_id"])
    return Snapshot(data, content_hash(data))
