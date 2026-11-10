"""Agent runtime v2: interactive state machine, tool dispatch, budget, final gate and traces.

States (docs/architecture.md): VERIFY_INPUT -> CLARIFY -> ACT -> WAIT_USER | FINAL_GATE -> DONE | EVIDENCED_BLOCKER,
plus NEED_INFO and STOP_UNVERIFIED. The LLM never edits trusted state: the record changes only through record
decisions, the goal only through approved cards, and every plan shown is the stored candidate that passed the gate.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone

from .. import snapshot as snapshot_mod, terms as T
from ..contracts import ConsentRef, GoalConstraints, StudentState
from ..fixtures import load_persona
from ..ingest.cr60 import reconciliation, refresh_categories
from ..rules import allocate, internship_info, standing
from ..snapshot import ROOT, Snapshot
from ..tools import planner, validator
from ..tools.audit import audit
from ..tools.retrieval import Index, retrieve
from . import llm as llm_mod
from .prompts import EXPLAIN, GOAL_DRAFT, STATE, SYSTEM, SYSTEM_B, lang_of, text
from .session import Card, Session, Store, TurnRecord, new_id
from .tools import ARGS, ProposeGoalArgs, RetrieveArgs, SolveArgs, SubmitArgs, ValidateArgs, parse, schemas

BUDGET = {"tool_calls": 8, "revisions": 2, "seconds": 120.0}
SOLVER_TIME_LIMIT_S = 10.0
ID_RE = re.compile(r"\b\d{5}[0-9xX?]{2}\b")
NUM_RE = re.compile(r"\d+")
THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
THINK_RE = re.compile(r"<think>.*?</think>", re.S)
TEST_SET = ROOT / "data" / "test_set.jsonl"
PERSONA_LABELS = {
    "y1-start": "นิสิตปี 1 (เพิ่งจบภาค 1)", "y2-mid": "นิสิตปี 2", "y3-base": "นิสิตปี 3",
    "y3-retake-open": "นิสิตปี 3 (มีวิชาที่ได้ F)", "y3-retake-passed": "นิสิตปี 3 (เคยเรียนซ้ำ)",
    "y3-unclear-grade": "นิสิตปี 3 (เกรดบางวิชาอ่านไม่ออก)", "y3-unclear-id": "นิสิตปี 3 (รหัสวิชาบางตัวอ่านไม่ออก)",
    "y4-final": "นิสิตปี 4 (เทอมสุดท้าย)",
}
ARMS = ("A", "B", "C")      # experiment arms (docs/evaluation.md); C is the product
LETTERS = re.compile(r"[A-Za-z\u0e00-\u0e7f]")
TITLE_ID = re.compile(r"((?:[A-Z][\w&-]*|[IVX]+|and|of|for|in|to|the)(?:\s+(?:[A-Z][\w&-]*|[IVX]+|and|of|for|in|to|the))*)"
                      r"\s*\(\s*(\d{7})\s*\)")
VAGUE = {"caps": re.compile(r"ไม่หนัก|เบา ?ๆ|ไม่เยอะ|สบาย ?ๆ|\blight\b|not too heavy|\beasy\b|relaxed", re.I),
         "horizon": re.compile(r"จบเร็ว|จบไว|เร็วที่สุด|ก่อนกำหนด|finish early|graduate early|graduate fast|as soon as", re.I)}
ONE_CATEGORY = re.compile(r"หมวดเดียว|เพียงหมวด|หนึ่งหมวด|อย่างใดอย่างหนึ่ง|นับซ้ำไม่ได้|ไม่สามารถนับ|ไม่ได้ในเวลาเดียวกัน|"
                          r"ไม่ได้พร้อมกัน|only one|exactly one|one category|not both|cannot count|either", re.I)
BOTH_AT_ONCE = re.compile(r"ได้ในเวลาเดียวกัน|ได้พร้อมกัน|นับได้ทั้ง|at the same time|simultaneously|counts? (?:toward|for) both", re.I)
# Interests must be topics the student stated; each group lists words that count as the same topic.
TOPIC_WORDS = [{"ai", "artificial intelligence", "ปัญญาประดิษฐ์", "เอไอ", "machine learning", "ml"},
               {"systems", "system", "ระบบ"}, {"security", "cyber", "ความปลอดภัย", "ความมั่นคง"},
               {"data", "ข้อมูล"}, {"network", "networks", "เครือข่าย"}, {"software", "ซอฟต์แวร์"},
               {"cloud", "คลาวด์"}, {"graphics", "กราฟิก"}, {"hardware", "ฮาร์ดแวร์"}]
GENERIC_WORDS = {"computer", "computing", "engineering", "course", "courses", "subject", "with", "from", "study"}
ALT_LABELS = {"raise_caps": ("เพิ่มเพดานหน่วยกิต", "Raise the credit cap"),
              "allow_summer": ("ใช้ภาคฤดูร้อน", "Use summer terms"),
              "extend_horizon": ("ขยายเวลาจบ", "Extend the finishing term")}


class Stop(Exception):
    """End the turn in STOP_UNVERIFIED (budget, timeout, model failure, solver UNKNOWN, gate exhausted)."""

    def __init__(self, key: str, **kw):
        super().__init__(key)
        self.key, self.kw = key, kw


def load_tasks() -> dict[str, dict]:
    if not TEST_SET.exists():
        return {}
    lines = TEST_SET.read_text(encoding="utf-8").splitlines()
    return {t["id"]: t for t in map(json.loads, filter(None, lines))}


def _git_commit() -> str:
    try:
        rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                             timeout=5).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True,
                               timeout=5).stdout.strip()
        return rev + ("+dirty" if dirty else "")
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _gpu() -> str:
    if sys.platform == "darwin":
        return _apple_gpu()
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        return out or "none"
    except (OSError, subprocess.SubprocessError):
        return "none"


def _apple_gpu() -> str:
    """Apple silicon: chip, GPU cores and unified memory, e.g. "Apple M4, 10-core GPU, 24 GB unified"."""
    try:
        disp = subprocess.run(["system_profiler", "SPDisplaysDataType"], capture_output=True, text=True,
                              timeout=10).stdout
        mem = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return "none"
    chip = re.search(r"Chipset Model:\s*(.+)", disp)
    cores = re.search(r"Total Number of Cores:\s*(\d+)", disp)
    if not chip or "Apple" not in chip.group(1):
        return "none"
    parts = [chip.group(1).strip()]
    if cores:
        parts.append(f"{cores.group(1)}-core GPU")
    if mem.strip().isdigit():
        parts.append(f"{int(mem) // 2**30} GB unified")
    return ", ".join(parts)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Ctx:
    """Per-turn accounting."""

    def __init__(self, rec: TurnRecord):
        self.rec, self.t0, self.need_info, self.end = rec, time.monotonic(), False, None
        self.blocker = None      # blocker_id from an INFEASIBLE solve in this turn, until a plan is found

    def remaining(self) -> float:
        return BUDGET["seconds"] - (time.monotonic() - self.t0)


class Runtime:
    def __init__(self, llm=None, store: Store | None = None, solver_time_limit_s: float = SOLVER_TIME_LIMIT_S,
                 arm: str = "C"):
        if arm not in ARMS:
            raise ValueError(f"unknown arm {arm!r}")
        self.arm = arm
        self.llm = llm or llm_mod.OllamaLLM()
        self.store = store or Store()
        self.solver_time_limit_s = solver_time_limit_s
        self.sessions: dict[str, Session] = {}
        self.locks: dict[str, threading.Lock] = {}
        self._snaps: dict[str, tuple[Snapshot, Index]] = {}
        self.tool_names = [n for n in ARGS if not (arm == "B" and n == "retrieve_courses")]
        self.tool_schemas = schemas(self.tool_names)
        self.system = SYSTEM_B if arm == "B" else SYSTEM
        self.static = {"arm": arm, "git_commit": _git_commit(), "gpu": _gpu(),
                       "test_set_sha256": hashlib.sha256(TEST_SET.read_bytes()).hexdigest() if TEST_SET.exists() else None}

    # ------------------------------------------------------------ sessions
    def snap(self, s: Session) -> tuple[Snapshot, Index]:
        key = s.snapshot_id + json.dumps(s.overlay, sort_keys=True)
        if key not in self._snaps:
            snap = snapshot_mod.load(s.snapshot_id, s.overlay)
            self._snaps[key] = (snap, Index(snap))
        return self._snaps[key]

    def create_session(self, persona: str | None = None, task_id: str | None = None, fault: str | None = None,
                       overlay: dict | None = None, student: StudentState | None = None) -> Session:
        snapshot_id = student.snapshot_id if student else snapshot_mod.DEFAULT_SNAPSHOT
        if task_id:
            task = load_tasks()[task_id]
            persona, snapshot_id = task["persona"], task["snapshot_id"]
            inject = task.get("inject") or {}
            fault, overlay = inject.get("fault", fault), inject.get("snapshot_overlay", overlay)
        if fault not in (None, "planner_timeout", "model_unavailable"):
            raise ValueError(f"unknown fault {fault!r}")
        student = student or load_persona(persona)
        student.snapshot_id = snapshot_id
        persona = persona or "uploaded-report"
        s = Session(session_id=new_id(), created_at=time.time(), persona=persona, task_id=task_id, fault=fault,
                    overlay=overlay, snapshot_id=snapshot_id, snapshot_hash="", student=student)
        snap, _ = self.snap(s)
        s.snapshot_hash = snap.content_hash
        s.state = "VERIFY_INPUT"
        s.run_record = {**self.static, **llm_mod.model_info(getattr(self.llm, "model", llm_mod.MODEL)),
                        "llm_options": llm_mod.OPTIONS, "budget": BUDGET, "session_id": s.session_id,
                        "task_id": task_id, "persona": persona, "fault": fault, "overlay": bool(overlay),
                        "snapshot_id": snapshot_id, "snapshot_hash": snap.content_hash, "started_at": _now()}
        self.sessions[s.session_id] = s
        self.locks[s.session_id] = threading.Lock()
        self.store.trace(s.session_id, "session_created", run_record=s.run_record)
        self.store.save(s)
        return s

    def replace_report(self, session_id: str, student: StudentState) -> Session:
        s = self.get(session_id)
        student.student_ref = s.student.student_ref
        student.record_version = s.student.record_version + 1
        s.student = student
        s.persona, s.task_id, s.fault = "uploaded-report", None, None
        s.overlay = None
        s.snapshot_id = student.snapshot_id
        s.snapshot_hash = self.snap(s)[0].content_hash
        s.run_record.update({"persona": s.persona, "task_id": None, "fault": None, "overlay": False,
                             "snapshot_id": s.snapshot_id, "snapshot_hash": s.snapshot_hash})
        s.goal = None
        s.goal_history = []
        s.final_plan_id = None
        s.candidates.clear()
        s.blockers.clear()
        s.llm_messages.clear()
        s.retrieved.clear()
        s.queued = None
        for card in s.cards:
            if card.status == "pending":
                card.status = "superseded"
        for item in s.items:
            if item.kind == "plan":
                item.data["stale"] = True
        s.state, s.outcome = "VERIFY_INPUT", None
        s.add("system", "event", "อัปโหลดรายงานใหม่แล้ว กรุณาตรวจและยืนยันระเบียนอีกครั้ง แผนเดิมไม่ใช่แผนปัจจุบัน")
        self.store.trace(session_id, "report_replaced", record_version=student.record_version,
                         source_sha256=student.source_sha256)
        self._save(s)
        return s

    def get(self, session_id: str) -> Session:
        if session_id not in self.sessions:
            self.sessions[session_id] = self.store.load(session_id)
            self.locks[session_id] = threading.Lock()
            restored = self.sessions[session_id]
            if restored.busy:
                restored.busy = False
                restored.progress = []
                restored.state = restored.outcome = "STOP_UNVERIFIED"
                restored.add("system", "stop", "เซิร์ฟเวอร์หยุดระหว่างทำงาน กรุณาส่งคำขออีกครั้ง / The server stopped during a turn. Please retry.")
                self._save(restored)
            if restored.student.source_kind == "pdf" and restored.snapshot_id in {"cp2566-v0", "cp2566-gened-v1"}:
                self._upgrade_gened(restored)
        return self.sessions[session_id]

    def _upgrade_gened(self, s: Session):
        """Carry uploaded records into D18; old UAT sessions stay bound to their snapshot."""
        previous = {"snapshot_id": s.snapshot_id, "snapshot_hash": s.snapshot_hash}
        s.snapshot_id = s.student.snapshot_id = snapshot_mod.DEFAULT_SNAPSHOT
        s.overlay = None
        snap, _ = self.snap(s)
        s.snapshot_hash = snap.content_hash
        for record in s.student.records:
            record.category = snap.category_id(record.category)
        for unresolved in s.student.unresolved:
            if unresolved.field == "category":
                unresolved.candidates = snap.slot_categories()
        s.student.record_version += 1
        s.final_plan_id = None
        s.candidates.clear()
        s.blockers.clear()
        s.llm_messages.clear()
        s.retrieved.clear()
        s.queued = None
        for card in s.cards:
            if card.status == "pending":
                card.status = "superseded"
        for item in s.items:
            if item.kind == "plan":
                item.data["stale"] = True
        s.state = "CLARIFY" if s.student.confirmed else "VERIFY_INPUT"
        s.outcome = None
        s.run_record.update(snapshot_id=s.snapshot_id, snapshot_hash=s.snapshot_hash)
        s.add("system", "event", "ปรับกฎเป็น GenEd รวม 12 หน่วยกิตแล้ว หน่วยกิตใน 4 หมวดเดิมนับรวมกัน เพิ่มกฎฝึกงาน 2100301 เฉพาะซัมเมอร์ปี 3 แผนเดิมต้องจัดใหม่ตามกฎนี้")
        self.store.trace(s.session_id, "curriculum_updated", previous=previous,
                         snapshot_id=s.snapshot_id, snapshot_hash=s.snapshot_hash,
                         record_version=s.student.record_version)
        self._save(s)

    def lock(self, session_id: str) -> threading.Lock:
        self.get(session_id)
        return self.locks[session_id]

    def _save(self, s: Session):
        self.store.save(s)

    def _end(self, s: Session, outcome: str, ctx: Ctx | None = None, reason: str | None = None):
        s.outcome = outcome
        s.outcomes.append(outcome)
        s.state = outcome
        if ctx:
            ctx.end = outcome
            ctx.rec.outcome, ctx.rec.reason = outcome, reason
        self.store.trace(s.session_id, "outcome", outcome=outcome, reason=reason,
                         record_version=s.student.record_version, goal_version=s.goal.goal_version if s.goal else None)

    # ------------------------------------------------------------ entry points (callers hold the session lock)
    def message(self, session_id: str, msg: str) -> Session:
        s = self.get(session_id)
        msg = msg.strip()[:2000]
        if LETTERS.search(msg):      # a reply of digits only ("2110415", "18") keeps the conversation language
            s.lang = lang_of(msg)
        s.add("student", "text", msg)
        self.store.trace(s.session_id, "student_message", text=msg)
        if not s.student.confirmed:
            s.queued = msg
            if s.student.unresolved:
                s.add("system", "need_info", text("need_info_record", s.lang, items=self._unresolved_text(s)))
                self._end(s, "NEED_INFO", reason="record has unresolved identity fields")
            else:
                s.add("system", "text", text("confirm_records", s.lang))
                self._end(s, "WAIT_USER", reason="records not confirmed")
            self._save(s)
            return s
        self._run_agent(s, msg)
        return s

    def record(self, session_id: str, resolve: list[dict], confirm: bool, profile: dict | None = None) -> Session:
        s = self.get(session_id)
        snap, _ = self.snap(s)
        st = s.student.model_copy(deep=True)  # failed decisions must not partially mutate trusted state
        if st.confirmed:
            raise ValueError("records are already confirmed")
        changed = []
        for r in resolve:
            idx, field, value = r.get("record_index"), r.get("field"), str(r.get("value", "")).strip()
            u = next((u for u in st.unresolved if u.record_index == idx and u.field == field), None)
            if u is None:
                raise ValueError(f"record {idx} has no unresolved field {field!r}")
            if field == "grade" and value not in snap.data["grades"]:
                raise ValueError(f"{value!r} is not a grade in the snapshot")
            if field == "course_id" and value not in snap.courses:
                raise ValueError(f"{value!r} is not a course ID in the snapshot")
            if field == "category" and value not in snap.slot_categories():
                raise ValueError("Choose a supported elective category.")
            if field == "credits":
                if not value.isdigit() or (u.candidates and value not in u.candidates):
                    raise ValueError("Confirm the credit value printed in the report.")
                value = int(value)
            if field == "term":
                T.parse(value)
            st.records[idx] = st.records[idx].model_copy(update={field: value})
            st.unresolved = [x for x in st.unresolved if x is not u]
            changed.append({"record_index": idx, "field": field, "value": value})
        if st.report:
            if profile:
                entry = profile["entry_year"]
                next_term = profile["next_term"]
                T.parse(next_term)
                if not 2566 <= entry <= T.parse(st.report["last_term"])[0]:
                    raise ValueError("Check the admission year (B.E.); this build supports CP 2566 onward.")
                if not T.key(st.report["last_term"]) < T.key(next_term) <= T.key(T.label(entry + 7, "2")):
                    raise ValueError("Planning must start after the last reported semester, within eight academic years of admission.")
                if not profile["confirmed"]:
                    raise ValueError("Confirm CP 2566 and the academic history before planning.")
                if (st.entry_year, st.next_term) != (entry, next_term):
                    st.internship_completed = False  # changed timeline needs a fresh attestation
                st.entry_year, st.next_term = entry, next_term
                st.report["profile_confirmed"] = True
                changed.append({"profile": profile})
            refresh_categories(st, snap)
            st.report["reconciliation_errors"] = reconciliation(st, snap)
            if confirm and (not st.report["profile_confirmed"] or st.report["reconciliation_errors"]):
                raise ValueError("Confirm the planning details and resolve report credit mismatches before continuing.")
        if confirm and st.unresolved:
            raise ValueError("some record fields are still unresolved")
        if changed:
            st.record_version += 1
            self.store.trace(s.session_id, "record_resolved", changes=changed, record_version=st.record_version)
        if confirm:
            st.confirmed = True
            s.student = st
            s.state = "CLARIFY"
            s.add("system", "event", text("record_confirmed", s.lang, v=st.record_version))
            self.store.trace(s.session_id, "record_confirmed", record_version=st.record_version)
            if s.queued:
                queued, s.queued = s.queued, None
                self._run_agent(s, queued)
                return s
        s.student = st
        self._save(s)
        return s

    def internship_decision(self, session_id: str, completed: bool) -> Session:
        s = self.get(session_id)
        info = internship_info(self.snap(s)[0], s.student)
        if not info:
            raise ValueError("This snapshot does not support supplemental internship confirmation")
        if completed and T.key(s.student.next_term) <= T.key(info["term"]):
            raise ValueError("ยืนยันผ่านได้หลังซัมเมอร์ปี 3 เท่านั้น กรุณาตรวจเทอมเริ่มวางแผน")
        if s.student.internship_completed == completed:
            return s
        s.student.internship_completed = completed
        s.student.record_version += 1
        s.final_plan_id = None
        s.candidates.clear()
        s.blockers.clear()
        s.llm_messages.clear()
        s.queued = None
        for card in s.cards:
            if card.status == "pending":
                card.status = "superseded"
        for item in s.items:
            if item.kind == "plan":
                item.data["stale"] = True
        s.state = "CLARIFY" if s.student.confirmed else "VERIFY_INPUT"
        s.outcome = None
        s.add("system", "event", "บันทึกสถานะฝึกงาน 2100301 จากการยืนยันของผู้ใช้แล้ว กรุณาส่งคำขอจัดแผนใหม่")
        self.store.trace(s.session_id, "internship_confirmation", completed=completed,
                         term=info["term"], record_version=s.student.record_version, source="student_attestation")
        self._save(s)
        return s

    def goal_decision(self, session_id: str, card_id: str, approve: bool) -> Session:
        s = self.get(session_id)
        card = self._card(s, card_id, "goal")
        prev = s.goal
        if approve:
            new = GoalConstraints(**card.data["goal"])
            self._apply_goal(s, new, card.card_id, card.data["changes"])
            card.status = "approved"
            s.add("system", "event", text("goal_approved", s.lang, v=s.goal.goal_version))
            event = (f"[UI event] The student approved the goal card. Goal v{s.goal.goal_version} is now confirmed: "
                     f"{self._goal_summary(s, s.goal)}. Continue with the student's request.")
        else:
            card.status = "declined"
            s.consent_events.append({"card_id": card_id, "approved": False, "at": _now(),
                                     "goal_version": prev.goal_version if prev else None})
            s.add("system", "event", text("goal_declined", s.lang))
            event = ("[UI event] The student declined the goal card; the goal is unchanged "
                     f"({self._goal_summary(s, prev) if prev else 'no confirmed goal'}). Ask what they want instead, "
                     "or continue with the current goal.")
        self.store.trace(s.session_id, "goal_decision", card_id=card_id, approve=approve,
                         goal_version=s.goal.goal_version if s.goal else None)
        self._run_agent(s, event, "goal_approved" if approve else "goal_declined")
        return s

    def blocker_decision(self, session_id: str, card_id: str, choose: str | None = None, decline: bool = False) -> Session:
        s = self.get(session_id)
        card = self._card(s, card_id, "blocker")
        if decline or not choose:
            card.status = "declined"
            s.consent_events.append({"card_id": card_id, "approved": False, "at": _now(),
                                     "goal_version": s.goal.goal_version})
            s.add("system", "event", text("blocker_declined", s.lang, v=s.goal.goal_version))
            self.store.trace(s.session_id, "blocker_decision", card_id=card_id, declined=True)
            self._save(s)
            return s
        alt = next((a for a in card.data["alternatives"] if a["kind"] == choose), None)
        if alt is None:
            raise ValueError(f"alternative {choose!r} is not offered by this blocker")
        update, change = {}, []
        if alt["kind"] == "raise_caps":
            update["caps"] = {**s.goal.caps, **alt["caps"]}
            change.append({"field": "caps", "from": s.goal.caps, "to": update["caps"]})
        elif alt["kind"] == "allow_summer":
            update["allow_summer"] = True
            change.append({"field": "allow_summer", "from": False, "to": True})
        elif alt["kind"] == "extend_horizon":
            update["horizon_end"] = alt["horizon_end"]
            change.append({"field": "horizon_end", "from": s.goal.horizon_end, "to": alt["horizon_end"]})
        self._apply_goal(s, s.goal.model_copy(update=update), card_id, change)
        card.status = "approved"
        label = alt["label_th"] if s.lang == "th" else alt["label_en"]
        s.add("system", "event", text("alt_approved", s.lang, alt=label, v=s.goal.goal_version))
        self.store.trace(s.session_id, "blocker_decision", card_id=card_id, choose=choose,
                         goal_version=s.goal.goal_version)
        self._run_agent(s, f"[UI event] The student approved the alternative '{alt['label_en']}'. Goal "
                           f"v{s.goal.goal_version}: {self._goal_summary(s, s.goal)}. Run solve_plan again and submit "
                           "the plan.", "alt_approved")
        return s

    def retry(self, session_id: str, clear_fault: bool = False) -> Session:
        """Retry after STOP_UNVERIFIED from the same record, goal and conversation (UAT T09)."""
        s = self.get(session_id)
        if s.outcome != "STOP_UNVERIFIED":
            raise ValueError("retry is only available after a stopped turn")
        if clear_fault and s.fault:
            self.store.trace(s.session_id, "fault_cleared", fault=s.fault)
            s.fault = None
            s.run_record["fault"] = None
        g = f", goal v{s.goal.goal_version}" if s.goal else ""
        s.add("system", "event", text("retried", s.lang, r=s.student.record_version, goal=g))
        self.store.trace(s.session_id, "retry", record_version=s.student.record_version,
                         goal_version=s.goal.goal_version if s.goal else None)
        follow = (f"Goal v{s.goal.goal_version} ({self._goal_summary(s, s.goal)}) is still confirmed: run solve_plan "
                  "again and submit the plan." if s.goal else "Continue with the student's last request.")
        self._run_agent(s, f"[UI event] The student pressed Retry after the previous turn stopped. The record and the "
                           f"goal are unchanged. {follow}", "retry")
        return s

    def defer_missing(self, session_id: str) -> Session:
        """After NEED_INFO about a course: plan the rest now without it (UAT T11)."""
        s = self.get(session_id)
        if s.outcome != "NEED_INFO" or not s.student.confirmed:
            raise ValueError("this option is only available after the agent asked for missing course information")
        names = [n["title"] for n in self._unpublished(s)]
        what = ", ".join(names) if names else "the course whose code is missing"
        s.add("system", "event", text("deferred", s.lang))
        self.store.trace(s.session_id, "defer_missing", courses=names)
        self._run_agent(s, f"[UI event] The student chose to plan the rest now without {what}. Do not ask about it "
                           "again and do not put it in must_take or interests.", "defer")
        return s

    def _card(self, s: Session, card_id: str, kind: str) -> Card:
        card = next((c for c in s.cards if c.card_id == card_id), None)
        if card is None or card.kind != kind:
            raise ValueError(f"no {kind} card {card_id}")
        if card.status != "pending":
            raise ValueError(f"card {card_id} is already {card.status}")
        return card

    def _apply_goal(self, s: Session, new: GoalConstraints, consent_id: str, changes: list):
        """The only place where the goal changes: after an explicit approval in the UI (invariant 3)."""
        prev = s.goal
        version = prev.goal_version + 1 if prev else 1
        ref = ConsentRef(consent_id=consent_id, change={"changes": changes, "initial": prev is None}, approved=True,
                         at=_now())
        s.goal = new.model_copy(update={"goal_version": version, "confirmed": True, "preferred_course_ids": [],
                                        "consent_refs": (prev.consent_refs if prev else []) + [ref]})
        s.goal_history.append(s.goal)
        s.consent_events.append({"card_id": consent_id, "approved": True, "at": ref.at, "goal_version": version,
                                 "changes": changes})
        self.store.trace(s.session_id, "goal_changed", goal=s.goal.model_dump(), consent=ref.model_dump())

    # ------------------------------------------------------------ the agent loop
    def _state(self, s: Session) -> str:
        st = s.student
        pending = s.pending("goal")
        goal_status = (f"v{s.goal.goal_version} confirmed: {self._goal_summary(s, s.goal)}" if s.goal
                       else "none confirmed yet")
        if pending:
            goal_status += "; a goal card is waiting for the student's approval"
        return STATE.format(snapshot_id=s.snapshot_id, entry_year=st.entry_year, next_term=st.next_term,
                             end_y4=T.end_of_year4(st.entry_year),
                            record_status=self._record_summary(s), goal_status=goal_status,
                            language="Thai" if s.lang == "th" else "English")

    def _record_summary(self, s: Session) -> str:
        snap, _ = self.snap(s)
        a = audit(snap, s.student, s.goal)
        out = (f"confirmed version {s.student.record_version} (already bound; never ask the student for it); "
               f"{a['earned_credits']} of {snap.total_credits} credits earned")
        if a["must_retake"]:
            out += "; must retake " + ", ".join(f"{c} {snap.courses[c]['name_en']}" for c in a["must_retake"]) +                    " (the planner schedules retakes)"
        return out

    def _progress(self, s: Session, step: str):
        s.progress.append({"step": step, "at": time.time()})

    def _run_agent(self, s: Session, content: str, event: str = "student"):
        """One turn. event: student | goal_approved | goal_declined | alt_approved | retry | defer."""
        info = internship_info(self.snap(s)[0], s.student)
        if info and info["needs_review"]:
            s.add("system", "need_info", info["message"])
            self._end(s, "NEED_INFO", reason="internship completion needs confirmation")
            self._save(s)
            return
        if self.arm != "A":
            s.llm_messages.append({"role": "user", "content": self._state(s) + "\n\n" + content})
        rec = TurnRecord(turn=len(s.turns) + 1, trigger=content[:300], started=time.time())
        s.turns.append(rec)
        s.progress = []
        s.state = "ACT"
        ctx = Ctx(rec)
        llm = llm_mod.FaultyLLM() if s.fault == "model_unavailable" else self.llm
        try:
            if event == "defer" and s.goal is None:
                self._defer_turn(s, ctx, llm, content)
            elif self.arm == "A":
                self._fixed_turn(s, ctx, llm, event)
            else:
                self._agent_loop(s, ctx, llm)
        except Stop as e:
            reason = text(e.key, s.lang, **{k: v for k, v in e.kw.items() if k != "detail"})
            s.add("system", "stop", text("stop", s.lang, reason=reason), detail=e.kw.get("detail"),
                  retry=True)
            self._end(s, "STOP_UNVERIFIED", ctx, reason=f"{e.key}: {e.kw}")
        finally:
            rec.ended = time.time()
            s.progress = []
            if ctx.end == "NEED_INFO" and s.student.confirmed:
                self._next_steps(s)
            self.store.trace(s.session_id, "turn", **rec.model_dump())
            self._save(s)

    def _agent_loop(self, s: Session, ctx: Ctx, llm):
        """Arms B and C: the LLM chooses the tools; the runtime checks every call."""
        rec, nudged = ctx.rec, False
        while ctx.end is None:
            if ctx.remaining() <= 0:
                raise Stop("reason_budget", what="120 s")
            if rec.tool_calls >= BUDGET["tool_calls"]:
                raise Stop("reason_budget", what=f"{BUDGET['tool_calls']} tool calls")
            self._progress(s, "think")
            t0 = time.monotonic()
            try:
                msg, stats = llm.chat([{"role": "system", "content": self.system}] + s.llm_messages,
                                      self.tool_schemas, ctx.remaining())
            except llm_mod.ModelUnavailable as e:
                raise Stop("reason_model", detail=str(e)) from e
            rec.llm_calls += 1
            rec.llm_s = round(rec.llm_s + time.monotonic() - t0, 3)
            content_out = THINK_RE.sub("", msg.get("content") or "").strip()
            calls = msg.get("tool_calls") or []
            self.store.trace(s.session_id, "llm", turn=rec.turn, content=content_out, tool_calls=calls, stats=stats)
            s.llm_messages.append({"role": "assistant", "content": content_out,
                                   **({"tool_calls": calls} if calls else {})})
            if not calls:
                calls = self._calls_in_text(content_out)
            if not calls:
                if not nudged and ctx.remaining() > 5:
                    nudged = True
                    s.llm_messages.append({"role": "user", "content": "[runtime] Answer by calling a tool "
                                           "(reply, ask_user, propose_goal, solve_plan or submit_final)."})
                    continue
                self._finish_text(s, ctx, "info", content_out or "-", [])
                break
            for call in calls:
                fn = call.get("function") or {}
                name, raw = fn.get("name"), fn.get("arguments")
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except json.JSONDecodeError:
                        pass
                if name in self.tool_names:
                    args, err = parse(name, raw)
                else:
                    args, err = None, f"unknown tool {name!r}; allowed: {', '.join(self.tool_names)}"
                if err:
                    rec.tool_calls += 1
                    rec.tools.append(str(name))
                    if rec.tool_calls > BUDGET["tool_calls"]:
                        raise Stop("reason_budget", what=f"{BUDGET['tool_calls']} tool calls")
                    obs = {"status": "ERROR", "error": err}
                    self.store.trace(s.session_id, "tool", turn=rec.turn, name=name, args=raw, observation=obs, wall_s=0)
                else:
                    obs = self._tool(s, ctx, name, args, raw)
                s.llm_messages.append({"role": "tool", "tool_name": str(name),
                                       "content": json.dumps(obs, ensure_ascii=False)})
                if ctx.end is not None:
                    break

    def _tool(self, s: Session, ctx: Ctx, name: str, args, raw=None) -> dict:
        """Run one allowed tool with budget accounting and a trace line (all arms)."""
        rec = ctx.rec
        rec.tool_calls += 1
        rec.tools.append(name)
        if rec.tool_calls > BUDGET["tool_calls"]:
            raise Stop("reason_budget", what=f"{BUDGET['tool_calls']} tool calls")
        self._progress(s, name)
        t1 = time.monotonic()
        obs = getattr(self, f"_t_{name}")(s, ctx, args)
        rec.tool_s = round(rec.tool_s + time.monotonic() - t1, 3)
        self.store.trace(s.session_id, "tool", turn=rec.turn, name=name,
                         args=raw if raw is not None else args.model_dump(), observation=obs,
                         wall_s=round(time.monotonic() - t1, 3))
        return obs

    # ------------------------------------------------------------ arm A: fixed workflow
    def _fixed_llm(self, s: Session, ctx: Ctx, llm, messages: list[dict], tools: list[dict]) -> dict:
        self._progress(s, "think")
        t0 = time.monotonic()
        try:
            msg, stats = llm.chat(messages, tools, ctx.remaining())
        except llm_mod.ModelUnavailable as e:
            raise Stop("reason_model", detail=str(e)) from e
        ctx.rec.llm_calls += 1
        ctx.rec.llm_s = round(ctx.rec.llm_s + time.monotonic() - t0, 3)
        msg = {**msg, "content": THINK_RE.sub("", msg.get("content") or "").strip()}
        self.store.trace(s.session_id, "llm", turn=ctx.rec.turn, content=msg["content"],
                         tool_calls=msg.get("tool_calls") or [], stats=stats)
        return msg

    def _fixed_turn(self, s: Session, ctx: Ctx, llm, event: str):
        """Arm A: audit -> retrieval (interests) -> solve -> validate -> final gate, in this order; clarification
        follows fixed rules. The LLM drafts the goal and writes the explanation, nothing else."""
        if event == "goal_declined":
            s.add("agent", "text", text("fixed_goal_declined", s.lang))
            self._end(s, "WAIT_USER", ctx, reason="goal declined")
            return
        if event in ("goal_approved", "alt_approved") or (event == "retry" and s.goal):
            self._fixed_plan(s, ctx, llm)
            return
        said = [i.text for i in s.items if i.role == "student"]
        latest = said[-1] if said else ""
        if not re.search(r"\d", latest):
            for field, pattern in VAGUE.items():
                if pattern.search(latest):
                    question = text(f"fixed_clarify_{field}", s.lang)
                    s.asked.append({"turn": ctx.rec.turn, "kind": "clarify", "fields": [field]})
                    s.add("agent", "question", question, fields=[field], ask_kind="clarify")
                    self._end(s, "WAIT_USER", ctx, reason=f"rule clarify {field}")
                    return
        msg = self._fixed_llm(s, ctx, llm, [
            {"role": "system", "content": GOAL_DRAFT},
            {"role": "user", "content": self._state(s) + "\n\nStudent messages, oldest first:\n" +
             "\n".join(f"- {t}" for t in said)}], schemas(["propose_goal"]))
        calls = msg.get("tool_calls") or self._calls_in_text(msg["content"])
        raw = next(((c.get("function") or {}).get("arguments") for c in calls
                    if (c.get("function") or {}).get("name") == "propose_goal"), None)
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                raw = None
        args, err = parse("propose_goal", raw or {})
        if err:
            args = ProposeGoalArgs()
        obs = self._tool(s, ctx, "propose_goal", args)
        if ctx.end is not None:
            return                                   # goal card shown
        if obs["status"] == "APPLIED":
            self._fixed_plan(s, ctx, llm)
            return
        errors = obs.get("missing") or obs.get("errors") or []
        if any("never choose a number" in e for e in errors):
            question = text("fixed_clarify_caps", s.lang)
            s.asked.append({"turn": ctx.rec.turn, "kind": "clarify", "fields": ["caps"]})
            s.add("agent", "question", question, fields=["caps"], ask_kind="clarify")
            self._end(s, "WAIT_USER", ctx, reason="rule clarify caps")
            return
        ctx.need_info = True
        s.add("agent", "question", text("fixed_need_info", s.lang, items="; ".join(errors)), fields=["must_take"],
              ask_kind="need_info")
        self._end(s, "NEED_INFO", ctx, reason="goal draft rejected")

    def _defer_turn(self, s: Session, ctx: Ctx, llm, content: str):
        """"Plan the rest now": one restricted goal draft from the student's other wishes, else the default goal."""
        said = [i.text for i in s.items if i.role == "student"]
        msg = self._fixed_llm(s, ctx, llm, [
            {"role": "system", "content": GOAL_DRAFT + " " + content.removeprefix("[UI event] ")},
            {"role": "user", "content": self._state(s) + "\n\nStudent messages, oldest first:\n" +
             "\n".join(f"- {t}" for t in said)}], schemas(["propose_goal"]))
        calls = msg.get("tool_calls") or self._calls_in_text(msg["content"])
        raw = next(((c.get("function") or {}).get("arguments") for c in calls
                    if (c.get("function") or {}).get("name") == "propose_goal"), None)
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                raw = None
        args, err = parse("propose_goal", raw or {})
        if not err:
            deferred = {m["title"].lower() for m in self._unpublished(s)}
            if args.interests:      # the student chose to leave that course out: keep only real topics
                args.interests = [t for t in args.interests if t.lower().strip() not in deferred] or None
            if args.must_take:      # and only real course codes (the deferred course has none)
                args.must_take = [c for c in args.must_take if c in self.snap(s)[0].courses] or None
            self._tool(s, ctx, "propose_goal", args)
        if ctx.end is None:
            self._tool(s, ctx, "propose_goal", ProposeGoalArgs())     # the default goal: end of Year 4, cap 22
        s.llm_messages.append({"role": "user", "content": self._state(s) + "\n\n" + content +
                               " GradPath showed the student a goal card without that course."})

    def _fixed_plan(self, s: Session, ctx: Ctx, llm):
        self._tool(s, ctx, "audit", ARGS["audit"]())
        preferred = []
        if s.goal.interests:
            found = self._tool(s, ctx, "retrieve_courses", RetrieveArgs(query=" ".join(s.goal.interests)[:200]))
            preferred = [r["course_id"] for r in found["results"] if r.get("course_id")][:12]
        r = self._tool(s, ctx, "solve_plan", SolveArgs(preferred_course_ids=preferred))
        if r["status"] == "NEED_INFO":
            s.add("agent", "question", text("fixed_need_info", s.lang, items="; ".join(r["missing"])),
                  fields=["record"], ask_kind="need_info")
            self._end(s, "NEED_INFO", ctx, reason="planner NEED_INFO")
            return
        if r["status"] == "INFEASIBLE":
            facts = (f"No plan meets every hard rule under the student's goal ({self._goal_summary(s, s.goal)}). The "
                     f"solver proved these alternatives feasible: {json.dumps(r['proven_alternatives'])}. The student "
                     "chooses one in the UI.")
            status, ref = "blocker", r["blocker_id"]
        else:
            self._tool(s, ctx, "validate_plan", ValidateArgs(plan_id=r["plan_id"]))
            facts = (f"Verified plan to {s.goal.horizon_end} for the goal ({self._goal_summary(s, s.goal)}). Terms: "
                     f"{json.dumps(r['terms'], ensure_ascii=False)}. Courses matching the interests: "
                     f"{r['preferred_in_plan']}.")
            status, ref = "plan", r["plan_id"]
        errors = []
        while ctx.end is None:
            note = f"\nYour previous text was rejected: {errors}" if errors else ""
            msg = self._fixed_llm(s, ctx, llm, [
                {"role": "system", "content": EXPLAIN.format(language="Thai" if s.lang == "th" else "English")},
                {"role": "user", "content": facts + note}], [])
            explanation = (msg["content"] or ("แผนนี้ผ่านการตรวจแล้ว" if s.lang == "th" else "This result is verified."))[:1500]
            out = self._tool(s, ctx, "submit_final", SubmitArgs(status=status, ref=ref, explanation=explanation))
            errors = out.get("errors", [])

    @staticmethod
    def _calls_in_text(content: str) -> list[dict]:
        """Small models sometimes write a tool call as JSON text; accept it only when it parses as one."""
        try:
            obj = json.loads(content.strip().removeprefix("```json").removesuffix("```").strip())
        except (json.JSONDecodeError, AttributeError):
            return []
        if not isinstance(obj, dict):
            return []
        if isinstance(obj.get("name"), str) and isinstance(obj.get("arguments"), dict):
            return [{"function": {"name": obj["name"], "arguments": obj["arguments"]}}]
        if obj.get("kind") in ("info", "decline") and isinstance(obj.get("message"), str):
            return [{"function": {"name": "reply", "arguments": obj}}]
        return []

    # ------------------------------------------------------------ grounding
    def _allowed_ids(self, s: Session, plan_ids: set[str] | None = None) -> set[str]:
        snap, index = self.snap(s)
        ids = {r.course_id for r in s.student.records} | (plan_ids or set())
        for p in index.docs:
            if p.source_id in s.retrieved:
                ids |= {p.course_id} if p.course_id else set()
                ids |= set(ID_RE.findall(p.text))
        if plan_ids is None:
            ids |= set(snap.courses)
        return ids

    def _ungrounded(self, s: Session, msg: str, plan_ids: set[str] | None = None) -> list[str]:
        allowed = self._allowed_ids(s, plan_ids)
        return sorted({i for i in ID_RE.findall(msg) if i not in allowed})

    def _mislabelled(self, s: Session, msg: str) -> list[str]:
        """A Latin course title written next to a code that belongs to another course, e.g. "Software-Defined
        Systems I (2110413)" when 2110413 is Computer Security (UAT T11, 4 Nov)."""
        snap, _ = self.snap(s)
        out = []
        for title, cid in TITLE_ID.findall(msg):
            c = snap.courses.get(cid)
            words = {w for w in re.findall(r"[a-z]{3,}", title.lower()) if w not in ("and", "for", "the")}
            if not c or not words:
                continue
            known = set(re.findall(r"[a-z]{3,}", c["name_en"].lower()))
            if not words & known:
                out.append(f"{cid} is {c['name_en']}, not {title.strip()}")
        return out

    def _double_counted(self, s: Session, msg: str) -> list[str]:
        """An answer that lets one course count toward two categories at once (T08 on 3 and 9 Nov said 2110521
        counts as a core-level and a department elective "at the same time"); rules.allocate gives each course
        exactly one category."""
        if ONE_CATEGORY.search(msg):
            return []
        snap, _ = self.snap(s)
        out = []
        for cid in sorted(set(ID_RE.findall(msg))):
            cats = (snap.courses.get(cid) or {}).get("categories", [])
            named = [k for k in cats if k in msg or snap.categories[k]["name_th"] in msg
                     or snap.categories[k]["name_en"].lower() in msg.lower()]
            if len(cats) > 1 and (len(named) > 1 or BOTH_AT_ONCE.search(msg)):
                out.append(f"{cid} counts toward exactly one of {cats} in a plan, never two at once; say that it may "
                           "count toward one of them")
        return out

    def _unpublished(self, s: Session) -> list[dict]:
        """Curriculum options whose course code is not published (snapshot conflicts C10, C11) that the student named
        or that retrieval returned in this session."""
        snap, index = self.snap(s)
        said = " ".join(i.text for i in s.items if i.role == "student").lower()
        out = []
        for p in index.docs:
            if not p.source_id.startswith("unlisted:"):
                continue
            title = p.title.split(" / ")[0]
            if p.source_id in s.retrieved or title.lower() in said:
                cat = snap.categories.get(p.meta.get("category"), {})
                out.append({"title": title, "category": p.meta.get("category"),
                            "category_name": cat.get("name_th" if s.lang == "th" else "name_en", p.meta.get("category"))})
        return out

    def _next_steps(self, s: Session):
        """After NEED_INFO: what is missing and the two ways forward (UAT finding T11)."""
        snap, _ = self.snap(s)
        missing = self._unpublished(s)
        deficits = audit(snap, s.student, s.goal)["category_deficits"]
        said = " ".join(i.text for i in s.items if i.role == "student")
        unknown = sorted({c for c in ID_RE.findall(said) if c not in snap.courses})
        lines = [text("missing_unpublished", s.lang, title=m["title"], snapshot=s.snapshot_id,
                      category=m["category_name"]) for m in missing]
        if unknown:
            lines.append(text("missing_unknown_code", s.lang, codes=", ".join(unknown), snapshot=s.snapshot_id))
        lines = lines or [text("missing_generic", s.lang)]
        gap = next(((m["category_name"], deficits[m["category"]]) for m in missing if deficits.get(m["category"])), None)
        lines.append(text("next_defer", s.lang, deficit=text("next_deficit", s.lang, category=gap[0], credits=gap[1])
                          if gap else ""))
        lines.append(text("next_code", s.lang))
        s.add("system", "next_steps", "\n".join(lines), missing=[m["title"] for m in missing], can_defer=True)

    def _finish_text(self, s: Session, ctx: Ctx, kind: str, msg: str, citations: list[str]):
        s.add("agent", "decline" if kind == "decline" else "text", msg, citations=citations)
        self._end(s, "NEED_INFO" if ctx.need_info else "WAIT_USER", ctx, reason=f"reply {kind}")

    # ------------------------------------------------------------ tools
    def _t_audit(self, s, ctx, args):
        snap, _ = self.snap(s)
        return audit(snap, s.student, s.goal)

    def _t_retrieve_courses(self, s, ctx, args):
        _, index = self.snap(s)
        results = retrieve(index, args.query)
        for r in results:
            if r["source_id"] not in s.retrieved:
                s.retrieved.append(r["source_id"])
        keep = ("source_id", "course_id", "title", "credits", "status", "snippet")
        out = []
        for r in results:
            row = {k: r[k] for k in keep if r.get(k) not in (None, "", [])}
            if r.get("categories"):
                row["may_count_toward_one_of"] = r["categories"]
            out.append(row)
        return {"results": out, "note": "a course counts toward exactly one category"}

    def _t_propose_goal(self, s, ctx, args: ProposeGoalArgs):
        snap, _ = self.snap(s)
        st = s.student
        base = s.goal or GoalConstraints(horizon_end=T.end_of_year4(st.entry_year))
        update = args.model_dump(exclude_none=True)
        errors, missing = [], []
        reg_max, summer_max = snap.regulation("max_credits_regular"), snap.regulation("max_credits_summer")
        if update.get("default_cap") == reg_max and base.default_cap is None:
            del update["default_cap"]          # the regulation maximum is the default, not a change
        if "horizon_end" in update:
            h = update["horizon_end"]
            try:
                if T.is_summer(h) or T.key(h) < T.key(st.next_term) or T.study_year(h, st.entry_year) > 8:
                    errors.append(f"horizon_end {h} must be a regular term from {st.next_term} on")
            except ValueError as e:
                errors.append(str(e))
        # Caps above the regulation are never applied (R4): they are dropped and shown on the card, whatever the
        # source of the number (a student's wish or an injected "approval").
        ignored = []
        if update.get("default_cap", 0) > reg_max:
            ignored.append({"field": "default_cap", "value": update.pop("default_cap"), "max": reg_max})
        if "default_cap" in update and update["default_cap"] < 1:
            errors.append("default_cap must be at least 1")
        caps = {}
        for term, cap in (update.pop("caps", None) or {}).items():
            try:
                top = summer_max if T.is_summer(term) else reg_max
            except ValueError as e:
                errors.append(str(e))
                continue
            if cap > top:
                ignored.append({"field": f"caps[{term}]", "value": cap, "max": top})
            elif cap < 1:
                errors.append(f"cap for {term} must be at least 1")
            else:
                caps[term] = cap
        if caps:
            update["caps"] = caps
        # A cap the student did not type is a number the model chose: vague wording needs a clarifying question.
        typed = set(NUM_RE.findall(" ".join(i.text for i in s.items if i.role == "student").translate(THAI_DIGITS)))
        chosen = sorted({v for v in [update.get("default_cap"), *update.get("caps", {}).values()]
                         if v is not None and str(v) not in typed})
        if chosen:
            errors.append(f"the student never typed the cap {chosen}; never choose a number for them: call ask_user "
                          "with kind \"clarify\" and fields [\"caps\"]")
        # A course title without a published code is not a study topic (UAT T11: putting it in interests would plan
        # silently without the course the student must take).
        unpublished = {o["name_en"].lower() for cat in snap.data["categories"] for o in cat.get("unlisted_options", [])}
        for topic in update.get("interests", []):
            low = topic.lower().strip()
            if any(low == t or (len(low) > 10 and (low in t or t in low)) for t in unpublished):
                errors.append(f"{topic!r} is a course title without a published code, not a study topic: leave it out "
                              "of interests (if the student must take it, the missing code needs ask_user kind "
                              "\"need_info\")")
        # An interest the student never stated is the model's own idea (10 Nov: "ช่วยวางแผนให้หน่อย" became
        # interests ["AI"]): it is dropped, so preferred courses come only from what the student asked for.
        said = " ".join(i.text for i in s.items if i.role == "student").lower()
        unstated = [t for t in update.get("interests", []) if not self._stated(t, said)]
        if unstated:
            update["interests"] = [t for t in update["interests"] if t not in unstated]
        done = {r.course_id for r in st.records if snap.earns_credit(r.grade)}
        # Invariant 4: a course ID enters the goal only if the student typed it or retrieval returned it.
        grounded = set(ID_RE.findall(" ".join(i.text for i in s.items if i.role == "student"))) | \
            {sid.split(":", 1)[1] for sid in s.retrieved if sid.startswith("course:")}
        # Checked before grounding: a required course the student has not passed (a retake, UAT T05) is always
        # planned, so it is not a goal change and never goes on the goal card for approval.
        scheduled = [c for c in update.get("must_take", []) if c in snap.courses and c not in done
                     and snap.courses[c]["kind"] == "required"]
        if scheduled:
            update["must_take"] = [c for c in update["must_take"] if c not in scheduled]
        for field in ("must_take", "avoid"):
            for cid in update.get(field, []):
                if cid not in snap.courses:
                    missing.append(f"{field}: {cid!r} is not a course code in snapshot {snap.snapshot_id}")
                elif cid not in grounded:
                    errors.append(f"{cid} was neither typed by the student nor returned by retrieve_courses; search "
                                  "for the course by name first and never guess a course ID")
                elif field == "must_take" and cid in done:
                    errors.append(f"{cid} is already passed")
                elif field == "avoid" and snap.courses[cid]["kind"] == "required":
                    errors.append(f"{cid} is a required course and cannot be avoided")
        if missing:
            ctx.need_info = True
            return {"status": "NEED_INFO", "missing": missing,
                    "hint": "do not guess a course ID; ask the student with ask_user kind need_info"}
        if errors:
            return {"status": "ERROR", "errors": errors}
        new = base.model_copy(update=update)
        changes = [{"field": f, "from": getattr(base, f), "to": getattr(new, f)}
                   for f in GoalConstraints.HARD_FIELDS if getattr(base, f) != getattr(new, f)]
        note = "; ".join(filter(None, [
            (f"not applied: caps above the regulation maximum need the dean's approval and are outside GradPath "
             f"{ignored}") if ignored else None,
            (f"{scheduled} left out of must_take: required courses not yet passed are always planned (retakes "
             "included)") if scheduled else None,
            (f"interests {unstated} removed: the student did not state them") if unstated else None])) or None
        if s.goal is not None and not changes:
            s.goal = new
            return {"status": "APPLIED", "goal_version": s.goal.goal_version, "note": note or "soft fields only"}
        s.supersede("goal")
        card = Card(card_id="G-" + uuid.uuid4().hex[:6], kind="goal",
                    data={"goal": new.model_dump(exclude={"consent_refs", "goal_version", "confirmed"}),
                          "initial": s.goal is None, "changes": changes, "ignored": ignored,
                          "from_version": s.goal.goal_version if s.goal else None,
                          "course_names": {c: snap.courses[c]["name_en"] for c in new.must_take + new.avoid}})
        s.cards.append(card)
        s.add("agent", "goal_card", "", card_id=card.card_id)
        self._end(s, "WAIT_USER", ctx, reason="goal card")
        return {"status": "WAITING_FOR_STUDENT", "card_id": card.card_id, **({"note": note} if note else {})}

    @staticmethod
    def _stated(topic: str, said: str) -> bool:
        """The whole topic, a listed synonym, or one distinctive word of it (4+ letters) appears in the student's
        text, so a typo elsewhere ("software archetecture") or a reworded phrase ("cloud compute") still counts."""
        t = topic.lower().strip()
        words = {t, t.removesuffix("s")} | next((g for g in TOPIC_WORDS if t in g), set())
        words |= {w.removesuffix("s") for w in re.findall(r"[a-z]{4,}", t) if w not in GENERIC_WORDS}
        return any(w and w in said for w in words)

    def _blocker_waiting(self, ctx) -> dict | None:
        if ctx.blocker:
            return {"status": "ERROR", "error": f"solve_plan returned INFEASIBLE in this turn: call submit_final with "
                    f"status \"blocker\" and ref \"{ctx.blocker}\". Do not ask the student about goal changes; the UI "
                    "shows the alternatives that the solver proved."}
        return None

    def _t_ask_user(self, s, ctx, args):
        if err := self._blocker_waiting(ctx):
            return err
        bad = self._ungrounded(s, args.question)
        if bad:
            return {"status": "ERROR", "error": f"the question mentions unknown course IDs {bad}"}
        known = sorted({r.course_id for r in s.student.records} & set(ID_RE.findall(args.question)))
        if known:      # UAT T05: never ask the student to confirm what the confirmed record already shows
            return {"status": "ERROR", "error": f"{known} are in the student's confirmed record v"
                    f"{s.student.record_version}; do not ask about them (retakes are scheduled by the planner). "
                    "Continue without this question."}
        s.asked.append({"turn": ctx.rec.turn, "kind": args.kind, "fields": list(args.fields)})
        s.add("agent", "question", args.question, fields=list(args.fields), ask_kind=args.kind)
        ctx.need_info = ctx.need_info or args.kind == "need_info"
        self._end(s, "NEED_INFO" if ctx.need_info else "WAIT_USER", ctx, reason=f"ask_user {args.kind}")
        return {"status": "ASKED"}

    def _t_reply(self, s, ctx, args):
        if err := self._blocker_waiting(ctx):
            return err
        bad = self._ungrounded(s, args.message)
        unknown_cites = [c for c in args.citations if c not in s.retrieved]
        if bad or unknown_cites:
            return {"status": "ERROR", "error": f"unknown course IDs {bad}; citations not retrieved in this session "
                                                f"{unknown_cites}"}
        if wrong := self._mislabelled(s, args.message):
            return {"status": "ERROR", "error": f"course names do not match their codes: {wrong}"}
        if wrong := self._double_counted(s, args.message):
            return {"status": "ERROR", "error": f"the message breaks the one-category rule: {wrong}"}
        self._finish_text(s, ctx, args.kind, args.message, args.citations)
        return {"status": "SENT"}

    def _t_solve_plan(self, s, ctx, args):
        snap, _ = self.snap(s)
        if s.goal is None:
            return {"status": "ERROR", "error": "no confirmed goal; call propose_goal with the student's goal first"}
        unknown = [c for c in args.preferred_course_ids if c not in snap.courses]
        if unknown:
            return {"status": "ERROR", "error": f"preferred course IDs not in the snapshot: {unknown}"}
        if s.fault == "planner_timeout":
            self.store.trace(s.session_id, "fault", fault="planner_timeout")
            raise Stop("reason_solver", detail="fault injected: planner_timeout")
        goal = s.goal.model_copy(update={"preferred_course_ids": list(dict.fromkeys(args.preferred_course_ids))})
        r = planner.solve(snap, s.student, goal, self.solver_time_limit_s)
        if r["status"] == "UNKNOWN":
            raise Stop("reason_solver", detail=r.get("reason"))
        if r["status"] == "NEED_INFO":
            ctx.need_info = True
            return {"status": "NEED_INFO", "missing": r["missing"]}
        if r["status"] == "INFEASIBLE":
            d = planner.diagnose(snap, s.student, s.goal, self.solver_time_limit_s)
            bid = "B-" + uuid.uuid4().hex[:6]
            alts = [{**a, "label_th": ALT_LABELS[a["kind"]][0], "label_en": ALT_LABELS[a["kind"]][1]}
                    for a in d["alternatives"]]
            s.blockers[bid] = {"blocker_id": bid, "alternatives": alts, "reason": r.get("reason"),
                               "modeled_constraints": d["modeled_constraints"], "goal_version": s.goal.goal_version,
                               "record_version": s.student.record_version, "snapshot_hash": snap.content_hash,
                               "goal_summary": self._goal_summary(s, s.goal),
                               "goal": s.goal.model_dump(exclude={"consent_refs", "preferred_course_ids"})}
            ctx.blocker = bid
            return {"status": "INFEASIBLE", "blocker_id": bid, "reason": r.get("reason") or "no plan meets every "
                    "hard rule under the current goal", "proven_alternatives": d["alternatives"]}
        cand = r["candidate"]
        ctx.blocker = None
        s.candidates[cand.plan_id] = cand
        s.plan_preferred[cand.plan_id] = list(dict.fromkeys(args.preferred_course_ids))
        return {"status": "PLAN", **self._plan_summary(s, cand, args.preferred_course_ids)}

    def _t_validate_plan(self, s, ctx, args):
        cand = s.candidates.get(args.plan_id)
        if cand is None:
            return {"status": "ERROR", "error": f"no stored plan {args.plan_id}"}
        snap, _ = self.snap(s)
        v = validator.validate(snap, s.student, s.goal, cand)
        return {"valid": v.valid, "errors": v.errors[:6], "warnings": v.warnings[:4], "total_credits": v.total_credits}

    def _t_submit_final(self, s, ctx, args):
        snap, _ = self.snap(s)
        if args.status == "blocker":
            b = s.blockers.get(args.ref)
            errors = []
            if b is None:
                errors.append(f"no stored blocker {args.ref}")
            elif (b["goal_version"], b["record_version"], b["snapshot_hash"]) != \
                    (s.goal.goal_version, s.student.record_version, snap.content_hash):
                errors.append("the blocker was found under an older goal or record version; run solve_plan again")
            errors += [f"explanation mentions unknown course IDs {bad}" for bad in [self._ungrounded(s, args.explanation)] if bad]
            errors += [f"course names do not match their codes: {w}" for w in [self._mislabelled(s, args.explanation)] if w]
            if errors:
                return self._reject(s, ctx, errors)
            card = Card(card_id="X-" + uuid.uuid4().hex[:6], kind="blocker",
                        data={**b, "explanation": args.explanation})
            s.supersede("blocker")
            s.cards.append(card)
            s.add("agent", "blocker_card", args.explanation, card_id=card.card_id)
            self.store.trace(s.session_id, "final_gate", kind="blocker", ref=args.ref, passed=True)
            self._end(s, "EVIDENCED_BLOCKER", ctx, reason="witnessed infeasibility")
            return {"status": "SHOWN"}
        cand = s.candidates.get(args.ref)
        if cand is None:
            return self._reject(s, ctx, [f"no stored plan {args.ref}; use the plan_id returned by solve_plan"])
        v = validator.validate(snap, s.student, s.goal, cand)
        plan_ids = {i.course_id for t in cand.terms for i in t.items if i.course_id}
        errors = list(v.errors)
        bad = self._ungrounded(s, args.explanation, plan_ids)
        if bad:
            errors.append(f"explanation mentions course IDs that are not in the plan or retrieved results: {bad}")
        if wrong := self._mislabelled(s, args.explanation):
            errors.append(f"course names do not match their codes: {wrong}")
        self.store.trace(s.session_id, "final_gate", kind="plan", plan_id=cand.plan_id, plan_hash=cand.plan_hash,
                         valid=v.valid, errors=errors, record_version=s.student.record_version,
                         goal_version=s.goal.goal_version, snapshot_hash=snap.content_hash)
        if errors:
            return self._reject(s, ctx, errors)
        s.final_plan_id = cand.plan_id
        s.add("agent", "plan", args.explanation, plan=self.plan_view(s, cand, v))
        self._end(s, "DONE", ctx, reason="final gate passed")
        return {"status": "ACCEPTED"}

    def _reject(self, s, ctx, errors):
        ctx.rec.revisions += 1
        if ctx.rec.revisions > BUDGET["revisions"]:
            raise Stop("reason_gate", detail="; ".join(errors)[:300])
        return {"status": "REJECTED", "errors": errors[:6], "revisions_left": BUDGET["revisions"] - ctx.rec.revisions}

    # ------------------------------------------------------------ views
    def _goal_summary(self, s: Session, g: GoalConstraints | None) -> str:
        if g is None:
            return "none"
        parts = [f"horizon {g.horizon_end}", f"cap {g.default_cap or 22} per regular term"]
        if g.caps:
            parts.append("term caps " + ", ".join(f"{t}: {c}" for t, c in sorted(g.caps.items())))
        parts.append("summer allowed" if g.allow_summer else "no summer")
        if g.must_take:
            parts.append("must take " + ", ".join(g.must_take))
        if g.avoid:
            parts.append("avoid " + ", ".join(g.avoid))
        if g.interests:
            parts.append("interests " + ", ".join(g.interests))
        return "; ".join(parts)

    def _plan_summary(self, s: Session, cand, preferred: list[str]) -> dict:
        terms, planned = {}, set()
        for t in cand.terms:
            if not t.items:
                continue
            names = [i.course_id if i.course_id else f"slot {i.slot}" for i in t.items]
            planned |= {i.course_id for i in t.items if i.course_id}
            terms[t.term] = f"{t.credits}/{t.cap} credits: " + ", ".join(names)
        return {"plan_id": cand.plan_id, "terms": terms, "preferred_in_plan": [c for c in preferred if c in planned],
                "solver": cand.solver.get("status"),
                "next": "call validate_plan, then submit_final with this plan_id"}

    def plan_view(self, s: Session, cand, v) -> dict:
        snap, _ = self.snap(s)
        retake = set(audit(snap, s.student, s.goal)["must_retake"])
        preferred = set(s.plan_preferred.get(cand.plan_id, []))
        goal = s.goal

        def reasons(cid: str, c: dict) -> list[str]:
            out = []
            if cid in retake:
                out.append("retake")
            if goal and cid in goal.must_take:
                out.append("must_take")
            if cid in preferred:
                out.append("interest")
            if c["kind"] == "required" and cid not in retake:
                out.append("required")
            return out or ["category"]

        st = standing(snap, s.student)
        before, _ = allocate(snap, dict(st.completed), [(cat, cr) for cr, cat in st.external.values()])
        categories = [{"id": k, "name_th": c["name_th"], "name_en": c["name_en"], "min": c["min_credits"],
                       "before": before.get(k, 0), "after": v.category_totals.get(k, 0)}
                      for k, c in snap.categories.items() if c["min_credits"]]
        terms = []
        for t in cand.terms:
            items = []
            for i in t.items:
                cat = snap.categories.get(i.category, {})
                if i.course_id:
                    c = snap.courses[i.course_id]
                    items.append({"course_id": i.course_id, "name_th": c["name_th"], "name_en": c["name_en"],
                                  "credits": i.credits, "category": i.category, "category_th": cat.get("name_th"),
                                  "flags": i.flags, "kind": c["kind"], "reasons": reasons(i.course_id, c)})
                else:
                    items.append({"slot": i.slot, "credits": i.credits, "category": i.category,
                                  "category_th": cat.get("name_th"), "category_en": cat.get("name_en"), "flags": []})
            terms.append({"term": t.term, "kind": t.kind, "cap": t.cap, "credits": t.credits, "items": items})
        return {"plan_id": cand.plan_id, "plan_hash": cand.plan_hash, "goal_version": cand.goal_version,
                "record_version": cand.record_version, "snapshot_id": cand.snapshot_id, "valid": v.valid,
                "warnings": v.warnings, "total_credits": v.total_credits, "category_totals": v.category_totals,
                "categories": categories, "interests": goal.interests if goal else [], "terms": terms}

    def _unresolved_text(self, s: Session) -> str:
        names = {"th": {"grade": "เกรด", "course_id": "รหัสวิชา", "credits": "หน่วยกิต", "category": "หมวด",
                        "term": "ภาคการศึกษา"},
                 "en": {"grade": "grade", "course_id": "course code", "credits": "credits", "category": "category",
                        "term": "term"}}[s.lang]
        out = []
        for u in s.student.unresolved:
            r = s.student.records[u.record_index]
            what = r.evidence.text if r.evidence and r.evidence.text else r.course_id
            hint = f" ({'อาจเป็น' if s.lang == 'th' else 'possibly'} {' / '.join(u.candidates)})" if u.candidates else ""
            out.append(f"{names[u.field]} {'ของ' if s.lang == 'th' else 'of'} “{what}” {r.term}{hint}")
        return "; ".join(out)

    def view(self, s: Session, operator: bool = False) -> dict:
        snap, _ = self.snap(s)
        st = s.student
        unresolved = {(u.record_index, u.field): u for u in st.unresolved}
        records = []
        for n, r in enumerate(st.records):
            c = snap.courses.get(r.course_id)
            category_ids = c["categories"] if c else ([snap.category_id(r.category)] if r.category else [])
            flags = [{"field": f, "reason": u.reason, "candidates": u.candidates}
                     for (i, f), u in unresolved.items() if i == n]
            records.append({"index": n, "course_id": r.course_id, "term": r.term, "grade": r.grade,
                            "name_th": c["name_th"] if c else r.title, "name_en": c["name_en"] if c else r.title,
                            "credits": r.credits if r.credits is not None else c["credits"] if c else None,
                            "title": r.title, "category": snap.category_id(r.category),
                            "category_names": [snap.categories[k]["name_th"] for k in category_ids],
                            "evidence": r.evidence.text if r.evidence else None,
                            "page": r.evidence.page if r.evidence else None,
                            "unresolved": flags})
        summary = audit(snap, st, s.goal) if not st.unresolved else None
        if summary:
            summary["category_names"] = {k: snap.categories[k]["name_th"] for k in summary["category_deficits"]}
        out = {
            "session_id": s.session_id, "persona": s.persona,
            "persona_label": "รายงานผลการเรียนของคุณ" if st.source_kind == "pdf" else PERSONA_LABELS.get(s.persona, s.persona),
            "task_id": s.task_id, "state": s.state, "outcome": s.outcome, "busy": s.busy, "lang": s.lang,
            "progress": s.progress, "turn_started": s.turns[-1].started if s.busy and s.turns else None,
            "student": {"student_ref": st.student_ref, "entry_year": st.entry_year, "next_term": st.next_term,
                        "end_of_year4": T.end_of_year4(st.entry_year), "record_version": st.record_version,
                        "confirmed": st.confirmed, "unresolved": len(st.unresolved), "source_kind": st.source_kind},
            "report": st.report,
            "internship": internship_info(snap, st),
            "categories": [{"id": k, "name": snap.categories[k]["name_th"]} for k in snap.slot_categories()],
            "records": records, "audit": summary,
            "goal": ({**s.goal.model_dump(exclude={"consent_refs", "preferred_course_ids"}),
                      "summary": self._goal_summary(s, s.goal)} if s.goal else None),
            "cards": [c.model_dump() for c in s.cards], "items": [i.model_dump() for i in s.items],
            "regulation": {"max_regular": snap.regulation("max_credits_regular"),
                           "max_summer": snap.regulation("max_credits_summer")},
        }
        if operator:
            out["operator"] = {"fault": s.fault, "overlay": bool(s.overlay), "run_record": s.run_record,
                               "turns": [t.model_dump() for t in s.turns],
                               "trace": str(self.store.trace_path(s.session_id))}
        return out
