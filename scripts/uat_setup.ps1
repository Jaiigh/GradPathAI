# Set up a fresh Windows machine for the UAT (docs/dev-setup.md, "UAT machine").
# Needs: Python 3.13 (py launcher), Node 20+ with corepack, Ollama. Run from the repository root:
#   powershell -ExecutionPolicy Bypass -File scripts\uat_setup.ps1
$ErrorActionPreference = "Stop"

if (-not (Test-Path .venv)) { py -3 -m venv .venv }
.venv\Scripts\python.exe -m pip install --quiet -r requirements.txt

corepack pnpm install
corepack pnpm build

ollama pull qwen3:8b
ollama list

.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts\uat_check.py --quick
Write-Host "Setup done. Start the server with: .venv\Scripts\python.exe -m gradpath.api"
