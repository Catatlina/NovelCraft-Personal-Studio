"""NC-SC-004 continuous chapter pipeline contracts: strict output validation,
idempotent persistence, continuity risk report, and resumable batch generation."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request


ROOT = Path(__file__).resolve().parents[2]


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": []})


# --- strict output validation (docs/26: 空对象/缺字段不能落库为成功) -----------

def test_gen_next_chapter_output_is_strictly_validated():
    from app.gateway import OutputValidationError, validate_task_output

    with pytest.raises(OutputValidationError):
        validate_task_output("gen_next_chapter", {"chapter": {}})
    with pytest.raises(OutputValidationError):
        validate_task_output("gen_next_chapter", {})
    with pytest.raises(OutputValidationError):
        validate_task_output("gen_next_chapter", {"chapter": {"title": "第二章", "body": []}})


def test_gen_next_chapter_provider_output_passes_validation():
    from app.gateway import validate_task_output

    output = {"chapter": {"title": "第二章 风起", "body": ["第一段推进目标。", "第二段制造冲突。", "第三段留下钩子。"]}}
    validated = validate_task_output("gen_next_chapter", output)
    assert len(validated["chapter"]["body"]) >= 3


def test_editor_and_imitation_empty_outputs_are_rejected():
    from app.gateway import OutputValidationError, validate_task_output

    with pytest.raises(OutputValidationError):
        validate_task_output("editor_rewrite", {"text": "   "})
    with pytest.raises(OutputValidationError):
        validate_task_output("style_imitation", {
            "title": "样稿",
            "style_profile": {},
            "text": "过短",
        })


def test_draft_length_feedback_drives_real_retry():
    from app.workers.tasks import _draft_length_feedback

    assert "chapter too short" in _draft_length_feedback(
        {"chapter": {"body": ["不足三千字"]}}
    )
    assert _draft_length_feedback(
        {"chapter": {"body": ["足" * 3000]}}
    ) == ""


def test_quality_evidence_payload_keeps_score_dimensions_and_provenance():
    from app.workers.tasks import _quality_evidence_payload

    payload = _quality_evidence_payload(
        {"checks": {"characters": {"status": "pass"}, "timeline": {"status": "warning"}}},
        {"self_score": 84, "weaknesses": ["时间钩子偏弱"]},
    )
    assert payload == {
        "score": 84.0,
        "dimensions": {"characters": 90, "timeline": 65},
        "issues": ["时间钩子偏弱"],
        "source": "write_self_review+final_consistency_check",
    }


# --- idempotent persistence (docs/26: run/node 级生成键 + 数据库唯一索引兜底) --

def test_next_chapter_persistence_uses_stable_generation_key():
    source = (ROOT / "backend/app/workers/tasks.py").read_text(encoding="utf-8")
    assert "novel:{novel_id}:chapter:{next_seq}:v1" in source
    chapter_block = source.split("def _generate_next_chapter_unlocked")[1].split("def _continuity_report")[0]
    assert "ON CONFLICT (project_id, generation_key)" in chapter_block
    assert "client_mutation_id=generation_key" in chapter_block
    assert "ON CONFLICT (client_mutation_id)" in chapter_block


# --- continuity risk report ----------------------------------------------------

def test_continuity_report_flags_conflicts_and_due_foreshadows(monkeypatch):
    from app.services import narrative_engine
    from app.workers.tasks import _continuity_report

    monkeypatch.setattr(narrative_engine, "detect_cross_chapter_conflicts",
                        lambda novel_id: [{"type": "timeline_contradiction", "detail": "时间倒退"}])
    monkeypatch.setattr(narrative_engine, "check_foreshadow_due",
                        lambda novel_id, seq: [{"id": "f1", "content": "墨晶来历"}])
    report = _continuity_report("novel-1", 5)
    assert report["status"] == "flagged"
    assert {risk["type"] for risk in report["risks"]} == {"timeline_contradiction", "foreshadow_due"}


def test_continuity_report_is_clean_without_risks(monkeypatch):
    from app.services import narrative_engine
    from app.workers.tasks import _continuity_report

    monkeypatch.setattr(narrative_engine, "detect_cross_chapter_conflicts", lambda novel_id: [])
    monkeypatch.setattr(narrative_engine, "check_foreshadow_due", lambda novel_id, seq: [])
    report = _continuity_report("novel-1", 5)
    assert report["status"] == "clean"
    assert report["risks"] == []


def test_continuity_check_failure_is_recorded_not_hidden(monkeypatch):
    from app.services import narrative_engine
    from app.workers.tasks import _continuity_report

    def _boom(novel_id):
        raise RuntimeError("timeline table unavailable")

    monkeypatch.setattr(narrative_engine, "detect_cross_chapter_conflicts", _boom)
    report = _continuity_report("novel-1", 5)
    assert report["status"] == "unchecked"
    assert "timeline table unavailable" in report["error"]


# --- resumable batch generation ------------------------------------------------

class _Cursor:
    def __init__(self, one=None):
        self.one = one

    def fetchone(self):
        return self.one


class _BatchDb:
    def __init__(self, batch: dict):
        self.batch = batch
        self.statements: list[tuple[str, tuple]] = []

    def execute(self, sql, params=()):
        compact = " ".join(sql.split())
        self.statements.append((compact, params))
        if "SELECT cancel_requested" in compact:
            return _Cursor({"cancel_requested": self.batch["cancel_requested"]})
        if "SELECT * FROM generation_batches" in compact:
            return _Cursor(dict(self.batch))
        if "completed_count = completed_count + 1" in compact:
            self.batch["completed_count"] += 1
        if compact.startswith("UPDATE generation_batches SET status ="):
            pass
        return _Cursor()

    def commit(self):
        pass

    def close(self):
        pass


def _batch(completed: int = 0, requested: int = 5) -> dict:
    return {"id": "batch-1", "project_id": "project-1", "novel_id": "novel-1",
            "requested_count": requested, "completed_count": completed,
            "status": "failed", "cancel_requested": False}


def test_batch_resumes_from_completed_count(monkeypatch):
    from app.workers import tasks

    db = _BatchDb(_batch(completed=2, requested=5))
    monkeypatch.setattr(tasks, "connect", lambda: db)
    calls = []
    monkeypatch.setattr(tasks.gen_next_chapter_task, "run",
                        lambda *args, **kwargs: calls.append(args) or {"chapter_id": "c", "seq": len(calls)})

    result = tasks.batch_generate_chapters_task.run("batch-1")

    assert result["status"] == "succeeded"
    assert len(calls) == 3  # only the remaining chapters, no duplicates
    assert db.batch["completed_count"] == 5


def test_provider_failure_marks_batch_failed_with_cause(monkeypatch):
    from app.gateway import ProviderError
    from app.workers import tasks

    db = _BatchDb(_batch(completed=1, requested=3))
    monkeypatch.setattr(tasks, "connect", lambda: db)

    def _raise(*args, **kwargs):
        raise ProviderError("deepseek circuit breaker open")

    monkeypatch.setattr(tasks.gen_next_chapter_task, "run", _raise)
    result = tasks.batch_generate_chapters_task.run("batch-1")

    assert result["status"] == "failed"
    assert "circuit breaker" in result["reason"]
    assert any("status = 'failed'" in sql and "circuit breaker" in str(params)
               for sql, params in db.statements)
    assert db.batch["completed_count"] == 1  # progress is preserved for resume


def test_resume_endpoint_redispatches_interrupted_batch(monkeypatch):
    from app import main

    batch = {**_batch(completed=2, requested=5), "status": "failed"}

    class _MainDb(_BatchDb):
        pass

    db = _MainDb(batch)
    monkeypatch.setattr(main, "connect", lambda: db)
    monkeypatch.setattr(main, "ensure_project_member", lambda *args, **kwargs: None)
    dispatched = []

    class _Task:
        id = "celery-task-1"

    from app.workers import tasks
    monkeypatch.setattr(tasks.batch_generate_chapters_task, "delay",
                        lambda *args, **kwargs: dispatched.append(args) or _Task())

    response = main.resume_generation_batch(_request(), "batch-1", {"id": "user-1"})

    assert response.data["status"] == "pending"
    assert response.data["completed_count"] == 2
    assert dispatched == [("batch-1",)]
    assert any("cancel_requested = FALSE" in sql for sql, _ in db.statements)


def test_resume_rejects_batches_that_are_not_interrupted(monkeypatch):
    from app import main

    for status in ("running", "succeeded", "cancelled", "pending"):
        db = _BatchDb({**_batch(), "status": status})
        monkeypatch.setattr(main, "connect", lambda db=db: db)
        monkeypatch.setattr(main, "ensure_project_member", lambda *args, **kwargs: None)
        with pytest.raises(HTTPException) as exc_info:
            main.resume_generation_batch(_request(), "batch-1", {"id": "user-1"})
        assert exc_info.value.status_code == 409


def test_batch_recovery_migration_extends_current_head():
    sql = (ROOT / "backend/alembic/versions/nc_sc004_batch_recovery.py").read_text(encoding="utf-8")
    assert 'down_revision = "nc_fusion_account_tracking"' in sql
    assert "ADD COLUMN IF NOT EXISTS error" in sql


# --- schema-drift regression: continuity checks must run against the real DB ---
# (the old queries referenced foreshadowings.target_chapter and
#  timeline_events.character_name, columns that never existed)

@pytest.fixture
def seeded_novel():
    import uuid
    from fastapi.testclient import TestClient
    from app.db import connect, encode, new_id
    from app.main import app

    client = TestClient(app)
    email = f"pipeline-{uuid.uuid4().hex[:6]}@nc.dev"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    novel_id = client.post(f"/api/v1/projects/{project_id}/novels", headers=headers,
                           json={"idea": "连续性回归", "genre": "科幻", "style": "紧凑", "target_words": 10000}).json()["data"]["id"]
    db = connect()
    chapter_id = new_id()
    db.execute(
        "INSERT INTO contents (id, project_id, parent_id, type, title, body, meta, status) VALUES (%s,%s,%s,'chapter','第一章',%s,%s,'draft')",
        (chapter_id, project_id, novel_id, encode({"type": "doc", "content": []}), encode({"seq": 1})),
    )
    db.commit()
    db.close()
    return {"project_id": project_id, "novel_id": novel_id, "chapter_id": chapter_id}


def test_check_foreshadow_due_runs_against_real_schema(seeded_novel):
    from app.db import connect, new_id
    from app.services.narrative_engine import check_foreshadow_due

    db = connect()
    db.execute(
        "INSERT INTO foreshadowings (id, chapter_id, content, planned_resolve_chapter, status) VALUES (%s,%s,%s,%s,'planted')",
        (new_id(), seeded_novel["chapter_id"], "墨晶的来历", 1),
    )
    db.commit()
    db.close()

    due = check_foreshadow_due(seeded_novel["novel_id"], 1)
    assert [item["content"] for item in due] == ["墨晶的来历"]
    assert due[0]["target"] == 1
    assert due[0]["planted_at"] == "1"
    assert check_foreshadow_due(seeded_novel["novel_id"], 0) == []


def test_detect_conflicts_runs_against_real_schema(seeded_novel):
    from app.db import connect, new_id
    from app.services.narrative_engine import detect_cross_chapter_conflicts

    db = connect()
    for location in ("回声城邦", "旧城修理铺"):
        db.execute(
            "INSERT INTO entity_states (id, chapter_id, entity_type, entity_name, location) VALUES (%s,%s,'character','林序',%s)",
            (new_id(), seeded_novel["chapter_id"], location),
        )
    db.commit()
    db.close()

    conflicts = detect_cross_chapter_conflicts(seeded_novel["novel_id"])
    assert len(conflicts) == 1
    assert conflicts[0]["type"] == "entity_location_contradiction"
    assert conflicts[0]["character"] == "林序"


def test_version_reason_preserves_long_manual_review_feedback(seeded_novel):
    from app.db import connect, encode, new_id

    reason = "人工审核：增强场景冲突、生活质感、人物连续性和章末钩子。" * 5
    db = connect()
    version_id = new_id("ver")
    db.execute(
        """INSERT INTO versions (id, entity_type, entity_id, label, snapshot, reason)
           VALUES (%s, 'content', %s, 'before_manual_regenerate', %s, %s)""",
        (version_id, seeded_novel["chapter_id"], encode({"status": "before"}), reason),
    )
    db.commit()
    stored = db.execute("SELECT reason FROM versions WHERE id=%s", (version_id,)).fetchone()["reason"]
    db.close()

    assert len(reason) > 50
    assert stored == reason
