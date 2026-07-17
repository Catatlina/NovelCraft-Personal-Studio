"""Contracts for turning a ranking topic into a traceable, AI-planned book (NC-SC-003)."""
from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from starlette.requests import Request


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": []})


class _Cursor:
    def __init__(self, one=None):
        self.one = one

    def fetchone(self):
        return self.one

    def fetchall(self):
        return []


class _BookDb:
    def __init__(self, *, role="owner", novel_id=None):
        self.role = role
        self.topic = {
            "id": "topic-1",
            "project_id": "project-1",
            "analysis_id": "analysis-1",
            "snapshot_id": "snapshot-1",
            "title": "雾城修理铺",
            "premise": "灾后城市里，修理师通过旧物记忆修复社区关系。",
            "genre": "科幻",
            "novel_id": novel_id,
            "status": "selected",
        }
        self.run_id = None
        self.statements: list[tuple[str, tuple]] = []
        self.commits = 0

    def execute(self, sql, params=()):
        compact = " ".join(sql.split())
        self.statements.append((compact, params))
        if "SELECT role FROM project_members" in compact:
            return _Cursor({"role": self.role})
        if "SELECT * FROM topic_candidates WHERE id=" in compact:
            return _Cursor(dict(self.topic))
        if "SELECT id FROM workflow_runs WHERE novel_id=" in compact:
            return _Cursor({"id": self.run_id} if self.run_id else None)
        if compact.startswith("UPDATE topic_candidates SET") and "novel_id=" in compact:
            self.topic["novel_id"] = params[0]
            self.topic["status"] = "generating"
        return _Cursor()

    def commit(self):
        self.commits += 1

    def close(self):
        pass


def _content_insert(db: _BookDb):
    return next((params for sql, params in db.statements if sql.startswith("INSERT INTO contents")), None)


def test_ranking_book_is_created_in_library_with_complete_source_lineage(monkeypatch):
    from app.api.v1 import ranking

    db = _BookDb()
    monkeypatch.setattr(ranking, "connect", lambda: db)
    response = ranking.generate_book(
        "topic-1", ranking.CreateBookRequest(auto_start=False), _request(), {"id": "owner-1"}
    )

    inserted = _content_insert(db)
    assert inserted is not None
    meta = json.loads(inserted[4]) if isinstance(inserted[4], str) else inserted[4]
    assert meta["source_type"] == "ranking_topic"
    assert meta["source_ref_id"] == "topic-1"
    assert meta["analysis_id"] == "analysis-1"
    assert meta["snapshot_id"] == "snapshot-1"
    assert meta["suggested_title"] == "雾城修理铺"
    assert "selected_title" not in meta
    assert inserted[2] == "待命名作品"
    assert response["data"]["novel_id"] == db.topic["novel_id"]
    assert response["data"]["status"] == "planning"
    assert db.commits == 1


def test_ranking_planning_nodes_use_gateway_and_have_structured_contracts():
    from app.prompt_registry import OUTPUT_CONTRACTS
    from app.workers import tasks

    expected = {
        "plan_idea": ("plan_idea", {"idea_expanded", "core_hook", "target_audience", "title_candidates", "creative_bible", "source_facts", "forbidden_changes", "downstream_deliverables"}),
        "plan_world_architecture": ("plan_world_architecture", {"worldview"}),
        "plan_character_system": ("plan_character_system", {"characters"}),
        "blueprint_chapter_outline": ("blueprint_chapter_outline", {"chapter_outlines"}),
    }
    nodes = {node_key: task_type for node_key, _kind, _agent, _title, task_type in tasks.BOOTSTRAP_NODES}
    for node_key, (task_type, required_keys) in expected.items():
        assert nodes[node_key] == task_type
        assert task_type in OUTPUT_CONTRACTS
        contract = OUTPUT_CONTRACTS[task_type]
        # Contracts may carry a trailing human annotation after the JSON example
        contract_json = contract[: contract.rfind("}") + 1]
        assert required_keys <= json.loads(contract_json).keys()
    task_impl = getattr(tasks.execute_bootstrap.run, "__wrapped__", tasks.execute_bootstrap.run)
    assert "complete" in task_impl.__code__.co_names


def test_provider_failure_keeps_retryable_run_state_without_fabricated_output(monkeypatch):
    from app.gateway import ProviderError
    from app.workers import tasks

    db = _BookDb(novel_id="novel-1")
    run = {"id": "run-1", "project_id": "project-1", "novel_id": "novel-1", "context": {"selected_title": "雾城修理铺"}}
    node = {"status": "pending", "kind": "agent"}

    def execute(sql, params=()):
        compact = " ".join(sql.split())
        db.statements.append((compact, params))
        if "SELECT * FROM workflow_runs WHERE id" in compact:
            return _Cursor(run)
        if "SELECT * FROM run_nodes WHERE run_id" in compact:
            return _Cursor(node)
        return _Cursor()

    db.execute = execute
    monkeypatch.setattr(tasks, "connect", lambda: db)
    monkeypatch.setattr(tasks, "complete", lambda **_kwargs: (_ for _ in ()).throw(ProviderError("offline")))
    monkeypatch.setattr(tasks, "_persist_output", lambda *_args: pytest.fail("provider failure must not persist AI output"))

    result = tasks.execute_bootstrap.run("run-1", "plan_idea")

    assert result["status"] == "failed"
    assert result["node_key"] == "plan_idea"
    writes = [(sql, params) for sql, params in db.statements if sql.startswith("UPDATE")]
    assert any(params and params[0] == "failed" for _sql, params in writes)
    assert not any("output =" in sql for sql, _params in writes)


def test_auto_start_false_then_true_creates_exactly_one_run(monkeypatch):
    from app.api.v1 import ranking
    from app.workers import tasks

    db = _BookDb()
    calls = []
    monkeypatch.setattr(ranking, "connect", lambda: db)

    def fake_create_run(*args, **kwargs):
        calls.append((args, kwargs))
        db.run_id = "run-1"
        return db.run_id

    monkeypatch.setattr(tasks, "create_run", fake_create_run)

    first = ranking.generate_book("topic-1", ranking.CreateBookRequest(auto_start=False), _request(), {"id": "owner-1"})
    second = ranking.generate_book("topic-1", ranking.CreateBookRequest(auto_start=True), _request(), {"id": "owner-1"})
    third = ranking.generate_book("topic-1", ranking.CreateBookRequest(auto_start=True), _request(), {"id": "owner-1"})

    assert first["data"]["run_id"] is None
    assert second["data"]["run_id"] == "run-1"
    assert third["data"]["status"] == "already_created"
    assert len(calls) == 1
    assert calls[0][1]["selected_title"] == "雾城修理铺"
    assert sum(sql.startswith("INSERT INTO contents") for sql, _ in db.statements) == 1


def test_existing_topic_and_run_are_idempotent(monkeypatch):
    from app.api.v1 import ranking
    from app.workers import tasks

    db = _BookDb(novel_id="novel-1")
    db.run_id = "run-1"
    monkeypatch.setattr(ranking, "connect", lambda: db)
    monkeypatch.setattr(tasks, "create_run", lambda *_args, **_kwargs: pytest.fail("must not start duplicate run"))

    response = ranking.generate_book(
        "topic-1", ranking.CreateBookRequest(auto_start=True), _request(), {"id": "owner-1"}
    )
    assert response["data"] == {"novel_id": "novel-1", "run_id": "run-1", "status": "already_created"}
    assert _content_insert(db) is None


def test_viewer_cannot_create_book_from_ranking_topic(monkeypatch):
    from app.api.v1 import ranking

    db = _BookDb(role="viewer")
    monkeypatch.setattr(ranking, "connect", lambda: db)

    with pytest.raises(HTTPException) as exc_info:
        ranking.generate_book(
            "topic-1", ranking.CreateBookRequest(auto_start=False), _request(), {"id": "viewer-1"}
        )
    assert exc_info.value.status_code == 403
    assert _content_insert(db) is None
