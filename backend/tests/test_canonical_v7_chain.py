"""Contracts for the single canonical V7 prose generation path."""
from __future__ import annotations

import uuid


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
    assert all(statement[1][4] == "run-1" for statement in node_updates)
    assert any("canonical_engine" in str(statement[1][1]) for statement in node_updates)


def test_canonical_bootstrap_keeps_pending_approval_truthful(monkeypatch):
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
                return Cursor({"context": {}})
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
        "run-approval",
        {
            "status": "pending_approval",
            "run_id": "v7-run-approval",
            "chapter_number": 1,
            "blocked_reason": "confidence 0.45 below threshold 0.70",
        },
    )

    node_updates = [
        statement for statement in db.statements if "UPDATE run_nodes" in statement[0]
    ]
    assert node_updates[0][1][0] == "waiting_human"
    assert all(statement[1][0] in {"waiting_human", "pending"} for statement in node_updates)
    workflow_update = next(
        statement for statement in db.statements if "UPDATE workflow_runs" in statement[0]
    )
    assert workflow_update[1][2] == "waiting_human"


def test_canonical_bootstrap_keeps_quality_rejection_actionable(monkeypatch):
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
                return Cursor({"context": {}})
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
        "run-review",
        {
            "status": "needs_review",
            "run_id": "v7-run-review",
            "chapter_number": 1,
            "v6_content_id": "chapter-review",
            "review_score": 78,
            "issues": [{"dimension": "continuity", "description": "断点"}],
        },
    )

    node_updates = [
        statement for statement in db.statements if "UPDATE run_nodes" in statement[0]
    ]
    assert node_updates[0][1][0] == "needs_review"
    assert all(statement[1][0] in {"needs_review", "skipped"} for statement in node_updates)
    assert "草稿已保存" in str(node_updates[0][1][3])


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


def test_first_chapter_complete_brief_reaches_quality_gate_without_hiding_confidence():
    import asyncio

    from app.v7.director.story_director import StoryDirector

    class Permission:
        async def evaluate(self, _decision_type, _confidence):
            return {
                "allowed": False,
                "level": "auto",
                "threshold": 0.70,
                "blocked_reason": "confidence 0.55 below threshold 0.70",
            }

    class Brain:
        async def record_decision(self, *_args, **_kwargs):
            return {"id": "decision-1"}

    director = object.__new__(StoryDirector)
    director.permission_system = Permission()
    director.brain = Brain()
    result = asyncio.run(
        director._decide(
            1,
            {
                "confidence": 0.55,
                "plot_success": True,
                "context_ready": True,
                "blockers": [],
                "gaps": [],
            },
            run_id=uuid.uuid4(),
        )
    )

    assert result["allowed"] is True
    assert result["policy_override"] == "first_chapter_context_complete"


def test_first_chapter_structural_blocker_still_waits_for_review():
    import asyncio

    from app.v7.director.story_director import StoryDirector

    class Permission:
        async def evaluate(self, _decision_type, _confidence):
            return {
                "allowed": False,
                "level": "auto",
                "threshold": 0.70,
                "blocked_reason": "confidence 0.55 below threshold 0.70",
            }

    class Brain:
        async def record_decision(self, *_args, **_kwargs):
            return {"id": "decision-2"}

    director = object.__new__(StoryDirector)
    director.permission_system = Permission()
    director.brain = Brain()
    result = asyncio.run(
        director._decide(
            1,
            {
                "confidence": 0.55,
                "plot_success": True,
                "context_ready": True,
                "blockers": ["前情缺失"],
                "gaps": [],
            },
            run_id=uuid.uuid4(),
        )
    )

    assert result["allowed"] is False
    assert "confidence" in result["blocked_reason"]


def test_batch_confidence_observation_reaches_prose_gate_without_waiving_blockers():
    import asyncio

    from app.v7.director.story_director import (
        BATCH_AUTOGENERATION_CONFIDENCE_FLOOR,
        StoryDirector,
    )

    class Permission:
        async def evaluate(self, _decision_type, _confidence):
            return {
                "allowed": False,
                "level": "auto",
                "threshold": 0.70,
                "blocked_reason": "confidence 0.60 below threshold 0.70",
            }

    class Brain:
        async def record_decision(self, *_args, **_kwargs):
            return {"id": "decision-batch"}

    director = object.__new__(StoryDirector)
    director.generation_metadata = {"batch_id": "batch-1"}
    director.permission_system = Permission()
    director.brain = Brain()
    result = asyncio.run(
        director._decide(
            7,
            {
                "confidence": 0.60,
                "plot_success": True,
                "context_ready": False,
                "blockers": [],
                "gaps": ["state is still warming up"],
            },
            run_id=uuid.uuid4(),
        )
    )

    assert result["allowed"] is True
    assert result["policy_override"] == "batch_quality_observation"
    assert result["confidence_floor"] == BATCH_AUTOGENERATION_CONFIDENCE_FLOOR


def test_batch_confidence_below_floor_still_waits_for_review():
    import asyncio

    from app.v7.director.story_director import StoryDirector

    class Permission:
        async def evaluate(self, _decision_type, _confidence):
            return {
                "allowed": False,
                "level": "auto",
                "threshold": 0.70,
                "blocked_reason": "confidence 0.50 below threshold 0.70",
            }

    class Brain:
        async def record_decision(self, *_args, **_kwargs):
            return {"id": "decision-batch-low"}

    director = object.__new__(StoryDirector)
    director.generation_metadata = {"batch_id": "batch-1"}
    director.permission_system = Permission()
    director.brain = Brain()
    result = asyncio.run(
        director._decide(
            7,
            {
                "confidence": 0.50,
                "plot_success": True,
                "context_ready": False,
                "blockers": [],
                "gaps": [],
            },
            run_id=uuid.uuid4(),
        )
    )

    assert result["allowed"] is False
    assert "confidence" in result["blocked_reason"]


def test_quality_rework_feedback_formats_labeled_risk_failures():
    from app.v7.director.story_director import _format_quality_failure

    assert _format_quality_failure({
        "dimension": "ai_feel",
        "actual": "high",
        "minimum": "resolved",
    }) == "ai_feel high/resolved"

    assert _format_quality_failure({
        "dimension": "pacing",
        "actual": 78,
        "minimum": 85,
    }) == "pacing 78/85"


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
