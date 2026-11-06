#!/usr/bin/env bash
# Set up a fresh macOS (Apple silicon) machine for the UAT (docs/dev-setup.md, "UAT machine").
# Needs: Python 3.13, Node 22.13+ with corepack, Ollama running (brew install python@3.13 node ollama;
# brew services start ollama). Run from the repository root:
#   bash scripts/uat_setup.sh
set -euo pipefail

PY=${PY:-python3.13}
if [ ! -d .venv ]; then "$PY" -m venv .venv; fi
.venv/bin/python -m pip install --quiet -r requirements.txt

corepack pnpm install
corepack pnpm build

ollama pull qwen3:8b
ollama list

.venv/bin/python -m pytest -q
.venv/bin/python scripts/uat_check.py --quick
echo "Setup done. Start the server with: caffeinate -dims .venv/bin/python -m gradpath.api"
