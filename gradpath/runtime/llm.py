"""Ollama chat client with tools (D12). Always 127.0.0.1: `localhost` costs about 2 s per call on Windows."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

HOST = os.environ.get("GRADPATH_OLLAMA", "http://127.0.0.1:11434")
MODEL = os.environ.get("GRADPATH_MODEL", "qwen3:8b")
OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 8192, "num_predict": 1200}


class ModelUnavailable(Exception):
    """The model could not be reached or did not answer in time; the turn ends in STOP_UNVERIFIED."""


def _request(path: str, body: dict | None, timeout: float) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{HOST}{path}", data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        raise ModelUnavailable(f"{type(e).__name__}: {e}") from e


class OllamaLLM:
    def __init__(self, model: str = MODEL):
        self.model = model

    def chat(self, messages: list[dict], tools: list[dict], timeout: float) -> tuple[dict, dict]:
        if timeout <= 0:
            raise ModelUnavailable("no time left in the turn budget")
        body = {"model": self.model, "messages": messages, "tools": tools, "stream": False, "think": False,
                "options": OPTIONS, "keep_alive": "60m"}
        t0 = time.monotonic()
        data = _request("/api/chat", body, timeout)
        stats = {k: data.get(k) for k in ("total_duration", "load_duration", "prompt_eval_count",
                                          "prompt_eval_duration", "eval_count", "eval_duration")}
        stats["wall_s"] = round(time.monotonic() - t0, 3)
        return data["message"], stats


class FaultyLLM:
    """Fault injection `model_unavailable` (UAT-05): every call fails as if Ollama were down."""
    model = MODEL

    def chat(self, messages, tools, timeout):
        raise ModelUnavailable("fault injected: model_unavailable")


def model_info(model: str = MODEL) -> dict:
    """Ollama version and model digest for the run record; empty values when Ollama is down."""
    info = {"model": model, "ollama_version": None, "digest": None}
    try:
        info["ollama_version"] = _request("/api/version", None, 3).get("version")
        for m in _request("/api/tags", None, 3).get("models", []):
            if m.get("name") == model or m.get("model") == model:
                info["digest"] = m.get("digest", "")[:12]
    except ModelUnavailable:
        pass
    return info


def warm_up(model: str = MODEL) -> float:
    """Load the model into memory; returns the seconds it took."""
    t0 = time.monotonic()
    _request("/api/chat", {"model": model, "messages": [{"role": "user", "content": "ok"}], "stream": False,
                           "think": False, "options": {**OPTIONS, "num_predict": 1}, "keep_alive": "60m"}, 300)
    return round(time.monotonic() - t0, 2)
