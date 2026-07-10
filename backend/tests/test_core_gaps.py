"""Regression tests for auth hardening, text metrics and bounded batches."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import limiter
from app.main import app
from app.db import connect, encode, new_id
from app.services.knowledge_hub import (
    EMBEDDING_DIMENSION,
    _chunk_text,
    _local_embedding,
    rebuild_item_embeddings,
    search,
)
from app.services.text_metrics import count_content_chars


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    limiter.reset()


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


def test_offline_content_sync_is_idempotent_and_preserves_conflicts():
    with TestClient(app) as client:
        email = f"offline-sync-{uuid.uuid4().hex}@nc.dev"
        registered = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"})
        headers = {"Authorization": f"Bearer {registered.json()['data']['access_token']}"}
        project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
        novel = client.post(
            f"/api/v1/projects/{project_id}/novels",
            headers=headers,
            json={"idea": "离线冲突测试小说", "target_words": 100000},
        ).json()["data"]
        original_updated_at = novel["updated_at"]
        first_mutation = f"mutation-{uuid.uuid4()}"
        first_body = {"type": "doc", "content": [{"type": "paragraph", "text": "联网版本"}]}
        applied = client.put(
            f"/api/v1/contents/{novel['id']}",
            headers=headers,
            json={
                "body": first_body,
                "base_updated_at": original_updated_at,
                "client_mutation_id": first_mutation,
            },
        ).json()["data"]
        assert applied["sync_status"] == "applied"

        replayed = client.put(
            f"/api/v1/contents/{novel['id']}",
            headers=headers,
            json={
                "body": first_body,
                "base_updated_at": original_updated_at,
                "client_mutation_id": first_mutation,
            },
        ).json()["data"]
        assert replayed["mutation_replayed"] is True

        conflict = client.put(
            f"/api/v1/contents/{novel['id']}",
            headers=headers,
            json={
                "body": {"type": "doc", "content": [{"type": "paragraph", "text": "离线版本"}]},
                "base_updated_at": original_updated_at,
                "client_mutation_id": f"mutation-{uuid.uuid4()}",
            },
        ).json()["data"]
        assert conflict["sync_status"] == "conflict"
        assert conflict["conflict_version_id"]
        assert conflict["body"] == first_body
        resolved = client.put(
            f"/api/v1/contents/{novel['id']}",
            headers=headers,
            json={
                "body": {"type": "doc", "content": [{"type": "paragraph", "text": "合并版本"}]},
                "base_updated_at": conflict["updated_at"],
                "client_mutation_id": f"mutation-{uuid.uuid4()}",
            },
        ).json()["data"]
        assert resolved["sync_status"] == "applied"
        db = connect()
        conflict_version = db.execute(
            "SELECT reason FROM versions WHERE id = %s",
            (conflict["conflict_version_id"],),
        ).fetchone()
        db.close()
        assert conflict_version["reason"] == "offline_conflict_resolved"


def test_offline_ai_mutation_replay_returns_cached_result():
    from app.gateway import complete

    mutation_id = f"ai-mutation-{uuid.uuid4()}"
    expected = {"text": "已经生成且不会重复计费"}
    db = connect()
    project = db.execute("SELECT id FROM projects LIMIT 1").fetchone()
    db.execute(
        """
        INSERT INTO ai_calls (
            id, provider, model, prompt_name, task_type, input, output,
            status, client_mutation_id, project_id
        ) VALUES (%s, 'test', 'test', 'editor.polish', 'editor_polish', %s, %s, 'succeeded', %s, %s)
        """,
        (new_id(), encode({}), encode(expected), mutation_id, project["id"]),
    )
    db.commit()
    db.close()
    result = complete(
        run_id=None,
        node_key=None,
        project_id=str(project["id"]),
        task_type="editor_polish",
        prompt_name="editor.polish",
        variables={"selection": "原文"},
        client_mutation_id=mutation_id,
    )
    assert result == expected
