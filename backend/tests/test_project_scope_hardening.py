from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


def _auth_project():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"scope-{uuid.uuid4().hex[:8]}@nc.dev"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    return client, headers, project_id


def test_style_check_only_reads_references_from_requested_project():
    from app.db import connect, encode, new_id

    client, headers, project_id = _auth_project()
    other_project = client.post("/api/v1/projects", headers=headers, json={"name": "另一个项目"}).json()["data"]["id"]
    similar = "这是一段用于相似度检测的参考文本，包含独特的旧城钟楼、雨夜、红灯、潮湿石阶。" * 4
    db = connect()
    db.execute(
        "INSERT INTO knowledge_items (id, project_id, kind, title, body, meta) VALUES (%s,%s,'reference','other',%s,%s)",
        (new_id(), other_project, similar, encode({})),
    )
    db.commit()
    db.close()

    response = client.get("/api/v1/knowledge/style-check", headers=headers,
                          params={"project_id": project_id, "text": similar})
    assert response.status_code == 200
    assert response.json()["data"]["similarity"] == 0

    db = connect()
    db.execute(
        "INSERT INTO knowledge_items (id, project_id, kind, title, body, meta) VALUES (%s,%s,'reference','own',%s,%s)",
        (new_id(), project_id, similar, encode({})),
    )
    db.commit()
    db.close()

    response = client.get("/api/v1/knowledge/style-check", headers=headers,
                          params={"project_id": project_id, "text": similar})
    assert response.status_code == 200
    assert response.json()["data"]["similarity"] > 0.6
    assert response.json()["data"]["warning"]


def test_overseas_translate_uses_content_project_and_surfaces_provider_errors(monkeypatch):
    import app.gateway as gateway
    from app.db import connect, encode, new_id

    client, headers, project_id = _auth_project()
    content_id = new_id()
    db = connect()
    db.execute(
        "INSERT INTO contents (id, project_id, type, title, body, meta, status) VALUES (%s,%s,'chapter','出海翻译测试',%s,%s,'draft')",
        (content_id, project_id,
         encode({"type": "doc", "content": [{"type": "paragraph", "text": "这是需要翻译的正文。"}]}),
         encode({"seq": 1})),
    )
    db.commit()
    db.close()

    seen_projects: list[str] = []

    def fake_complete(**kwargs):
        seen_projects.append(kwargs["project_id"])
        if kwargs["task_type"] == "translate_segment":
            return {"translated": "Translated text."}
        return {"localized": "Localized text.", "notes": ["ok"]}

    monkeypatch.setattr(gateway, "complete", fake_complete)
    response = client.post("/api/v1/overseas/translate", headers=headers,
                           params={"content_id": content_id, "target_lang": "en"})
    assert response.status_code == 200
    assert response.json()["data"]["localized"] == "Localized text."
    assert seen_projects == [project_id, project_id]

    def down(**_kwargs):
        raise gateway.ProviderError("provider down")

    monkeypatch.setattr(gateway, "complete", down)
    response = client.post("/api/v1/overseas/translate", headers=headers,
                           params={"content_id": content_id, "target_lang": "en"})
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "AI_PROVIDER_FAILED"

    with pytest.raises(gateway.ProviderError):
        # Service-level contract: provider errors are not converted to fake text.
        from app.services.overseas import translate_chapter
        translate_chapter("正文", "en", project_id)
