"""Tool allowlist with strict argument models (D9, invariant 5).

Unknown tools, extra arguments and wrongly typed arguments are rejected; the rejection is returned to the model as
an observation and counts toward the turn budget. The schemas sent to Ollama are generated from these models.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .prompts import TOOL_SPECS


class Args(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class NoArgs(Args):
    pass


class RetrieveArgs(Args):
    query: str = Field(min_length=1, max_length=200)


class ProposeGoalArgs(Args):
    horizon_end: str | None = Field(None, description="last term of the plan, e.g. 2570/2")
    default_cap: int | None = Field(None, description="maximum credits per regular term, 1-22")
    caps: dict[str, int] | None = Field(None, description="per-term caps, e.g. {\"2570/1\": 18}")
    allow_summer: bool | None = None
    must_take: list[str] | None = Field(None, description="course IDs the student must take")
    avoid: list[str] | None = Field(None, description="course IDs to leave out")
    interests: list[str] | None = Field(None, description="topics the student likes (soft)")


AskField = Literal["horizon", "caps", "allow_summer", "must_take", "avoid", "interests", "record"]


class AskArgs(Args):
    kind: Literal["clarify", "need_info"]
    fields: list[AskField] = Field(min_length=1)
    question: str = Field(min_length=1, max_length=600)


class ReplyArgs(Args):
    kind: Literal["info", "decline"]
    message: str = Field(min_length=1, max_length=1500)
    citations: list[str] = []


class SolveArgs(Args):
    preferred_course_ids: list[str] = Field(default_factory=list, max_length=12)


class ValidateArgs(Args):
    plan_id: str


class SubmitArgs(Args):
    status: Literal["plan", "blocker"]
    ref: str
    explanation: str = Field(min_length=1, max_length=1500)


ARGS: dict[str, type[Args]] = {
    "audit": NoArgs, "retrieve_courses": RetrieveArgs, "propose_goal": ProposeGoalArgs, "ask_user": AskArgs,
    "reply": ReplyArgs, "solve_plan": SolveArgs, "validate_plan": ValidateArgs, "submit_final": SubmitArgs,
}
TERMINAL_TOOLS = ("ask_user", "reply", "submit_final")


def _clean(schema: dict) -> dict:
    """Inline a pydantic JSON schema for Ollama: no titles, Optional[x] shown as x."""
    if isinstance(schema, dict):
        if "anyOf" in schema:
            options = [o for o in schema["anyOf"] if o.get("type") != "null"]
            if len(options) == 1:
                merged = {**options[0], **{k: v for k, v in schema.items() if k not in ("anyOf", "default")}}
                return _clean(merged)
        return {k: _clean(v) for k, v in schema.items() if k not in ("title", "default")}
    if isinstance(schema, list):
        return [_clean(v) for v in schema]
    return schema


def schemas(names: list[str] | None = None) -> list[dict]:
    out = []
    for name, model in ARGS.items():
        if names is not None and name not in names:
            continue
        params = _clean(model.model_json_schema())
        params.pop("additionalProperties", None)
        params.setdefault("properties", {})
        out.append({"type": "function", "function": {"name": name, "description": TOOL_SPECS[name], "parameters": params}})
    return out


def parse(name: str, raw) -> tuple[Args | None, str | None]:
    """Return (validated args, None) or (None, error message for the model)."""
    if name not in ARGS:
        return None, f"unknown tool {name!r}; allowed: {', '.join(ARGS)}"
    if raw in (None, ""):
        raw = {}
    if not isinstance(raw, dict):
        return None, f"arguments of {name} must be a JSON object"
    raw = {k: v for k, v in raw.items() if v is not None}   # omitted and null optional fields mean the same
    try:
        return ARGS[name].model_validate(raw), None
    except ValidationError as e:
        errs = "; ".join(f"{'.'.join(str(p) for p in err['loc']) or name}: {err['msg']}" for err in e.errors()[:4])
        allowed = ", ".join(ARGS[name].model_fields) or "none, call it with {}"
        return None, f"invalid arguments for {name}: {errs}. Allowed arguments: {allowed}"
