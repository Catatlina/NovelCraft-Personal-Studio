from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient


def _auth_project():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"sea-{uuid.uuid4().hex[:8]}@nc.dev"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["data"]["id"]
    return client, headers, project_id, user_id


def test_market_compliance_rules_catch_aliases_and_rating():
    from app.services.overseas_complete import check_market_compliance, validate_market_release

    result = check_market_compliance("en_UK", "This draft contains racial slur material.")
    assert result["engine"] == "deterministic_rules_v1"
    assert not result["clean"]
    assert "banned_topic: hate_speech" in result["issues"]
    assert result["matched_rules"][0]["patterns"]

    release = validate_market_release("ja_JP", "clean fantasy chapter", "R")
    assert not release["allowed"]
    assert any("rating R not allowed" in blocker for blocker in release["blockers"])


def test_glossary_persistence_overrides_builtin():
    from app.services.overseas_complete import get_glossary, set_glossary_term

    _client, _headers, project_id, _user_id = _auth_project()
    assert get_glossary(project_id, "zh", "en")["金丹"] == "Golden Core"

    result = set_glossary_term(project_id, "zh", "en", "金丹", "Core of Gold")
    assert result["status"] == "ok"
    assert get_glossary(project_id, "zh", "en")["金丹"] == "Core of Gold"


def test_publish_overseas_records_project_provenance():
    from app.db import connect, decode, encode, new_id
    from app.services.overseas_complete import publish_overseas

    _client, _headers, project_id, user_id = _auth_project()
    content_id = new_id()
    db = connect()
    db.execute(
        """INSERT INTO contents (id, project_id, type, title, body, meta, status, owner_id)
           VALUES (%s,%s,'chapter','出海章节',%s,%s,'draft',%s)""",
        (content_id, project_id, encode({"type": "doc", "content": [{"type": "paragraph", "text": "正文"}]}), encode({}), user_id),
    )
    db.commit()
    db.close()

    result = publish_overseas(content_id, "en_US", "royalroad")
    assert result["status"] == "draft"
    assert result["mode"] == "manual_required"

    db = connect()
    row = db.execute("SELECT project_id, meta FROM published_posts WHERE id=%s", (result["post_id"],)).fetchone()
    db.close()
    assert str(row["project_id"]) == project_id
    assert decode(row["meta"], {})["market"] == "en_US"


def test_overseas_publish_endpoint_enforces_content_membership():
    from app.db import connect, encode, new_id

    client, headers, project_id, user_id = _auth_project()
    content_id = new_id()
    db = connect()
    db.execute(
        """INSERT INTO contents (id, project_id, type, title, body, meta, status, owner_id)
           VALUES (%s,%s,'chapter','出海章节',%s,%s,'draft',%s)""",
        (content_id, project_id, encode({"type": "doc", "content": []}), encode({}), user_id),
    )
    db.commit()
    db.close()

    response = client.post(
        "/api/v1/overseas/publish",
        headers=headers,
        params={"content_id": content_id, "market": "en_US", "platform": "royalroad"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["mode"] == "manual_required"


@pytest.mark.skipif(not os.getenv("DEEPSEEK_API_KEY"), reason="requires real DEEPSEEK_API_KEY")
def test_translate_text_real_provider_records_ai_call():
    from app.db import connect
    from app.services.overseas_complete import translate_text

    _client, _headers, project_id, _user_id = _auth_project()
    output = translate_text("主角获得金丹后离开宗门。", "zh", "en", project_id=project_id)
    assert output["method"] == "ai_gateway"
    assert output["text"]

    db = connect()
    row = db.execute(
        """SELECT provider, status FROM ai_calls
           WHERE project_id=%s AND task_type='translate_segment'
           ORDER BY created_at DESC LIMIT 1""",
        (project_id,),
    ).fetchone()
    db.close()
    assert row["status"] == "succeeded"
    assert row["provider"] != "mock"
