"""Session state, persistence and traces. Sessions of real runs live under local/ (gitignored)."""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ..contracts import GoalConstraints, PlanCandidate, StudentState
from ..snapshot import ROOT

LOCAL = Path(os.environ.get("GRADPATH_LOCAL", ROOT / "local"))
TERMINAL = ("DONE", "EVIDENCED_BLOCKER", "NEED_INFO", "STOP_UNVERIFIED")


class Card(BaseModel):
    card_id: str
    kind: Literal["goal", "blocker"]
    data: dict
    status: Literal["pending", "approved", "declined", "superseded"] = "pending"


class Item(BaseModel):
    """One entry of the conversation as the UI shows it."""
    seq: int
    role: Literal["student", "agent", "system"]
    kind: str            # text | need_info | question | goal_card | plan | blocker_card | stop | decline | event
    text: str = ""
    data: dict = Field(default_factory=dict)
    at: float = Field(default_factory=time.time)


class TurnRecord(BaseModel):
    turn: int
    trigger: str
    started: float
    ended: float | None = None
    llm_calls: int = 0
    llm_s: float = 0.0
    tool_calls: int = 0
    tool_s: float = 0.0
    revisions: int = 0
    tools: list[str] = Field(default_factory=list)
    outcome: str | None = None
    reason: str | None = None


class Session(BaseModel):
    session_id: str
    created_at: float
    persona: str
    task_id: str | None = None
    fault: str | None = None
    overlay: dict | None = None
    snapshot_id: str
    snapshot_hash: str
    lang: Literal["th", "en"] = "th"
    student: StudentState
    goal: GoalConstraints | None = None
    goal_history: list[GoalConstraints] = Field(default_factory=list)
    cards: list[Card] = Field(default_factory=list)
    items: list[Item] = Field(default_factory=list)
    llm_messages: list[dict] = Field(default_factory=list)
    candidates: dict[str, PlanCandidate] = Field(default_factory=dict)
    blockers: dict[str, dict] = Field(default_factory=dict)
    retrieved: list[str] = Field(default_factory=list)
    asked: list[dict] = Field(default_factory=list)          # ask_user calls, for scoring and the trace
    consent_events: list[dict] = Field(default_factory=list)
    state: str = "VERIFY_INPUT"
    outcome: str | None = None
    outcomes: list[str] = Field(default_factory=list)
    final_plan_id: str | None = None
    queued: str | None = None
    turns: list[TurnRecord] = Field(default_factory=list)
    progress: list[dict] = Field(default_factory=list)
    busy: bool = False
    run_record: dict = Field(default_factory=dict)

    def add(self, role, kind, text="", **data) -> Item:
        item = Item(seq=len(self.items), role=role, kind=kind, text=text, data=data)
        self.items.append(item)
        return item

    def pending(self, kind: str | None = None) -> Card | None:
        return next((c for c in reversed(self.cards) if c.status == "pending" and (kind is None or c.kind == kind)), None)

    def supersede(self, kind: str):
        for c in self.cards:
            if c.kind == kind and c.status == "pending":
                c.status = "superseded"


def new_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]


class Store:
    """Session JSON files and append-only JSONL traces under local/."""

    def __init__(self, base: Path = LOCAL):
        self.sessions_dir, self.traces_dir = base / "sessions", base / "traces"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.traces_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def save(self, s: Session):
        path = self.sessions_dir / f"{s.session_id}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(s.model_dump_json(indent=1), encoding="utf-8")
        tmp.replace(path)

    def load(self, session_id: str) -> Session:
        return Session.model_validate_json((self.sessions_dir / f"{session_id}.json").read_text(encoding="utf-8"))

    def trace_path(self, session_id: str) -> Path:
        return self.traces_dir / f"{session_id}.jsonl"

    def trace(self, session_id: str, event: str, **data):
        line = json.dumps({"t": round(time.time(), 3), "event": event, **data}, ensure_ascii=False, default=str)
        with self._lock, open(self.trace_path(session_id), "a", encoding="utf-8") as f:
            f.write(line + "\n")
