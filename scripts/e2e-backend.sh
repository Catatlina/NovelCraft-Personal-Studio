#!/bin/sh
# E2E backend launcher — used by frontend/playwright.config.ts webServer.
# Picks the repo venv locally, falls back to system python in CI.
# Starts a real Celery worker alongside uvicorn so async workflow tasks
# (novel wizard runs, chapter generation) are actually consumed during E2E.
set -e
cd "$(dirname "$0")/../backend"
PY=".venv/bin/python"
[ -x "$PY" ] || PY="python"

"$PY" -m celery -A app.workers.celery_app worker --loglevel=info --concurrency=2 &
WORKER_PID=$!

"$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "${E2E_BACKEND_PORT:-8100}" &
UVICORN_PID=$!

trap 'kill "$WORKER_PID" "$UVICORN_PID" 2>/dev/null || true' EXIT INT TERM
wait "$UVICORN_PID"
