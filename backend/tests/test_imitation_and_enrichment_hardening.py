from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


def _auth_project():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"imit-{uuid.uuid4().hex[:8]}@nc.dev"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    return client, headers, project_id


def test_style_similarity_blocks_copylike_output():
    from app.services.style_learn import check_similarity

    source = "风从旧城的钟楼穿过，带着铁锈和潮湿的味道。" * 30
    copied = source[:260] + "尾声稍作变化"
    result = check_similarity(source, copied)
    assert result["verdict"] == "blocked"
    assert result["similarity"] >= 0.75


def test_imitation_endpoint_blocks_high_similarity_before_persist(monkeypatch):
    from app.api.v1 import imitation
    from app.db import connect

    client, headers, project_id = _auth_project()
    source = "风从旧城的钟楼穿过，带着铁锈和潮湿的味道。主角沿着潮湿石阶向下，听见远处机器像心脏一样震动。" * 12

    monkeypatch.setattr(
        imitation,
        "complete",
        lambda **_kwargs: {"title": "高相似样稿", "style_profile": {"tone": "冷峻"}, "text": source[:900]},
    )

    response = client.post(
        "/api/v1/imitation",
        headers=headers,
        json={"project_id": project_id, "source_text": source, "instruction": "仿写"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "IMITATION_SIMILARITY_BLOCKED"

    db = connect()
    count = db.execute(
        "SELECT COUNT(*) AS c FROM contents WHERE project_id=%s AND type='imitation_sample'",
        (project_id,),
    ).fetchone()["c"]
    db.close()
    assert count == 0


def test_narrative_enrichment_provider_errors_are_not_silenced(monkeypatch):
    import app.gateway as gateway
    from app.db import connect, encode, new_id
    from app.services.entity_tracker import extract_and_store
    from app.services.foreshadowing import extract_and_store_foreshadowing
    from app.services.timeline import extract_timeline, update_arcs

    client, headers, project_id = _auth_project()
    del client, headers
    novel_id, chapter_id = new_id(), new_id()
    db = connect()
    db.execute(
        "INSERT INTO contents (id,project_id,type,title,body,meta,status) VALUES (%s,%s,'novel','叙事抽取错误测试',%s,%s,'draft')",
        (novel_id, project_id, encode({"type": "doc", "content": []}), encode({})),
    )
    db.execute(
        "INSERT INTO contents (id,project_id,parent_id,type,title,body,meta,status) VALUES (%s,%s,%s,'chapter','第一章',%s,%s,'draft')",
        (chapter_id, project_id, novel_id, encode({"type": "doc", "content": []}), encode({"seq": 1})),
    )
    db.commit()
    db.close()

    def _down(**_kwargs):
        raise gateway.ProviderError("provider unavailable")

    monkeypatch.setattr(gateway, "complete", _down)

    with pytest.raises(gateway.ProviderError):
        extract_and_store(chapter_id, novel_id, "正文")
    with pytest.raises(gateway.ProviderError):
        extract_and_store_foreshadowing(chapter_id, 1, "正文")
    with pytest.raises(gateway.ProviderError):
        extract_timeline(chapter_id, "正文")
    with pytest.raises(gateway.ProviderError):
        update_arcs(novel_id, "正文")
