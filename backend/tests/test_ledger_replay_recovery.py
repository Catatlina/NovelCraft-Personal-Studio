"""Regression: a failed ai_calls ledger row must never poison the idempotent
replay of the same client_mutation_id.

Before this fix, `_record_failed_call` wrote a `status='failed'` row keyed on
(project_id, client_mutation_id); a subsequent successful retry with the same
mutation id then collided on the unique index (UniqueViolation), permanently
breaking failed-state batch resume — the project's centerpiece recovery.
"""
from __future__ import annotations

import uuid

import pytest

from app.db import connect, encode, new_id
from app.gateway import complete, OutputValidationError, ProviderError


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


def _seed_deepseek_route(task_type: str) -> None:
    db = connect()
    db.execute(
        "INSERT INTO model_routes (id, task_type, provider, model, params, fallback_json) "
        "VALUES (%s,%s,'deepseek','deepseek-chat',%s,%s) ON CONFLICT(task_type) DO NOTHING",
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
    _seed_deepseek_route(task)

    def provider_down(*_args, **_kwargs):
        raise ProviderError("provider outage")

    monkeypatch.setattr("app.gateway.circuit_breaker", lambda _provider: True)
    monkeypatch.setattr("app.gateway.record_failure", lambda _provider: None)
    monkeypatch.setattr("app.gateway.record_success", lambda _provider: None)
    monkeypatch.setattr("app.gateway._deepseek_complete", provider_down)

    # Attempt 1: provider down -> ProviderError, a failed row is written.
    with pytest.raises(ProviderError):
        complete(run_id=None, node_key=None, project_id=pid, task_type=task,
                 prompt_name="editor.polish", variables={"selection": "x", "instruction": ""},
                 client_mutation_id=mutation)
    assert _mutation_rows(pid, mutation) == [{"status": "failed"}]

    # Attempt 2: provider recovers with the SAME mutation id.
    monkeypatch.setattr("app.gateway._deepseek_complete", lambda *_args, **_kwargs: ({"text": "ok"}, 10, 5))
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


def test_non_json_structured_response_is_resampled(monkeypatch):
    pid = _seed_project()
    mutation = f"schema-resample:{uuid.uuid4().hex}"
    _seed_deepseek_route("regenerate_titles")
    attempts = 0

    def provider(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OutputValidationError("deepseek returned non-json for regenerate_titles")
        return ({"title_candidates": ["《甲》", "《乙》", "《丙》"]}, 10, 20)

    monkeypatch.setattr("app.gateway.circuit_breaker", lambda _provider: True)
    monkeypatch.setattr("app.gateway.record_failure", lambda _provider: None)
    monkeypatch.setattr("app.gateway.record_success", lambda _provider: None)
    monkeypatch.setattr("app.gateway._deepseek_complete", provider)

    output = complete(
        run_id=None,
        node_key="human_confirm_title",
        project_id=pid,
        task_type="regenerate_titles",
        prompt_name="bootstrap.regenerate_titles",
        variables={"idea": "测试创意", "title_candidates": []},
        client_mutation_id=mutation,
    )
    assert attempts == 2
    assert len(output["title_candidates"]) == 3
