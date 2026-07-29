#!/bin/sh
# Run the backend quality gate against an isolated real PostgreSQL database.
set -e

cd "$(dirname "$0")/../backend"
PY=".venv/bin/python"
[ -x "$PY" ] || PY="python"

if [ -z "${DATABASE_URL:-}" ]; then
  command -v createdb >/dev/null 2>&1 || {
    echo "DATABASE_URL 未设置，且本机没有 createdb，拒绝让测试使用开发库" >&2
    exit 1
  }
  GATE_DB_NAME="${NOVELCRAFT_GATE_DB_NAME:-starlume_backend_gate}"
  createdb "$GATE_DB_NAME" 2>/dev/null || true
  DATABASE_URL="postgresql://$(id -un)@localhost/$GATE_DB_NAME"
  export DATABASE_URL
fi

REDIS_URL="${NOVELCRAFT_TEST_REDIS_URL:-redis://localhost:6379/15}"
export REDIS_URL

"$PY" -m alembic upgrade head
"$PY" -m pytest tests/ -q
