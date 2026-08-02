"""Contracts for the single canonical V7 prose generation path."""
from __future__ import annotations


def test_generation_task_canonical_flag_routes_to_v7(monkeypatch):
    from app.workers import tasks

    calls = []
    monkeypatch.setattr(
        tasks,
        "_run_canonical_v7_task",
        lambda *args, **kwargs: calls.append((args, kwargs)) or {
            "canonical_engine": "v7",
            "status": "completed",
        },
    )

    result = tasks.gen_next_chapter_task.run(
        "novel-1",
        "project-1",
        canonical=True,
        chapter_number=4,
    )

    assert result["canonical_engine"] == "v7"
    assert calls[0][1]["chapter_number"] == 4


def test_canonical_bootstrap_marks_legacy_writer_nodes_as_delegated(monkeypatch):
    from app.workers import tasks

    class Cursor:
        def __init__(self, row=None):
            self.row = row

        def fetchone(self):
            return self.row

    class DB:
        def __init__(self):
            self.statements = []

        def execute(self, sql, params=()):
            self.statements.append((" ".join(sql.split()), params))
            if "SELECT context FROM workflow_runs" in sql:
                return Cursor({"context": {"idea": "测试"}})
            return Cursor()

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    db = DB()
    monkeypatch.setattr(tasks, "connect", lambda: db)

    tasks._persist_canonical_bootstrap_result(
        "run-1",
        {
            "status": "completed",
            "run_id": "v7-run-1",
            "chapter_number": 1,
            "v6_content_id": "chapter-1",
            "review_score": 92,
            "dimension_scores": {"consistency": 90},
        },
    )

    node_updates = [
        statement for statement in db.statements if "UPDATE run_nodes" in statement[0]
    ]
    assert len(node_updates) == 8
    assert all(statement[1][1] == "run-1" for statement in node_updates)
    assert any("canonical_engine" in str(statement[1][0]) for statement in node_updates)


def test_v7_gateway_accepts_short_lived_provider_override():
    from app.v7.generation.generation_engine import AIGateway

    gateway = AIGateway(
        provider_config={
            "api_key": "request-only-key",
            "base_url": "https://provider.test/v1",
            "model": "request-model",
        }
    )

    assert gateway.api_key == "request-only-key"
    assert gateway.base_url == "https://provider.test/v1"
    assert gateway.default_model == "request-model"


def test_public_writer_agent_uses_canonical_v7_runtime(monkeypatch):
    from app.services.agent_registry import execute_agent

    captured = {}

    def fake_generate(novel_id, project_id, **kwargs):
        captured.update({"novel_id": novel_id, "project_id": project_id, **kwargs})
        return {
            "status": "completed",
            "canonical_engine": "v7",
            "chapter_number": 3,
            "title": "第三章",
            "content": "正文",
        }

    monkeypatch.setattr("app.v7.runtime.generate_v7_chapter_sync", fake_generate)
    result = execute_agent(
        "writer",
        "project-1",
        {"novel_id": "novel-1", "chapter_number": 3, "prompt": "继续承接"},
    )

    assert result["status"] == "succeeded"
    assert result["task_type"] == "v7_chapter_generation"
    assert result["output"]["canonical_engine"] == "v7"
    assert captured == {
        "novel_id": "novel-1",
        "project_id": "project-1",
        "chapter_number": 3,
        "prompt": "继续承接",
        "outline": None,
    }


def test_public_writer_agent_requires_novel_id():
    from app.services.agent_registry import execute_agent

    try:
        execute_agent("writer", "project-1", {})
    except ValueError as exc:
        assert "novel_id" in str(exc)
    else:
        raise AssertionError("writer agent must not reopen the legacy V6 path")


def test_v6_is_only_used_as_compatibility_fact_source():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    main_source = (root / "backend/app/main.py").read_text(encoding="utf-8")
    assert "canonical=True" in main_source
    runtime_source = (root / "backend/app/v7/runtime.py").read_text(encoding="utf-8")
    assert "Canonical V7 chapter runtime" in runtime_source
    assert "v6_compat_import" in runtime_source
