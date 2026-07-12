"""Protected real-provider T3 acceptance (P0-1).

These tests call the REAL DeepSeek API and cost a fraction of a cent per run.
They are skipped unless DEEPSEEK_API_KEY is set — locally via env, in CI via
the repository secret of the same name. Mock outputs can never satisfy these
assertions' provenance checks (ai_calls provider/model + strict schemas).

First executed 2026-07-12 against main; that run discovered and fixed:
1. OUTPUT_CONTRACTS chapter examples showed 2 paragraphs while the schema
   requires ≥3 — the real model copied the example and failed validation;
2. the review rework path crashed on an unbound local import (mock reviews
   always scored 84, so the path had never executed).
"""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    not os.getenv("DEEPSEEK_API_KEY"),
    reason="real-provider T3 needs DEEPSEEK_API_KEY (repo secret / local env)",
)


@pytest.fixture
def authed():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"t3-real-{uuid.uuid4().hex[:6]}@nc.dev"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    return {"client": client, "headers": headers, "project_id": project_id}


def _assert_real_call(project_id: str, task_type: str) -> None:
    """The call must be logged with a real provider — mock outputs cannot pass."""
    from app.db import connect

    db = connect()
    row = db.execute(
        "SELECT provider, model FROM ai_calls WHERE project_id=%s AND task_type=%s "
        "AND status='succeeded' ORDER BY created_at DESC LIMIT 1",
        (project_id, task_type),
    ).fetchone()
    db.close()
    assert row is not None, f"no succeeded ai_call for {task_type}"
    assert row["provider"] != "mock" and row["model"] != "mock", row


def test_real_market_analysis_produces_original_candidates(authed):
    client, headers, project_id = authed["client"], authed["headers"], authed["project_id"]
    titles = ["深空葬礼", "长夜灯塔", "雾都拾荒人", "时间当铺", "无声剧场"]
    items = [{"rank": i + 1, "title": t, "author": f"作者{i}", "category": "科幻", "confidence": 0.95,
              "evidence": {"collector": "visible_browser"}} for i, t in enumerate(titles)]
    snapshot_id = client.post(f"/api/v1/ranking/import?project_id={project_id}", headers=headers,
                              json={"source_key": "manual", "source_label": "T3", "items": items}).json()["data"]["snapshot_id"]
    data = client.post(f"/api/v1/ranking/snapshots/{snapshot_id}/analyze", headers=headers).json()["data"]
    assert data["analysis_mode"] == "ai"
    assert len(data["candidates"]) >= 1
    assert all(c["title"] not in titles for c in data["candidates"])  # 原创边界
    _assert_real_call(project_id, "ranking_market_analysis")


def test_real_chapter_generation_meets_schema_contract(authed):
    from app.gateway import complete

    project_id = authed["project_id"]
    output = complete(run_id=None, node_key=None, project_id=project_id,
                      task_type="gen_chapter1", prompt_name="bootstrap.gen_chapter1",
                      variables={"selected_title": "深渊回响", "style": "克制、悬疑"},
                      client_mutation_id=f"t3-ch1-{uuid.uuid4().hex[:8]}")
    chapter = output["chapter"]
    assert len(chapter["body"]) >= 3  # 2026-07-12 修复的契约缺陷防回归
    assert all(isinstance(p, str) and p.strip() for p in chapter["body"])
    _assert_real_call(project_id, "gen_chapter1")


def test_real_review_returns_bounded_score(authed):
    from app.gateway import complete

    project_id = authed["project_id"]
    output = complete(run_id=None, node_key=None, project_id=project_id,
                      task_type="review_7dim", prompt_name="bootstrap.review_7dim",
                      variables={"body": "他在凌晨三点听见了地底的嗡鸣。那声音像一台古老机械的呼吸。他决定明天去查看那口废弃的古井。"},
                      client_mutation_id=f"t3-review-{uuid.uuid4().hex[:8]}")
    assert 0 <= float(output.get("score", -1)) <= 100
    _assert_real_call(project_id, "review_7dim")
