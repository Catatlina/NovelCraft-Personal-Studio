"""Ordinal-slot recovery contracts for chapter batches (NC-SC-004)."""
from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


class _Cursor:
    def __init__(self, one=None, many=None):
        self.one = one
        self.many = many or []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


def test_each_batch_ordinal_has_a_stable_unique_generation_key():
    from app.workers.tasks import _batch_generation_key

    first = _batch_generation_key("batch-1", 1)
    assert first == _batch_generation_key("batch-1", 1)
    assert first != _batch_generation_key("batch-1", 2)
    assert first != _batch_generation_key("batch-2", 1)
    assert "batch-1" in first and "1" in first


def test_resume_reuses_persisted_draft_and_continues_review(monkeypatch):
    """A provider failure between draft commit and review cannot create a new chapter."""
    from app.workers import tasks

    existing = {
        "id": "chapter-slot-2",
        "generation_key": "batch:batch-1:ordinal:2:v1",
        "title": "第二章",
        "body": {"type": "doc", "content": [{"type": "paragraph", "text": "草稿"}]},
        "meta": {"batch_id": "batch-1", "ordinal": 2, "quality_status": "draft_pending_review"},
    }
    reviewed = []

    class Db:
        def execute(self, sql, _params=()):
            if "FROM contents" in sql and "generation_key" in sql:
                return _Cursor(existing)
            return _Cursor()

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(tasks, "connect", lambda: Db())
    monkeypatch.setattr(
        tasks.gen_next_chapter_task,
        "run",
        lambda *_args, **_kwargs: pytest.fail("resume must not generate another draft"),
    )
    monkeypatch.setattr(
        tasks,
        "_review_and_finalize_chapter",
        lambda chapter_id, *_args, **_kwargs: reviewed.append(chapter_id)
        or {"accepted": True, "review_status": "reviewed", "final_score": 90,
            "rewrite_attempts": 0, "title": existing["title"], "body": ["草稿"]},
    )

    result = tasks._run_batch_slot(
        {"id": "batch-1", "novel_id": "novel-1", "project_id": "project-1"}, 2
    )

    assert result["chapter_id"] == "chapter-slot-2"
    assert reviewed == ["chapter-slot-2"]


def test_progress_is_recounted_from_unique_chapter_slot_metadata(monkeypatch):
    from app.workers import tasks

    rows = [
        {"id": "c1", "meta": {"batch_id": "batch-1", "ordinal": 1, "quality_status": "accepted"}},
        {"id": "c1-duplicate", "meta": {"batch_id": "batch-1", "ordinal": 1, "quality_status": "accepted"}},
        {"id": "c2", "meta": {"batch_id": "batch-1", "ordinal": 2, "quality_status": "needs_review"}},
        {"id": "c3", "meta": {"batch_id": "batch-1", "ordinal": 3, "quality_status": "draft_pending_review"}},
        {"id": "old", "meta": {"batch_id": "other-batch", "ordinal": 1, "quality_status": "accepted"}},
    ]

    class Db:
        def __init__(self):
            self.update = None

        def execute(self, sql, params=()):
            if sql.lstrip().startswith("SELECT"):
                return _Cursor(many=rows)
            self.update = (sql, params)
            return _Cursor()

    db = Db()
    progress = tasks._recount_batch_progress(db, "batch-1")

    assert progress == {
        "generated_count": 3,
        "reviewed_count": 2,
        "accepted_count": 1,
        "needs_review_count": 1,
        "completed_count": 2,
    }
    assert db.update is not None


def test_batch_runner_is_slot_based_not_completed_counter_based():
    from app.workers import tasks

    names = set(tasks.batch_generate_chapters_task.run.__code__.co_names)
    assert "_run_batch_slot" in names
    assert "_recount_batch_progress" in names
    source_constants = " ".join(str(value) for value in tasks.batch_generate_chapters_task.run.__code__.co_consts)
    assert "completed_count = completed_count + 1" not in source_constants


def test_cancel_response_explains_in_flight_slot(monkeypatch):
    from app import main

    batch = {"id": "batch-1", "project_id": "project-1", "status": "running", "current_ordinal": 3}

    class Db:
        def execute(self, sql, _params=()):
            if sql.lstrip().startswith("SELECT"):
                return _Cursor(batch)
            return _Cursor()

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(main, "connect", lambda: Db())
    monkeypatch.setattr(main, "ensure_project_member", lambda *_args, **_kwargs: None)

    response = main.cancel_generation_batch("batch-1", {"id": "owner-1"})
    data = response.data
    assert data["status"] == "cancelled"
    assert data["in_flight"] is True
    assert data["current_ordinal"] == 3
    assert "后续" in data["message"] or "current" in data["message"].lower()


def test_legacy_batch_chapters_are_explicitly_unverified_by_migration():
    sql = (ROOT / "backend/alembic/versions/nc_sc004_slot_recovery.py").read_text(encoding="utf-8")

    assert "current_ordinal" in sql
    assert "start_seq" in sql
    assert "quality_status" in sql
    assert "legacy_unverified" in sql
