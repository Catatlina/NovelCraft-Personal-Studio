from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _auth_project():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"hot-{uuid.uuid4().hex[:8]}@nc.dev"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    return client, headers, project_id


def test_hotspot_generate_persists_platform_drafts(monkeypatch):
    from app.api.v1 import hotspots
    from app.db import connect

    client, headers, project_id = _auth_project()
    calls: list[str] = []

    def fake_complete(**kwargs):
        calls.append(kwargs["variables"]["platform"])
        return {
            "title": f"{kwargs['variables']['platform']}标题",
            "body": ["导语", "正文", "互动引导"],
            "meta": {"tags": ["热点"], "summary": "摘要"},
        }

    monkeypatch.setattr(hotspots, "complete", fake_complete)
    response = client.post(
        "/api/v1/hotspots/generate",
        headers=headers,
        json={"project_id": project_id, "title": "AI 新热点", "source": "baidu", "platforms": ["wechat", "douyin"]},
    )
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert [item["platform"] for item in items] == ["wechat", "douyin"]
    assert calls == ["微信公众号", "抖音"]

    db = connect()
    rows = [
        db.execute("SELECT type, meta FROM contents WHERE project_id=%s AND id=%s",
                   (project_id, item["content_id"])).fetchone()
        for item in items
    ]
    db.close()
    assert {row["type"] for row in rows} == {"wechat_article", "douyin_video"}
    assert all(row["meta"]["hotspot_title"] == "AI 新热点" for row in rows)


def test_hotspot_generate_rolls_back_on_provider_failure(monkeypatch):
    import app.gateway as gateway
    from app.api.v1 import hotspots
    from app.db import connect

    client, headers, project_id = _auth_project()
    calls = 0

    def flaky_complete(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise gateway.ProviderError("provider down")
        return {"title": "第一篇", "body": ["正文"]}

    monkeypatch.setattr(hotspots, "complete", flaky_complete)
    response = client.post(
        "/api/v1/hotspots/generate",
        headers=headers,
        json={"project_id": project_id, "title": "回滚热点", "source": "baidu", "platforms": ["wechat", "toutiao"]},
    )
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "AI_PROVIDER_FAILED"

    db = connect()
    count = db.execute(
        "SELECT COUNT(*) AS c FROM contents WHERE project_id=%s AND meta->>'hotspot_title'='回滚热点'",
        (project_id,),
    ).fetchone()["c"]
    db.close()
    assert count == 0
