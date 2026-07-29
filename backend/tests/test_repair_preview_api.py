"""Repair Engine product gate: preview is non-mutating and apply is explicit."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def repair_case():
    from app.core.rate_limit import limiter
    from app.db import connect, encode, new_id
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"repair-{uuid.uuid4().hex[:8]}@nc.dev"
    token = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "test1234"},
    ).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    novel_id = client.post(
        f"/api/v1/projects/{project_id}/novels",
        headers=headers,
        json={"idea": "旧城夜雨里的追凶故事", "genre": "悬疑", "style": "克制", "target_words": 10000},
    ).json()["data"]["id"]
    chapter_id = new_id()
    original = {
        "type": "doc",
        "content": [{"type": "paragraph", "text": "他是一个好人。雨落在旧巷里。"}],
    }
    db = connect()
    db.execute(
        """INSERT INTO contents
           (id, project_id, parent_id, type, title, body, meta, status)
           VALUES (%s,%s,%s,'chapter','第一章 夜雨',%s,%s,'needs_rewrite')""",
        (chapter_id, project_id, novel_id, encode(original), encode({"seq": 1})),
    )
    db.commit()
    db.close()
    return client, headers, chapter_id, original


def test_local_repair_requires_preview_then_apply(repair_case, monkeypatch):
    from app.api.v1 import repairs
    from app.db import connect, decode

    client, headers, chapter_id, original = repair_case

    def preview(*_args):
        proposed, applied, skipped = repairs._apply_replacements(
            original,
            [{"anchor": "一个好人", "replacement": "个愿意帮人的人"}],
        )
        return {
            "action": "repair_local",
            "level": "local",
            "replacements": [{"anchor": "一个好人", "replacement": "个愿意帮人的人"}],
            "proposed_body": proposed,
            "applied": applied,
            "skipped": skipped,
        }

    monkeypatch.setattr(repairs, "_preview_local_repair", preview)
    response = client.post(
        f"/api/v1/chapters/{chapter_id}/repair-preview",
        headers=headers,
        json={"action": "repair_local", "issues": ["人物评价过于空泛"]},
    )
    assert response.status_code == 200
    preview_data = response.json()["data"]

    db = connect()
    before = db.execute("SELECT body FROM contents WHERE id=%s", (chapter_id,)).fetchone()
    db.close()
    assert decode(before["body"], {}) == original

    applied = client.post(
        f"/api/v1/chapters/{chapter_id}/repair-apply",
        headers=headers,
        json={
            "action": preview_data["action"],
            "base_updated_at": preview_data["base_updated_at"],
            "proposal": preview_data["proposal"],
            "signature": preview_data["signature"],
        },
    )
    assert applied.status_code == 200
    result = applied.json()["data"]
    assert result["body"]["content"][0]["text"] == "他是个愿意帮人的人。雨落在旧巷里。"
    assert result["meta"]["repair_log"][-1]["applied"] == ["一个好人"]
    assert result["status"] == "needs_review"


def test_repair_apply_rejects_stale_preview(repair_case, monkeypatch):
    from app.api.v1 import repairs
    from app.db import connect

    client, headers, chapter_id, original = repair_case
    monkeypatch.setattr(
        repairs,
        "_preview_local_repair",
        lambda *_args: {
            "action": "repair_local",
            "level": "local",
            "replacements": [{"anchor": "一个好人", "replacement": "个愿意帮人的人"}],
            "proposed_body": repairs._apply_replacements(
                original, [{"anchor": "一个好人", "replacement": "个愿意帮人的人"}]
            )[0],
            "applied": ["一个好人"],
            "skipped": [],
        },
    )
    preview_data = client.post(
        f"/api/v1/chapters/{chapter_id}/repair-preview",
        headers=headers,
        json={"action": "repair_local", "issues": ["人物评价过于空泛"]},
    ).json()["data"]

    db = connect()
    db.execute("UPDATE contents SET updated_at=now() + interval '1 second' WHERE id=%s", (chapter_id,))
    db.commit()
    db.close()
    response = client.post(
        f"/api/v1/chapters/{chapter_id}/repair-apply",
        headers=headers,
        json={
            "action": preview_data["action"],
            "base_updated_at": preview_data["base_updated_at"],
            "proposal": preview_data["proposal"],
            "signature": preview_data["signature"],
        },
    )
    assert response.status_code == 409


def test_replan_preview_applies_outline_only(repair_case, monkeypatch):
    from app.api.v1 import repairs

    client, headers, chapter_id, original = repair_case
    revised = {
        "seq": 1,
        "title": "第一章 夜雨",
        "outline": "主角沿旧巷追查失踪者，不提前揭晓凶手。",
        "function_type": "悬念",
        "chapter_goal": "建立案件与主角动机",
        "reader_expectation": "凶手留下了什么线索",
        "beats": ["发现遗留物", "遭遇误导", "锁定下一处地点"],
    }
    monkeypatch.setattr(
        repairs,
        "_preview_chapter_replan",
        lambda *_args: {
            "action": "replan_chapter",
            "level": "plot",
            "revised_outline": revised,
            "rationale": "原结构提前泄底，调整信息释放顺序并保留既有案件事实。",
        },
    )
    preview = client.post(
        f"/api/v1/chapters/{chapter_id}/repair-preview",
        headers=headers,
        json={"action": "replan_chapter", "issues": ["结构提前泄底"]},
    ).json()["data"]
    applied = client.post(
        f"/api/v1/chapters/{chapter_id}/repair-apply",
        headers=headers,
        json={
            "action": preview["action"],
            "base_updated_at": preview["base_updated_at"],
            "proposal": preview["proposal"],
            "signature": preview["signature"],
        },
    )
    assert applied.status_code == 200
    result = applied.json()["data"]
    assert result["body"] == original
    assert result["meta"]["outline"] == revised
    assert result["status"] == "needs_rewrite"


def test_tampered_repair_proposal_is_rejected(repair_case, monkeypatch):
    from app.api.v1 import repairs

    client, headers, chapter_id, original = repair_case
    monkeypatch.setattr(
        repairs,
        "_preview_local_repair",
        lambda *_args: {
            "action": "repair_local",
            "level": "local",
            "replacements": [{"anchor": "一个好人", "replacement": "个愿意帮人的人"}],
            "proposed_body": repairs._apply_replacements(
                original, [{"anchor": "一个好人", "replacement": "个愿意帮人的人"}]
            )[0],
            "applied": ["一个好人"],
            "skipped": [],
        },
    )
    preview = client.post(
        f"/api/v1/chapters/{chapter_id}/repair-preview",
        headers=headers,
        json={"action": "repair_local", "issues": ["人物评价过于空泛"]},
    ).json()["data"]
    preview["proposal"]["replacements"][0]["replacement"] = "被篡改的内容"
    response = client.post(
        f"/api/v1/chapters/{chapter_id}/repair-apply",
        headers=headers,
        json={
            "action": preview["action"],
            "base_updated_at": preview["base_updated_at"],
            "proposal": preview["proposal"],
            "signature": preview["signature"],
        },
    )
    assert response.status_code == 422
