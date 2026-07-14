"""Protected real-provider smoke for the 2026-07-14 feature batch.

These tests call the real configured AI provider. They are skipped when
DEEPSEEK_API_KEY is absent and must never be replaced by product mock output.
"""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.skipif(
    not os.getenv("DEEPSEEK_API_KEY"),
    reason="real-provider feature smoke needs DEEPSEEK_API_KEY",
)


@pytest.fixture
def authed():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"feature-real-{uuid.uuid4().hex[:6]}@nc.dev"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    return client, headers, project_id


def test_real_editor_rewrite_chapter_returns_review_and_next_plan(authed):
    from app.db import connect, encode, new_id

    client, headers, project_id = authed
    content_id = new_id()
    text = "他在凌晨三点听见地底嗡鸣。旧楼像一只醒来的兽，墙皮簌簌落下。"
    db = connect()
    db.execute(
        "INSERT INTO contents (id, project_id, type, title, body, meta, status) VALUES (%s,%s,'chapter','真实编辑器冒烟',%s,%s,'draft')",
        (content_id, project_id, encode({"type": "doc", "content": [{"type": "paragraph", "text": text}]}), encode({"seq": 1})),
    )
    db.commit()
    db.close()

    response = client.post(
        f"/api/v1/contents/{content_id}/ai/rewrite_chapter",
        headers=headers,
        json={"selection": text, "instruction": "整章重写，增强悬疑感，保留核心事件", "client_mutation_id": f"real-edit-{uuid.uuid4().hex[:8]}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data.get("text") and data["text"] != text
    assert 0 <= float(data["review_7dim"].get("score", 0)) <= 100
    assert data["next_chapter_plan"].get("next_title") or data["next_chapter_plan"].get("goals")


def test_real_hotspot_generate_one_platform_persists_draft(authed):
    from app.db import connect

    client, headers, project_id = authed
    response = client.post(
        "/api/v1/hotspots/generate",
        headers=headers,
        json={"project_id": project_id, "title": "AI 写作工具真实验收", "source": "manual_smoke", "platforms": ["wechat"]},
    )
    assert response.status_code == 200, response.text
    item = response.json()["data"]["items"][0]
    assert item["platform"] == "wechat"

    db = connect()
    row = db.execute("SELECT type, title, meta FROM contents WHERE id=%s", (item["content_id"],)).fetchone()
    db.close()
    assert row is not None
    assert row["type"] == "wechat_article"
    assert row["meta"]["hotspot_title"] == "AI 写作工具真实验收"


def test_real_imitation_generates_original_sample_with_similarity_report(authed):
    client, headers, project_id = authed
    source = (
        "雨落在旧码头的铁皮棚上，声音像一群细小的虫在啃咬夜色。"
        "林舟把伞收起，鞋底踩过积水，倒影里那盏红灯忽明忽暗。"
        "他并不相信巧合，尤其不相信一封失踪十年的信会在今晚重新寄到自己手里。"
        "信纸上没有署名，只有一句话：别去钟楼，那里的人还在等你。"
    ) * 4
    response = client.post(
        "/api/v1/imitation",
        headers=headers,
        json={"project_id": project_id, "source_text": source, "instruction": "学习节奏和氛围，生成原创都市悬疑开篇，不复用码头、信、钟楼等具体元素。"},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["content_id"]
    assert data.get("text")
    assert data["similarity"]["verdict"] in {"pass", "warning"}
