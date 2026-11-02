"""Synthetic persona fixtures (data/fixtures/personas); keys starting with "_" are documentation only."""
from __future__ import annotations

import json

from .contracts import StudentState
from .snapshot import ROOT

PERSONA_DIR = ROOT / "data" / "fixtures" / "personas"


def load_persona(name: str) -> StudentState:
    data = json.loads((PERSONA_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return StudentState(**{k: v for k, v in data.items() if not k.startswith("_")})


def persona_names() -> list[str]:
    return sorted(p.stem for p in PERSONA_DIR.glob("*.json"))
