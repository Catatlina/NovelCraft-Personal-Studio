"""Manual chapter rewrite must expose a real, authorized completion state."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def regeneration_case():
    from app.core.rate_limit import limiter
    from app.db import connect, encode, new_id
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"regeneration-{uuid.uuid4().hex[:8]}@nc.dev"
    token = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "test1234"},
    ).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    novel_id = client.post(
        f"/api/v1/projects/{project_id}/novels",
        headers=headers,
        json={"idea": "被退回重写的章节", "genre": "悬疑", "style": "克制", "target_words": 10000},
    ).json()["data"]["id"]
    chapter_id = new_id()
    original = {"type": "doc", "content": [{"type": "paragraph", "text": "原文必须保持。"}]}
    db = connect()
    db.execute(
        """INSERT INTO contents
           (id, project_id, parent_id, type, title, body, meta, status)
           VALUES (%s,%s,%s,'chapter','第二章 旧稿',%s,%s,'pending_review')""",
        (chapter_id, project_id, novel_id, encode(original), encode({"seq": 2})),
    )
    db.commit()
    db.close()
    return client, headers, chapter_id, original


def test_reject_persists_real_task_id(regeneration_case, monkeypatch):
    from app.db import connect
    from app.workers import tasks

    client, headers, chapter_id, _original = regeneration_case
    monkeypatch.setattr(
        tasks.regenerate_chapter_task,
        "delay",
        lambda *_args, **_kwargs: type("Task", (), {"id": "task-real-1"})(),
    )
    response = client.post(
        f"/api/v1/chapters/{chapter_id}/manual-review",
        headers=headers,
        json={"decision": "reject", "reason": "冲突不足，请重写"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["task_id"] == "task-real-1"
    db = connect()
    row = db.execute("SELECT status,meta FROM contents WHERE id=%s", (chapter_id,)).fetchone()
    db.close()
    assert row["status"] == "needs_rewrite"
    assert row["meta"]["manual_review"]["status"] == "regenerating"
    assert row["meta"]["manual_review"]["task_id"] == "task-real-1"


def test_failed_task_is_explicit_and_does_not_overwrite_original(regeneration_case, monkeypatch):
    from app.db import connect, encode
    from app.workers.celery_app import celery_app

    client, headers, chapter_id, original = regeneration_case
    db = connect()
    db.execute(
        "UPDATE contents SET status='needs_rewrite',meta=meta || %s WHERE id=%s",
        (encode({"manual_review": {"status": "regenerating", "task_id": "task-failed-1"}}), chapter_id),
    )
    db.commit()
    db.close()
    monkeypatch.setattr(
        celery_app,
        "AsyncResult",
        lambda _task_id: type("Result", (), {"state": "FAILURE"})(),
    )
    response = client.get(f"/api/v1/chapters/{chapter_id}/regeneration", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "failed"
    db = connect()
    stored = db.execute("SELECT body FROM contents WHERE id=%s", (chapter_id,)).fetchone()["body"]
    db.close()
    assert stored == original


def test_completed_rewrite_returns_same_chapter_for_review(regeneration_case):
    from app.db import connect, encode

    client, headers, chapter_id, _original = regeneration_case
    rewritten = {"type": "doc", "content": [{"type": "paragraph", "text": "重写后的同一章节。"}]}
    db = connect()
    db.execute(
        "UPDATE contents SET body=%s,status='pending_review',meta=meta || %s WHERE id=%s",
        (encode(rewritten), encode({"manual_review": {"status": "regenerated", "task_id": "task-ok-1"}}), chapter_id),
    )
    db.commit()
    db.close()
    response = client.get(f"/api/v1/chapters/{chapter_id}/regeneration", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "pending_review"
    assert data["chapter"]["id"] == chapter_id
    assert data["chapter"]["body"] == rewritten
