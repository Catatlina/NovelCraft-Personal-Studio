"""骨架融合项目推进到待验收：harnessNovel（分层规划/审计/humanize 产品路径）、
insprira（账号追踪/诊断/违禁词真库回归）、BrowserAct（removed 状态诚信）。"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _auth_project():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"skel-{uuid.uuid4().hex[:8]}@nc.dev"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    return client, headers, project_id


# ===== harnessNovel =====

def test_layered_plan_endpoint_uses_real_gateway(monkeypatch):
    """分层规划走真实网关；Provider 失败显式失败，不返回模板规划。"""
    import app.gateway as gateway

    client, headers, _ = _auth_project()

    def fake_complete(**kwargs):
        assert kwargs["prompt_name"] == "narrative.expand_outline"
        return {"outline": {"volume_outlines": [{"volume": "第一卷", "chapters": "1-30"}],
                            "total_volumes": 8}}

    monkeypatch.setattr(gateway, "complete", fake_complete)
    result = client.get("/api/v1/novels/layered-plan", headers=headers,
                        params={"idea": "凡人修仙问道", "genre": "东方玄幻", "target_words": 1000000})
    assert result.status_code == 200
    assert result.json()["data"]["volume_outlines"][0]["volume"] == "第一卷"

    def empty_complete(**kwargs):
        return {"outline": {}}

    monkeypatch.setattr(gateway, "complete", empty_complete)
    import pytest
    from app.services.batch_fixes import build_layered_outline
    with pytest.raises(RuntimeError):
        build_layered_outline("凡人修仙问道")


def test_harness_final_phase_nodes_present_in_pipeline():
    """合理性审计与 humanize 通过 bootstrap 末段节点承担（20 节点管线）。"""
    from app.workers.tasks import BOOTSTRAP_NODES

    node_keys = [n[0] for n in BOOTSTRAP_NODES]
    for key in ("final_consistency_check", "final_continuity_audit", "final_humanize"):
        assert key in node_keys, f"{key} missing from pipeline"
    # humanize 是收尾写作节点，晚于审计节点
    assert node_keys.index("final_humanize") > node_keys.index("final_consistency_check")


# ===== insprira =====

def test_account_tracking_and_diagnostics_roundtrip():
    from app.db import connect, encode, new_id

    client, headers, project_id = _auth_project()
    account = f"acc-{uuid.uuid4().hex[:6]}"

    started = client.post("/api/v1/accounts/track", headers=headers,
                          params={"platform": "xiaohongshu", "account_id": account, "project_id": project_id})
    assert started.status_code == 200
    assert started.json()["data"]["status"] == "tracking_started"

    # Idempotent: second call reports already_tracked with the same id
    again = client.post("/api/v1/accounts/track", headers=headers,
                        params={"platform": "xiaohongshu", "account_id": account, "project_id": project_id})
    assert again.json()["data"]["status"] == "already_tracked"
    assert again.json()["data"]["tracking_id"] == started.json()["data"]["tracking_id"]

    # Diagnostics compute from真实 published_posts rows
    db = connect()
    for engagement in (3, 5):
        db.execute(
            "INSERT INTO published_posts (id, project_id, platform, title, body, status, meta) "
            "VALUES (%s,%s,'xiaohongshu','贴文','',%s,%s)",
            (new_id(), project_id, "published",
             encode({"account_id": account, "engagement": engagement})),
        )
    db.commit(); db.close()

    diag = client.get(f"/api/v1/accounts/xiaohongshu/{account}/diagnostics", headers=headers,
                      params={"project_id": project_id}).json()["data"]
    assert diag["total_posts"] == 2
    assert diag["avg_engagement"] == 4.0
    assert diag["redfox_index"] == 44.0  # 2*2 + 4*10
    assert diag["rating"] == "B"


def test_compliance_check_flags_violations_and_clean_text():
    client, headers, _ = _auth_project()
    dirty = client.post("/api/v1/content/check-compliance", headers=headers,
                        json={"text": "全网最低价，扫码立即关注，稳赚不赔！"})
    data = dirty.json()["data"]
    assert data["safe_to_publish"] is False
    categories = {v["category"] for v in data["violations"]}
    assert {"绝对化用语", "诱导引流", "金融风险"} <= categories

    clean = client.post("/api/v1/content/check-compliance", headers=headers,
                        json={"text": "今天的天空很好，主角在山里练剑。"})
    assert clean.json()["data"]["safe_to_publish"] is True


# ===== BrowserAct =====

def test_browseract_chrome_publish_reported_removed_in_fusion_status():
    """《25》合规：anti-bot 发布通路已删除，fusion 状态必须如实上报 removed。"""
    client, headers, _ = _auth_project()
    status = client.get("/api/v1/fusion/status", headers=headers).json()["data"]
    entry = status["fusion_governance"]["integration"]["entries"]["BrowserAct.chrome_publish"]
    assert entry["status"] == "removed"
    assert entry["route"] is None

    import app.services.fusion_browseract_insprira as fbi
    assert not hasattr(fbi, "scrape_ranking_with_browseract")
