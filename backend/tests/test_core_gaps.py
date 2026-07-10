"""Regression tests for auth hardening, text metrics and bounded batches."""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.db import connect, new_id
from app.services.knowledge_hub import (
    EMBEDDING_DIMENSION,
    _chunk_text,
    _local_embedding,
    rebuild_item_embeddings,
    search,
)
from app.services.text_metrics import count_content_chars


def test_content_character_count_ignores_whitespace():
    assert count_content_chars("第一章\n\n 你好 world\t!") == 11


def test_chunk_text_is_stable_and_overlapping():
    text = "x" * 1700
    chunks = _chunk_text(text)
    assert [len(chunk) for chunk in chunks] == [800, 800, 300]
    assert chunks == _chunk_text(text)


def test_local_embedding_is_deterministic_and_normalized():
    vector = _local_embedding("这是需要建立索引的世界观文本")
    assert len(vector) == EMBEDDING_DIMENSION
    assert vector == _local_embedding("这是需要建立索引的世界观文本")
    assert abs(sum(value * value for value in vector) - 1.0) < 1e-6


def test_refresh_cookie_requires_csrf_and_rotates():
    with TestClient(app) as client:
        email = f"refresh-{uuid.uuid4().hex}@nc.dev"
        registered = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"})
        assert registered.status_code == 200
        old_refresh = client.cookies.get("refresh_token")
        csrf = client.cookies.get("csrf_token")
        assert old_refresh and csrf
        assert "HttpOnly" in registered.headers.get("set-cookie", "")
        assert "refresh_token" not in registered.json()["data"]

        rejected = client.post("/api/v1/auth/refresh")
        assert rejected.status_code == 403

        refreshed = client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf})
        assert refreshed.status_code == 200
        assert refreshed.json()["data"]["access_token"]
        assert client.cookies.get("refresh_token") != old_refresh

    with TestClient(app) as replay_client:
        replay = replay_client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        assert replay.status_code == 401


def test_batch_chapter_count_is_bounded():
    with TestClient(app) as client:
        email = f"batch-{uuid.uuid4().hex}@nc.dev"
        registered = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"})
        token = registered.json()["data"]["access_token"]
        csrf = client.cookies.get("csrf_token")
        response = client.post(
            f"/api/v1/novels/{uuid.uuid4()}/chapters/batch",
            json={"chapter_count": 51},
            headers={"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf},
        )
        assert response.status_code == 422


def test_knowledge_reindex_replaces_old_chunks():
    db = connect()
    project = db.execute("SELECT id FROM projects LIMIT 1").fetchone()
    item_id = new_id()
    unique_term = f"量子航道-{uuid.uuid4().hex}"
    db.execute(
        "INSERT INTO knowledge_items (id, project_id, kind, title, body) VALUES (%s, %s, 'worldview', %s, %s)",
        (item_id, project["id"], "星港世界观", f"星港采用{unique_term}。" * 120),
    )
    db.commit()
    db.close()

    first_count = rebuild_item_embeddings(item_id)
    second_count = rebuild_item_embeddings(item_id)
    db = connect()
    stored_count = db.execute("SELECT COUNT(*) AS total FROM knowledge_vectors WHERE item_id = %s", (item_id,)).fetchone()["total"]
    db.close()
    assert first_count == second_count == stored_count
    assert str(search(unique_term, project_id=str(project["id"]))[0]["id"]) == item_id


def test_batch_can_be_created_and_cancelled(monkeypatch):
    class FakeTask:
        id = "fake-celery-task"

    from app.workers.tasks import batch_generate_chapters_task
    monkeypatch.setattr(batch_generate_chapters_task, "delay", lambda *args, **kwargs: FakeTask())

    with TestClient(app) as client:
        email = f"batch-flow-{uuid.uuid4().hex}@nc.dev"
        registered = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"})
        token = registered.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
        novel = client.post(
            f"/api/v1/projects/{project_id}/novels",
            headers=headers,
            json={"idea": "一座城市每天遗忘一个人", "target_words": 100000},
        ).json()["data"]
        created = client.post(
            f"/api/v1/novels/{novel['id']}/chapters/batch",
            headers=headers,
            json={"chapter_count": 3},
        )
        assert created.status_code == 200
        batch_id = created.json()["data"]["batch_id"]
        cancelled = client.post(f"/api/v1/generation-batches/{batch_id}/cancel", headers=headers)
        assert cancelled.status_code == 200
        state = client.get(f"/api/v1/generation-batches/{batch_id}", headers=headers).json()["data"]
        assert state["status"] == "cancelled"
        assert state["cancel_requested"] is True


def test_chapter_generation_releases_lock_on_failure(monkeypatch):
    from app.workers import lock
    from app.workers import tasks

    released: list[str] = []
    monkeypatch.setattr(lock, "acquire_lock", lambda key: True)
    monkeypatch.setattr(lock, "release_lock", lambda key: released.append(key))
    monkeypatch.setattr(tasks, "_generate_next_chapter_unlocked", lambda *_args: (_ for _ in ()).throw(RuntimeError("boom")))

    try:
        tasks.gen_next_chapter_task.run("novel-id", "project-id")
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("generation failure was not propagated")
    assert released == ["lock:novel:novel-id:gen_chapter"]
