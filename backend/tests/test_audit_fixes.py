"""Audit remediation contracts: B5 encrypted publish credentials, P1-1 index
repair, P0-3 compose migrate dependency, and de-faked narrative/stats/sensitive
surfaces (audit report 2026-07-11)."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def authed():
    from app.main import app

    client = TestClient(app)
    email = f"audit-{uuid.uuid4().hex[:6]}@nc.dev"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["data"]["id"]
    return {"client": client, "headers": headers, "project_id": project_id, "user_id": user_id}


# --- B5: publish credentials must persist encrypted, never in memory/plaintext ---

def test_platform_account_persists_encrypted_credentials(authed):
    from app.db import connect
    from app.services.publish_hub import get_platform_credentials, list_platform_accounts, register_platform_account

    secret = {"token": "tok-secret-123", "cookie": "abc"}
    result = register_platform_account("zhihu", "主账号", secret, user_id=authed["user_id"])
    assert result["status"] == "ok"
    assert "tok-secret-123" not in str(result)

    db = connect()
    row = db.execute("SELECT credentials_encrypted FROM platform_accounts WHERE id=%s", (result["account_id"],)).fetchone()
    db.close()
    assert row["credentials_encrypted"]
    assert "tok-secret-123" not in row["credentials_encrypted"]

    assert get_platform_credentials(authed["user_id"], "zhihu") == secret
    listed = list_platform_accounts(authed["user_id"])
    assert listed and listed[0]["platform"] == "zhihu"
    assert "tok-secret-123" not in str(listed)


def test_platform_account_reregistration_updates_in_place(authed):
    from app.services.publish_hub import get_platform_credentials, register_platform_account

    first = register_platform_account("wechat", "订阅号", {"token": "v1"}, user_id=authed["user_id"])
    second = register_platform_account("wechat", "订阅号", {"token": "v2"}, user_id=authed["user_id"])
    assert first["account_id"] == second["account_id"]
    assert get_platform_credentials(authed["user_id"], "wechat") == {"token": "v2"}


def test_platform_account_requires_user():
    from app.services.publish_hub import register_platform_account

    assert register_platform_account("zhihu", "x", {})["status"] == "error"


def test_publish_hub_no_longer_uses_memory_dict():
    source = (ROOT / "backend/app/services/publish_hub.py").read_text(encoding="utf-8")
    assert "AUTHORIZED_ACCOUNTS" not in source


def test_publish_history_with_empty_filters_does_not_crash():
    from app.services.publish_hub import get_publishing_history

    assert isinstance(get_publishing_history(), list)


# --- P1-1: repaired indexes exist on the real columns ---

def test_repaired_indexes_exist():
    from app.db import connect

    db = connect()
    for name in ("idx_entity_states_chapter", "idx_versions_entity", "idx_versions_author", "idx_operation_logs_project"):
        assert db.execute("SELECT to_regclass(%s) AS t", (name,)).fetchone()["t"], f"{name} missing"
    db.close()


def test_index_repair_migration_fails_loudly():
    source = (ROOT / "backend/alembic/versions/nc_ops_index_repair.py").read_text(encoding="utf-8")
    assert 'down_revision = "nc_ops_performance_indexes"' in source
    assert "try:" not in source  # no silent swallowing


# --- P0-3: compose must not start api/worker before migrations complete ---

def test_compose_orders_migrations_before_app():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert compose.count("service_completed_successfully") >= 2  # api + worker
    assert "appendonly yes" in compose
    assert "redis_data:/data" in compose


# --- de-faked surfaces: narrative + stats + sensitive check -------------------

def test_narrative_endpoint_returns_real_timeline_and_arcs(authed):
    from app.db import connect, encode, new_id

    client, headers, project_id = authed["client"], authed["headers"], authed["project_id"]
    novel_id = client.post(f"/api/v1/projects/{project_id}/novels", headers=headers,
                           json={"idea": "审计验收小说", "genre": "科幻", "style": "紧凑", "target_words": 10000}).json()["data"]["id"]
    db = connect()
    chapter_id = new_id()
    db.execute(
        "INSERT INTO contents (id, project_id, parent_id, type, title, body, meta, status) VALUES (%s,%s,%s,'chapter','第一章',%s,%s,'draft')",
        (chapter_id, project_id, novel_id, encode({"type": "doc", "content": []}), encode({"seq": 1})),
    )
    db.execute("INSERT INTO timeline_events (id, chapter_id, event_text, event_order) VALUES (%s,%s,'主角抵达修档馆',1)",
               (new_id(), chapter_id))
    db.execute("INSERT INTO arcs (id, novel_id, character_name, stage, goal, status) VALUES (%s,%s,'林序','觉醒','找到墨晶来源','active')",
               (new_id(), novel_id))
    db.commit()
    db.close()

    data = client.get(f"/api/v1/novels/{novel_id}/narrative", headers=headers).json()["data"]
    assert data["timeline"] == [{"event": "主角抵达修档馆", "chapter_seq": 1}]
    assert data["arcs"][0]["character"] == "林序"
    assert data["arcs"][0]["goal"] == "找到墨晶来源"


def test_stats_overview_returns_real_counts(authed):
    data = authed["client"].get("/api/v1/stats/overview", headers=authed["headers"]).json()["data"]
    assert isinstance(data["ai_calls"], int)
    assert isinstance(data["contents"], int)
    assert data["db_size"]


def test_check_sensitive_endpoint_flags_blocked_words(authed):
    from app.db import connect, encode, new_id

    client, headers, project_id = authed["client"], authed["headers"], authed["project_id"]
    db = connect()
    word = db.execute("SELECT word FROM sensitive_words LIMIT 1").fetchone()
    content_id = new_id()
    body = {"type": "doc", "content": [{"type": "paragraph", "text": f"平静的正文 {word['word'] if word else ''}"}]}
    db.execute(
        "INSERT INTO contents (id, project_id, type, title, body, meta, status) VALUES (%s,%s,'chapter','测试',%s,%s,'draft')",
        (content_id, project_id, encode(body), encode({"seq": 1})),
    )
    db.commit()
    db.close()

    data = client.post(f"/api/v1/contents/{content_id}/check-sensitive", headers=headers).json()["data"]
    assert "passed" in data and "blocked_words" in data
    if word:
        assert data["passed"] is False
        assert word["word"] in data["blocked_words"]
