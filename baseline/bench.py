"""Model benchmark for slide 11 (W9 protocol).

Same prompt + settings for every model, temperature 0, fixed num_predict,
1 warm-up run (not recorded), 3 measured runs, model unloaded between models.

Usage:
  python bench.py                         # qwen3:4b and qwen3:8b
  python bench.py --models qwen3:4b qwen3:8b --runs 3
Outputs: results/bench_runs.csv, results/bench_summary.md
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import shutil
import statistics as st
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 8192, "num_predict": 256}
PROMPT = ("A Computer Engineering student has completed C101 and G101. C102 is required and is a "
          "prerequisite of E202 (Artificial Intelligence I). The student wants to focus on AI and take at "
          "most 3 credits per term over the next two terms. Explain, step by step, which course to take in "
          "each term and why.")


def post(host, path, body, stream=False):
    req = urllib.request.Request(f"{host}{path}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=600)


def get(host, path):
    with urllib.request.urlopen(f"{host}{path}", timeout=30) as r:
        return json.loads(r.read())


def unload(host, model):
    try:
        post(host, "/api/generate", {"model": model, "keep_alive": 0}).read()
    except Exception:
        pass
    time.sleep(2)


class VramPeak:
    """Polls nvidia-smi for peak used memory (MiB). Silently disabled if unavailable."""
    def __init__(self):
        self.ok = shutil.which("nvidia-smi") is not None
        self.peak, self._stop = 0, threading.Event()

    def _poll(self):
        while not self._stop.is_set():
            try:
                out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                     capture_output=True, text=True, timeout=5).stdout
                self.peak = max(self.peak, max(int(x) for x in out.split()))
            except Exception:
                pass
            time.sleep(0.25)

    def __enter__(self):
        if self.ok:
            threading.Thread(target=self._poll, daemon=True).start()
        return self

    def __exit__(self, *a):
        self._stop.set()


def one_run(host, model, think_ok=True):
    body = {"model": model, "messages": [{"role": "user", "content": PROMPT}],
            "stream": True, "options": OPTIONS, "keep_alive": "10m"}
    if think_ok:
        body["think"] = False
    t0 = time.perf_counter(); ttft = None; final = None
    with post(host, "/api/chat", body) as r:
        for line in r:
            if not line.strip():
                continue
            chunk = json.loads(line)
            if ttft is None and chunk.get("message", {}).get("content"):
                ttft = time.perf_counter() - t0
            if chunk.get("done"):
                final = chunk
    e2e = time.perf_counter() - t0
    ns = 1e9
    return {
        "ttft_s": round(ttft or e2e, 3),
        "e2e_s": round(e2e, 3),
        "load_s": round(final.get("load_duration", 0) / ns, 3),
        "prompt_tokens": final.get("prompt_eval_count", 0),
        "prompt_tok_s": round(final.get("prompt_eval_count", 0) / max(final.get("prompt_eval_duration", 1), 1) * ns, 1),
        "gen_tokens": final.get("eval_count", 0),
        "gen_tok_s": round(final.get("eval_count", 0) / max(final.get("eval_duration", 1), 1) * ns, 1),
    }


def gpu_fit(host, model):
    for m in get(host, "/api/ps").get("models", []):
        if m.get("name") == model or m.get("model") == model:
            size, vram = m.get("size", 0), m.get("size_vram", 0)
            pct = round(100 * vram / size) if size else 0
            return {"loaded_gb": round(size / 1e9, 2), "vram_gb": round(vram / 1e9, 2), "gpu_pct": pct,
                    "digest": m.get("digest", "")[:12]}
    return {"loaded_gb": None, "vram_gb": None, "gpu_pct": None, "digest": ""}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["qwen3:4b", "qwen3:8b"])
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--host", default="http://localhost:11434")
    a = ap.parse_args()
    (HERE / "results").mkdir(exist_ok=True)

    version = get(a.host, "/api/version").get("version", "?")
    gpu = "unknown GPU"
    if shutil.which("nvidia-smi"):
        gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                             capture_output=True, text=True).stdout.strip()
    print(f"Ollama {version} | {gpu} | {platform.platform()}")

    rows, summary = [], []
    for model in a.models:
        for other in a.models:
            unload(a.host, other)
        print(f"\n== {model}: warm-up")
        try:
            one_run(a.host, model)
            think_ok = True
        except urllib.error.HTTPError:
            one_run(a.host, model, think_ok=False); think_ok = False
        runs = []
        with VramPeak() as vp:
            for i in range(a.runs):
                r = one_run(a.host, model, think_ok)
                r.update({"model": model, "run": i + 1}); runs.append(r); rows.append(r)
                print(f"  run {i+1}: gen {r['gen_tok_s']} tok/s | prompt {r['prompt_tok_s']} tok/s | "
                      f"TTFT {r['ttft_s']} s | e2e {r['e2e_s']} s")
        fit = gpu_fit(a.host, model)
        summary.append({"model": model, **fit, "peak_vram_mib": vp.peak if vp.ok else None,
                        "gen_tok_s": round(st.mean(r["gen_tok_s"] for r in runs), 1),
                        "prompt_tok_s": round(st.mean(r["prompt_tok_s"] for r in runs), 1),
                        "ttft_s": round(st.mean(r["ttft_s"] for r in runs), 2),
                        "e2e_s": round(st.mean(r["e2e_s"] for r in runs), 2)})
        unload(a.host, model)

    with open(HERE / "results/bench_runs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

    md = [f"Ollama {version} | {gpu} | num_ctx {OPTIONS['num_ctx']} | num_predict {OPTIONS['num_predict']} "
          f"| temp 0 | 1 warm-up + {a.runs} runs (mean)", "",
          "| Model | Gen tok/s | Prompt tok/s | TTFT (s) | Loaded / in VRAM | GPU fit | Peak VRAM |",
          "|---|---|---|---|---|---|---|"]
    for s in summary:
        md.append(f"| {s['model']} | {s['gen_tok_s']} | {s['prompt_tok_s']} | {s['ttft_s']} | "
                  f"{s['loaded_gb']} / {s['vram_gb']} GB | {s['gpu_pct']}% GPU | "
                  f"{s['peak_vram_mib']} MiB |")
    md += ["", "Slide 11 'GPU fit' cell:"] + [
        f"- {s['model']}: {s['gpu_pct']}% GPU, {s['vram_gb']} GB @ ctx 8192, {s['gen_tok_s']} tok/s" for s in summary]
    (HERE / "results/bench_summary.md").write_text("\n".join(md), encoding="utf-8")
    print("\n" + "\n".join(md))


if __name__ == "__main__":
    main()
