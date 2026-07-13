"""Regressions for the 2026-07-13 production QA report (QA-002/003/004/008 + healthz)."""
import json
import os
import urllib.request

import pytest
from fastapi.testclient import TestClient

from app.db import connect, encode, init_db, new_id
from app.main import app


@pytest.fixture()
def client():
    from app.core.rate_limit import limiter

    limiter.reset()
    init_db()
    return TestClient(app)


def _register(client, email):
    r = client.post("/api/v1/auth/register", json={
        "email": email, "password": "Str0ngPass!x", "display_name": "QA"})
    assert r.status_code == 200, r.text
    return r.json()["data"]


# ── QA-002: weibo nested payload must parse, not crash ──────────────────────

def test_weibo_nested_dict_payload_parses(monkeypatch):
    from app.services import hotspot_collector as hc

    payloads = {
        "zhihu": {"data": [{"target": {"title": "知乎话题", "url": "u"}, "detail_text": "100 万热度"}]},
        # weibo returns {"data": {"realtime": [...]}} — slicing the dict raised
        # TypeError: unhashable slice in production.
        "weibo": {"data": {"realtime": [{"word": "微博热搜词", "raw_hot": 12345}]}},
    }

    class _Resp:
        def __init__(self, body): self.body = body
        def read(self): return json.dumps(self.body).encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    class _Opener:
        def open(self, req, timeout=0):
            for key in payloads:
                if key in req.full_url:
                    return _Resp(payloads[key])
            raise AssertionError(req.full_url)

    monkeypatch.setattr(hc, "_hotspot_opener", lambda: _Opener())
    items, status = hc.fetch_hotspots()
    assert status["weibo"] == "ok", status
    assert any(i["title"] == "微博热搜词" for i in items)
    assert status["zhihu"] == "ok", status


# ── QA-003: admin reads honor NOVELCRAFT_ADMIN_EMAILS when configured ───────

def test_admin_reads_restricted_when_admin_emails_configured(client, monkeypatch):
    user = _register(client, f"qa3-{new_id()[:8]}@test.local")
    headers = {"Authorization": f"Bearer {user['access_token']}"}

    # Personal mode (no admin list): authenticated reads allowed
    monkeypatch.delenv("NOVELCRAFT_ADMIN_EMAILS", raising=False)
    assert client.get("/api/v1/admin/prompts", headers=headers).status_code == 200
    assert client.get("/api/v1/admin/model-routes", headers=headers).status_code == 200

    # Admin list configured and user not on it: reads are denied like writes
    monkeypatch.setenv("NOVELCRAFT_ADMIN_EMAILS", "owner@novelcraft.local")
    assert client.get("/api/v1/admin/prompts", headers=headers).status_code == 403
    assert client.get("/api/v1/admin/model-routes", headers=headers).status_code == 403
    assert client.get("/api/v1/admin/providers", headers=headers).status_code == 403

    # Admin on the list keeps access
    monkeypatch.setenv("NOVELCRAFT_ADMIN_EMAILS", user["user"]["email"])
    assert client.get("/api/v1/admin/prompts", headers=headers).status_code == 200


# ── QA-004: novels/contents are deletable (soft delete + cascade) ───────────

def test_delete_novel_soft_deletes_chapters_and_knowledge(client):
    user = _register(client, f"qa4-{new_id()[:8]}@test.local")
    headers = {"Authorization": f"Bearer {user['access_token']}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]

    db = connect()
    novel_id = new_id()
    db.execute(
        "INSERT INTO contents (id, project_id, type, title, body, meta, status) "
        "VALUES (%s,%s,'novel','待删除',%s,%s,'draft')",
        (novel_id, project_id, encode({}), encode({})),
    )
    chapter_id = new_id()
    db.execute(
        "INSERT INTO contents (id, project_id, parent_id, type, title, body, meta, status) "
        "VALUES (%s,%s,%s,'chapter','第一章',%s,%s,'draft')",
        (chapter_id, project_id, novel_id, encode({}), encode({})),
    )
    db.execute(
        "INSERT INTO knowledge_items (id, project_id, content_id, kind, title, body) "
        "VALUES (%s,%s,%s,'worldview','世界观','规则')",
        (new_id(), project_id, novel_id),
    )
    db.commit(); db.close()

    r = client.delete(f"/api/v1/novels/{novel_id}", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["children_deleted"] == 1

    db = connect()
    novel = db.execute("SELECT is_deleted FROM contents WHERE id=%s", (novel_id,)).fetchone()
    chapter = db.execute("SELECT is_deleted FROM contents WHERE id=%s", (chapter_id,)).fetchone()
    ki = db.execute("SELECT is_deleted FROM knowledge_items WHERE content_id=%s", (novel_id,)).fetchone()
    db.close()
    assert novel["is_deleted"] and chapter["is_deleted"] and ki["is_deleted"]


def test_delete_requires_membership(client):
    owner = _register(client, f"qa4o-{new_id()[:8]}@test.local")
    stranger = _register(client, f"qa4s-{new_id()[:8]}@test.local")
    project_id = client.get(
        "/api/v1/projects", headers={"Authorization": f"Bearer {owner['access_token']}"}
    ).json()["data"][0]["id"]

    db = connect()
    novel_id = new_id()
    db.execute(
        "INSERT INTO contents (id, project_id, type, title, body, meta, status) "
        "VALUES (%s,%s,'novel','别人的书',%s,%s,'draft')",
        (novel_id, project_id, encode({}), encode({})),
    )
    db.commit(); db.close()

    r = client.delete(f"/api/v1/contents/{novel_id}",
                      headers={"Authorization": f"Bearer {stranger['access_token']}"})
    assert r.status_code == 403


# ── QA-008: registration does not confirm existing emails ───────────────────

def test_register_duplicate_email_is_not_enumerable(client):
    email = f"qa8-{new_id()[:8]}@test.local"
    _register(client, email)
    r = client.post("/api/v1/auth/register", json={
        "email": email, "password": "Str0ngPass!x", "display_name": "QA"})
    assert r.status_code == 400
    assert "already" not in r.text.lower()
    assert "registered" not in r.text.lower()


# ── QA-001 follow-up: healthz surfaces worker liveness ───────────────────────

def test_healthz_reports_worker_and_queue(client):
    data = client.get("/api/v1/healthz").json()["data"]
    assert "worker" in data, data
    # No worker runs during tests: the check must say so instead of staying silent.
    assert data["worker"].startswith("ok") or data["worker"].startswith("error"), data
    assert "queue_depth" in data
