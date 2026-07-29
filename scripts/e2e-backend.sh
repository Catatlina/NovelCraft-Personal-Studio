#!/bin/sh
# E2E backend launcher — used by frontend/playwright.config.ts webServer.
# Picks the repo venv locally, falls back to system python in CI.
# Starts a real Celery worker alongside uvicorn so async workflow tasks
# (novel wizard runs, chapter generation) are actually consumed during E2E.
set -e
cd "$(dirname "$0")/../backend"
PY=".venv/bin/python"
[ -x "$PY" ] || PY="python"

if [ -z "${DATABASE_URL:-}" ]; then
  command -v createdb >/dev/null 2>&1 || {
    echo "DATABASE_URL 未设置，且本机没有 createdb，拒绝让 E2E 使用开发库" >&2
    exit 1
  }
  E2E_DB_NAME="${NOVELCRAFT_E2E_DB_NAME:-starlume_e2e}"
  createdb "$E2E_DB_NAME" 2>/dev/null || true
  DATABASE_URL="postgresql://$(id -un)@localhost/$E2E_DB_NAME"
  export DATABASE_URL
fi

# The E2E stack uses a persistent real PostgreSQL database locally. Always
# advance it before serving requests so UI fallbacks cannot hide missing-table
# errors from an older developer database.
"$PY" -m alembic upgrade head

"$PY" -m celery -A app.workers.celery_app worker --loglevel=info --concurrency=2 &
WORKER_PID=$!

"$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "${E2E_BACKEND_PORT:-8100}" &
UVICORN_PID=$!

trap 'kill "$WORKER_PID" "$UVICORN_PID" 2>/dev/null || true' EXIT INT TERM
wait "$UVICORN_PID"
