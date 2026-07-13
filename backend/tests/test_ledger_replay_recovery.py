"""Regression: a failed ai_calls ledger row must never poison the idempotent
replay of the same client_mutation_id.

Before this fix, `_record_failed_call` wrote a `status='failed'` row keyed on
(project_id, client_mutation_id); a subsequent successful retry with the same
mutation id then collided on the unique index (UniqueViolation), permanently
breaking pending_provider / batch resume — the project's centerpiece recovery.
"""
from __future__ import annotations

import uuid

import pytest

from app.db import connect, encode, new_id
from app.gateway import complete, ProviderError


def _seed_project() -> str:
    db = connect()
    uid, pid = new_id(), new_id()
    db.execute(
        "INSERT INTO users (id,email,password_hash,display_name) VALUES (%s,%s,'h','a')",
        (uid, f"ledger-{uuid.uuid4().hex[:8]}@nc.dev"),
    )
    db.execute("INSERT INTO projects (id,name,owner_id) VALUES (%s,'ledger',%s)", (pid, uid))
    db.commit()
    db.close()
    return pid


def _seed_mock_route(task_type: str) -> None:
    """V2 defaults unrouted tasks to the real deepseek provider; this test
    drives the ledger via the guarded mock, so it declares its route."""
    db = connect()
    db.execute(
        "INSERT INTO model_routes (id, task_type, provider, model, params, fallback_json) "
        "VALUES (%s,%s,'mock','mock',%s,%s) ON CONFLICT(task_type) DO NOTHING",
        (new_id(), task_type, encode({}), encode([])),
    )
    db.commit()
    db.close()


def _mutation_rows(project_id: str, mutation_id: str) -> list[dict]:
    db = connect()
    rows = db.execute(
        "SELECT status FROM ai_calls WHERE project_id=%s AND client_mutation_id=%s",
        (project_id, mutation_id),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def test_failed_call_then_successful_retry_same_mutation_id(monkeypatch):
    """provider down -> failed ledger row; provider recovers -> retry succeeds,
    the failed row is upgraded in place, and a third call replays cleanly."""
    pid = _seed_project()
    mutation = f"resume:{uuid.uuid4().hex}"
    task = f"probe_{uuid.uuid4().hex[:6]}"  # arbitrary non-structured task_type
    _seed_mock_route(task)

    # Attempt 1: mock gate closed -> ProviderError, a failed row is written.
    monkeypatch.setenv("NOVELCRAFT_ENV", "development")
    monkeypatch.setenv("NOVELCRAFT_ALLOW_MOCK", "false")
    with pytest.raises(ProviderError):
        complete(run_id=None, node_key=None, project_id=pid, task_type=task,
                 prompt_name="editor.polish", variables={"selection": "x", "instruction": ""},
                 client_mutation_id=mutation)
    assert _mutation_rows(pid, mutation) == [{"status": "failed"}]

    # Attempt 2: provider recovers (mock allowed) with the SAME mutation id.
    monkeypatch.setenv("NOVELCRAFT_ENV", "test")
    monkeypatch.setenv("NOVELCRAFT_ALLOW_MOCK", "true")
    out = complete(run_id=None, node_key=None, project_id=pid, task_type=task,
                   prompt_name="editor.polish", variables={"selection": "x", "instruction": ""},
                   client_mutation_id=mutation)
    assert "text" in out
    rows = _mutation_rows(pid, mutation)
    assert rows == [{"status": "succeeded"}], f"expected the failed row upgraded in place, got {rows}"

    # Attempt 3: pure replay returns the ledgered output without a new row.
    replay = complete(run_id=None, node_key=None, project_id=pid, task_type=task,
                      prompt_name="editor.polish", variables={"selection": "x", "instruction": ""},
                      client_mutation_id=mutation)
    assert replay.get("text") == out.get("text")
    assert len(_mutation_rows(pid, mutation)) == 1
