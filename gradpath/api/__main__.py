"""Run the GradPath server: .venv\\Scripts\\python.exe -m gradpath.api [--port 8000]. Binds to 127.0.0.1 only."""
import argparse

import uvicorn

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=8000)
args = ap.parse_args()
uvicorn.run("gradpath.api.app:app", host="127.0.0.1", port=args.port, log_level="warning")
