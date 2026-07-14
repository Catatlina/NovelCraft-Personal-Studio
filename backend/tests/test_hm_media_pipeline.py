"""NC-HM-001/002/003: hotspot dedup/trend/freshness scoring, platform matching,
real-AI content toolbox endpoints, and recoverable generation retry."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


def _auth_project():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"hm-{uuid.uuid4().hex[:8]}@nc.dev"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    return client, headers, project_id


# ===== NC-HM-001: dedup / trend / freshness =====

def test_store_hotspots_dedups_within_window_and_scores_freshness():
    from datetime import datetime, timedelta

    from app.db import connect
    from app.services.hotspot_collector import (
        _dedup_key, compute_freshness_score, store_hotspots)

    title = f"去重验证热点-{uuid.uuid4().hex[:6]}"
    item = {"title": title, "source": "zhihu", "category": "tech", "raw_score": "1181 万热度",
            "url": "https://example.com/t", "fetched_at": datetime.utcnow().isoformat(),
            "dedup_key": _dedup_key(title, "zhihu")}
    assert store_hotspots([item]) == 1
    # Second store of the same dedup_key inside 24h must not create a new row
    assert store_hotspots([dict(item)]) == 0

    db = connect()
    rows = db.execute(
        "SELECT meta FROM knowledge_items WHERE kind='hotspot' AND meta->>'dedup_key'=%s",
        (item["dedup_key"],),
    ).fetchall()
    db.close()
    assert len(rows) == 1
    meta = rows[0]["meta"]
    assert meta["trend"] in {"new", "rising", "stable", "cooling"}
    assert 0.1 <= float(meta["freshness"]) <= 1.0

    # Freshness decays with age: now ≈ 1.0, 12h ≈ 0.75, 48h hits the 0.1 floor
    now = datetime.utcnow()
    assert compute_freshness_score(now.isoformat()) > 0.99
    assert abs(compute_freshness_score((now - timedelta(hours=12)).isoformat()) - 0.75) < 0.01
    assert compute_freshness_score((now - timedelta(hours=48)).isoformat()) == pytest.approx(0.1)


def test_trend_report_endpoint_aggregates_real_rows():
    from datetime import datetime

    from app.services.hotspot_collector import _dedup_key, store_hotspots

    client, headers, _ = _auth_project()
    title = f"趋势报告热点-{uuid.uuid4().hex[:6]}"
    store_hotspots([{"title": title, "source": "weibo", "category": "general", "raw_score": 99,
                     "url": "", "fetched_at": datetime.utcnow().isoformat(),
                     "dedup_key": _dedup_key(title, "weibo")}])
    report = client.get("/api/v1/hotspots/trend-report", headers=headers)
    assert report.status_code == 200
    data = report.json()["data"]
    assert data["total_hotspots_24h"] >= 1
    assert 0 < data["avg_freshness"] <= 1
    assert sum(data["trends"].values()) == data["total_hotspots_24h"]


# ===== NC-HM-002: platform matching + compliance =====

def test_platform_match_endpoint_scores_and_flags_risks():
    client, headers, _ = _auth_project()
    result = client.get("/api/v1/hotspots/platform-match", headers=headers,
                        params={"topic": "AI 编程工具实测分享", "category": "tech"})
    assert result.status_code == 200
    matches = result.json()["data"]["matches"]
    assert len(matches) >= 5
    # Sorted by suitability desc; tech topic boosts zhihu/medium/baijia
    scores = [m["suitability"] for m in matches]
    assert scores == sorted(scores, reverse=True)
    top_platforms = {m["platform"] for m in matches[:3]}
    assert top_platforms & {"zhihu", "medium", "baijia"}
    for m in matches:
        assert set(m) >= {"platform", "suitability", "audience", "risks"}

    # 诱导分享 risk flagged for wechat
    risky = client.get("/api/v1/hotspots/platform-match", headers=headers,
                       params={"topic": "转发分享抽大奖"}).json()["data"]["matches"]
    wechat = next(m for m in risky if m["platform"] == "wechat")
    assert any("分享" in r for r in wechat["risks"])

    empty = client.get("/api/v1/hotspots/platform-match", headers=headers, params={"topic": "  "})
    assert empty.status_code == 422


# ===== NC-HM-003: real-AI toolbox endpoints =====

def test_title_variants_uses_gateway_and_fails_explicitly(monkeypatch):
    import app.gateway as gateway

    client, headers, project_id = _auth_project()
    calls = []

    def fake_complete(**kwargs):
        calls.append(kwargs)
        assert kwargs["prompt_name"] == "social.hm_title_variants"
        assert kwargs["task_type"] == "hm_title_variants"
        return {"titles": [f"标题{i}" for i in range(1, 9)]}

    monkeypatch.setattr(gateway, "complete", fake_complete)
    result = client.post("/api/v1/hotspots/title-variants", headers=headers,
                         json={"project_id": project_id, "topic": "夏日露营装备清单", "count": 5})
    assert result.status_code == 200
    titles = result.json()["data"]["titles"]
    assert titles == ["标题1", "标题2", "标题3", "标题4", "标题5"]
    assert calls and calls[0]["variables"]["count"] == 5

    def failing_complete(**kwargs):
        raise gateway.ProviderError("upstream 500")

    monkeypatch.setattr(gateway, "complete", failing_complete)
    failed = client.post("/api/v1/hotspots/title-variants", headers=headers,
                         json={"project_id": project_id, "topic": "夏日露营装备清单"})
    assert failed.status_code == 502
    assert "AI_PROVIDER_FAILED" in str(failed.json())


def test_video_script_and_material_endpoints_route_real_prompts(monkeypatch):
    import app.gateway as gateway

    client, headers, project_id = _auth_project()
    seen = []

    def fake_complete(**kwargs):
        seen.append(kwargs["prompt_name"])
        if kwargs["prompt_name"] == "social.gen_video_script":
            return {"title": "60秒看懂", "scenes": [{"time": "0-3s", "action": "开场", "text": "钩子"}],
                    "narration_style": "快节奏", "cover_text": "封面"}
        return {"cover_image_prompt": "深色科技感封面", "suggested_charts": ["折线图"],
                "data_sources": ["国家统计局"], "recommended_tags": ["科技"]}

    monkeypatch.setattr(gateway, "complete", fake_complete)
    video = client.post("/api/v1/hotspots/video-script", headers=headers,
                        json={"project_id": project_id, "topic": "AI 手机评测", "platform": "douyin"})
    assert video.status_code == 200
    assert video.json()["data"]["scenes"][0]["time"] == "0-3s"

    bad_platform = client.post("/api/v1/hotspots/video-script", headers=headers,
                               json={"project_id": project_id, "topic": "AI 手机评测", "platform": "nosuch"})
    assert bad_platform.status_code == 422

    materials = client.post("/api/v1/hotspots/material-suggestions", headers=headers,
                            json={"project_id": project_id, "topic": "AI 手机评测", "content": "正文草稿"})
    assert materials.status_code == 200
    assert materials.json()["data"]["data_sources"] == ["国家统计局"]
    assert seen == ["social.gen_video_script", "social.hm_material_suggestions"]


def test_hm_endpoints_require_project_membership(monkeypatch):
    import app.gateway as gateway

    client, headers, _ = _auth_project()
    monkeypatch.setattr(gateway, "complete", lambda **kwargs: {"titles": ["t"]})
    foreign = client.post("/api/v1/hotspots/title-variants", headers=headers,
                          json={"project_id": str(uuid.uuid4()), "topic": "越权话题"})
    assert foreign.status_code == 403


# ===== 可恢复工作流: failed batch rolls back, retry completes =====

def test_hotspot_generate_recovers_after_provider_failure(monkeypatch):
    import app.api.v1.hotspots as hotspots_api
    from app.db import connect
    from app.gateway import ProviderError

    client, headers, project_id = _auth_project()
    topic = f"可恢复热点-{uuid.uuid4().hex[:6]}"
    attempts = {"n": 0}
    mutation_ids: list[str] = []

    def flaky_complete(**kwargs):
        attempts["n"] += 1
        mutation_ids.append(kwargs.get("client_mutation_id") or "")
        if attempts["n"] == 2:
            raise ProviderError("provider down mid-batch")
        return {"title": f"{kwargs['variables']['platform']}稿", "body": ["真实生成正文"], "meta": {}}

    monkeypatch.setattr(hotspots_api, "complete", flaky_complete)
    payload = {"project_id": project_id, "title": topic, "source": "zhihu", "url": "",
               "platforms": ["wechat", "toutiao", "baijia"]}
    first = client.post("/api/v1/hotspots/generate", headers=headers, json=payload)
    assert first.status_code == 502

    db = connect()
    leftover = db.execute(
        "SELECT COUNT(*) AS c FROM contents WHERE project_id=%s AND meta->>'hotspot_title'=%s",
        (project_id, topic),
    ).fetchone()["c"]
    db.close()
    assert leftover == 0  # failed batch leaves no partial rows

    retry = client.post("/api/v1/hotspots/generate", headers=headers, json=payload)
    assert retry.status_code == 200
    items = retry.json()["data"]["items"]
    assert [i["platform"] for i in items] == ["wechat", "toutiao", "baijia"]
    assert all(i["status"] == "succeeded" for i in items)

    db = connect()
    persisted = db.execute(
        "SELECT COUNT(*) AS c FROM contents WHERE project_id=%s AND meta->>'hotspot_title'=%s",
        (project_id, topic),
    ).fetchone()["c"]
    db.close()
    assert persisted == 3

    # First attempt made 2 calls (wechat ok, toutiao failed); retry replays the same
    # per-platform idempotency keys so cached ai_calls can be reused.
    assert attempts["n"] == 5
    assert mutation_ids[0] == mutation_ids[2] and mutation_ids[1] == mutation_ids[3]
