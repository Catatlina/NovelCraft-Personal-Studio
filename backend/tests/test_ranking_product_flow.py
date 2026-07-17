"""Product-level contract tests for the ranking-driven novel workflow.

These tests deliberately avoid live ranking websites and a running Celery worker.
They protect the public API, persistence schema, explicit source-failure semantics,
and the automatic path that must not pause for a title already selected by ranking.
"""
import json
from pathlib import Path

import pytest
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "backend/alembic/versions/b73d14f0c2a1_add_ranking_product_flow.py"


def test_ranking_routes_are_registered_on_application():
    from app.main import app

    routes = {(path, method.upper()) for path, operations in app.openapi()["paths"].items() for method in operations}
    required = {
        ("/api/v1/ranking/sources", "GET"),
        ("/api/v1/ranking/sources/{source_key}/scan", "POST"),
        ("/api/v1/ranking/snapshots", "GET"),
        ("/api/v1/ranking/snapshots/{snapshot_id}", "GET"),
        ("/api/v1/ranking/snapshots/{snapshot_id}/analyze", "POST"),
        ("/api/v1/ranking/topics", "GET"),
        ("/api/v1/ranking/topics/{topic_id}/generate-book", "POST"),
        ("/api/v1/ranking/library/books", "GET"),
        ("/api/v1/library/books", "GET"),
    }
    assert required <= routes


def test_ranking_migration_has_dedicated_traceable_product_tables():
    sql = MIGRATION.read_text(encoding="utf-8")

    for table in (
        "ranking_sources",
        "ranking_snapshots",
        "ranking_items",
        "market_analyses",
        "topic_candidates",
    ):
        assert f"CREATE TABLE {table}" in sql
        assert f"DROP TABLE IF EXISTS {table}" in sql

    assert "UNIQUE(project_id, source_key)" in sql
    assert "UNIQUE(snapshot_id, rank_no)" in sql
    assert "snapshot_id UUID NOT NULL REFERENCES ranking_snapshots" in sql
    assert "analysis_id UUID NOT NULL REFERENCES market_analyses" in sql
    assert "novel_id UUID REFERENCES contents(id)" in sql


def test_all_supported_ranking_sources_have_registered_fetchers():
    from app.api.v1.ranking import SOURCE_NAMES
    from app.services.ranking_adapter import RANKING_FETCHERS

    assert set(RANKING_FETCHERS) == set(SOURCE_NAMES)
    expected = {"fanqie", "qidian", "zongheng", "qqread", "jjwxc", "sfacg", "xxsy"}
    assert set(RANKING_FETCHERS) >= expected, f"Missing: {expected - set(RANKING_FETCHERS)}"
    assert all(callable(fetcher) for fetcher in RANKING_FETCHERS.values())


class _ScanDb:
    def __init__(self):
        self.statements = []
        self.committed = False
        self.closed = False

    def execute(self, sql, params=()):
        self.statements.append((" ".join(sql.split()), params))
        return self

    def fetchone(self):
        return {"id": "source-id"}

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def test_scan_source_failure_is_persisted_and_raised_as_gateway_error(monkeypatch):
    """A broken upstream must never become a successful empty snapshot."""
    from app.api.v1 import ranking

    db = _ScanDb()
    monkeypatch.setattr(ranking, "connect", lambda: db)
    monkeypatch.setattr(ranking, "require_member", lambda *_args, **_kwargs: None)
    monkeypatch.setitem(
        ranking.RANKING_FETCHERS,
        "fanqie",
        lambda: [{"source": "fanqie", "error": "upstream timeout", "degraded": True}],
    )

    with pytest.raises(HTTPException) as exc_info:
        ranking.scan_source("fanqie", "project-id", {"id": "user-id"})

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail["code"] == "RANKING_SOURCE_FAILED"
    assert exc_info.value.detail["reason"] == "upstream timeout"
    assert db.committed and db.closed
    persisted_sql = " ".join(sql for sql, _ in db.statements)
    assert "ranking_snapshots" in persisted_sql and "'failed'" in persisted_sql
    assert "'succeeded'" not in persisted_sql


class _RunDb:
    def __init__(self):
        self.statements = []
        self.committed = False
        self.closed = False

    def execute(self, sql, params=()):
        self.statements.append((" ".join(sql.split()), params))
        return self

    def fetchone(self):
        return {
            "id": "novel-id",
            "meta": {"idea": "榜单原创题材", "genre": "玄幻", "style": "商业网文"},
        }

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def test_create_run_with_selected_title_still_runs_full_planning(monkeypatch):
    from app.workers import tasks

    db = _RunDb()
    dispatched = []
    monkeypatch.setattr(tasks, "connect", lambda: db)
    monkeypatch.setattr(tasks.execute_bootstrap, "delay", lambda *args: dispatched.append(args))

    run_id = tasks.create_run(
        "project-id",
        "novel-id",
        "api-key",
        "https://provider.example/v1",
        "model-id",
        selected_title="榜单原创书名",
    )

    assert run_id
    assert db.committed and db.closed
    assert dispatched == [(run_id, "plan_idea", "api-key", "https://provider.example/v1", "model-id")]

    # A ranking title is only a suggestion. It must not fabricate planning
    # success, bypass creative-bible decomposition, or confirm itself.
    # creative-bible decomposition module.
    skip_updates = [params for sql, params in db.statements
                    if "UPDATE run_nodes SET status='succeeded'" in sql and params and params[-2] == run_id]
    assert skip_updates == []
    run_insert = next(params for sql, params in db.statements if sql.startswith("INSERT INTO workflow_runs"))
    context = json.loads(run_insert[6])
    assert context["suggested_title"] == "榜单原创书名"
    assert "selected_title" not in context
