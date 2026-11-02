"""FastAPI app on 127.0.0.1 (D7): sessions, messages and UI decisions; serves the built React UI from dist/.

Agent turns run in a background thread per session; the UI polls GET /api/sessions/{id} while `busy` is true.
"""
from __future__ import annotations

import threading
import time
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from ..fixtures import load_persona, persona_names
from ..runtime import llm as llm_mod
from ..runtime.agent import PERSONA_LABELS, Runtime, load_tasks
from ..snapshot import ROOT
from ..tools.planner import solve
from .. import terms as T

app = FastAPI(title="GradPath", version="0.2")
runtime = Runtime()
errors: dict[str, str] = {}
warm = {"model": None, "model_s": None, "planner_s": None, "error": None, "started": time.time()}


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NewSession(Body):
    persona: str | None = None
    task_id: str | None = None


class Message(Body):
    text: str = Field(min_length=1, max_length=2000)


class Resolve(Body):
    record_index: int
    field: Literal["course_id", "grade", "credits", "category", "term"]
    value: str


class RecordDecision(Body):
    resolve: list[Resolve] = []
    confirm: bool = True


class GoalDecision(Body):
    card_id: str
    approve: bool


class BlockerDecision(Body):
    card_id: str
    choose: str | None = None
    decline: bool = False


def _warm_up():
    try:
        st = load_persona("y3-base")
        from ..contracts import GoalConstraints
        from ..snapshot import load
        t0 = time.monotonic()
        solve(load(), st, GoalConstraints(horizon_end=T.end_of_year4(st.entry_year)))
        warm["planner_s"] = round(time.monotonic() - t0, 2)
        warm["model_s"] = llm_mod.warm_up()
        warm["model"] = True
    except Exception as e:                      # report, never crash the server
        warm["model"], warm["error"] = False, f"{type(e).__name__}: {e}"


@app.on_event("startup")
def startup():
    threading.Thread(target=_warm_up, daemon=True).start()


@app.get("/api/health")
def health():
    info = llm_mod.model_info()
    return {"ok": True, "warm": warm, **info, **runtime.static, "budget": {"tool_calls": 8, "revisions": 2,
                                                                           "seconds": 120}}


@app.get("/api/personas")
def personas():
    out = []
    for name in persona_names():
        st = load_persona(name)
        out.append({"name": name, "label": PERSONA_LABELS.get(name, name), "entry_year": st.entry_year,
                    "next_term": st.next_term, "end_of_year4": T.end_of_year4(st.entry_year)})
    return out


@app.get("/api/tasks")
def tasks():
    """Operator view of the test set, without the expected outcomes."""
    return [{"id": t["id"], "uat": t["uat"], "type": t["type"], "persona": t["persona"], "lang": t["lang"],
             "fault": (t.get("inject") or {}).get("fault"), "overlay": bool((t.get("inject") or {}).get("snapshot_overlay"))}
            for t in load_tasks().values()]


def _view(session_id: str, operator: bool = False):
    try:
        s = runtime.get(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "no such session")
    v = runtime.view(s, operator)
    v["error"] = errors.get(session_id)
    return v


@app.post("/api/sessions")
def create(body: NewSession):
    try:
        s = runtime.create_session(persona=body.persona, task_id=body.task_id)
    except (KeyError, FileNotFoundError, ValueError) as e:
        raise HTTPException(400, f"cannot start the session: {e}")
    return _view(s.session_id, operator=True)


@app.get("/api/sessions/{session_id}")
def get(session_id: str, operator: bool = False):
    return _view(session_id, operator)


def _spawn(session_id: str, action):
    s = runtime.get(session_id)
    lock = runtime.lock(session_id)
    if s.busy or not lock.acquire(blocking=False):
        raise HTTPException(409, "the agent is still working on the previous step")
    s.busy = True
    errors.pop(session_id, None)

    def work():
        try:
            action()
        except ValueError as e:
            errors[session_id] = str(e)
        except Exception as e:                  # keep the session usable and visible to the operator
            errors[session_id] = f"internal error: {type(e).__name__}: {e}"
            runtime.store.trace(session_id, "error", error=errors[session_id])
        finally:
            s.busy = False
            lock.release()

    threading.Thread(target=work, daemon=True).start()
    return _view(session_id)


@app.post("/api/sessions/{session_id}/messages")
def message(session_id: str, body: Message):
    return _spawn(session_id, lambda: runtime.message(session_id, body.text))


@app.post("/api/sessions/{session_id}/record")
def record(session_id: str, body: RecordDecision):
    return _spawn(session_id, lambda: runtime.record(session_id, [r.model_dump() for r in body.resolve], body.confirm))


@app.post("/api/sessions/{session_id}/goal")
def goal(session_id: str, body: GoalDecision):
    return _spawn(session_id, lambda: runtime.goal_decision(session_id, body.card_id, body.approve))


@app.post("/api/sessions/{session_id}/blocker")
def blocker(session_id: str, body: BlockerDecision):
    return _spawn(session_id, lambda: runtime.blocker_decision(session_id, body.card_id, body.choose, body.decline))


DIST = ROOT / "dist"
if (DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        target = DIST / path
        return FileResponse(target if path and target.is_file() else DIST / "index.html")
