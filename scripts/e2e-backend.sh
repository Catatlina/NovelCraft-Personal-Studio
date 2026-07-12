#!/bin/sh
# E2E backend launcher — used by frontend/playwright.config.ts webServer.
# Picks the repo venv locally, falls back to system python in CI.
set -e
cd "$(dirname "$0")/../backend"
PY=".venv/bin/python"
[ -x "$PY" ] || PY="python"
exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "${E2E_BACKEND_PORT:-8100}"
