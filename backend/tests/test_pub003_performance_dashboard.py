"""NC-PUB-003 推进到待验收：指标口径、效果看板、可追溯选题建议、真实 AI 反哺。"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _auth_project():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"pub3-{uuid.uuid4().hex[:8]}@nc.dev"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    return client, headers, project_id


def _seed_posts(project_id: str) -> list[str]:
    from app.db import connect, encode, new_id

    db = connect()
    ids = []
    for title, platform, reads, revenue in (
        ("爆款文章A", "wechat", 5000, 80.0),
        ("普通文章B", "toutiao", 300, 3.0),
        ("冷门文章C", "zhihu", 20, 0.0),
    ):
        pid = new_id()
        ids.append(pid)
        db.execute(
            "INSERT INTO published_posts (id, project_id, platform, title, body, status, meta) "
            "VALUES (%s,%s,%s,%s,'', 'published', %s)",
            (pid, project_id, platform, title,
             encode({"reads": reads, "likes": reads // 10, "shares": reads // 50, "revenue": revenue})),
        )
    db.commit(); db.close()
    return ids


def test_dashboard_metrics_glossary_totals_roi_and_traceable_suggestions():
    client, headers, project_id = _auth_project()
    post_ids = _seed_posts(project_id)

    data = client.get("/api/v1/analytics/dashboard", headers=headers).json()["data"]

    # 指标口径固化
    assert set(data["metrics_glossary"]) >= {"reads", "likes", "shares", "revenue", "rpm", "posts"}
    assert "1000" in data["metrics_glossary"]["rpm"]

    assert data["totals"]["total_reads"] == 5320
    assert data["totals"]["total_revenue"] == 83.0
    assert data["totals"]["total_posts"] == 3

    roi = {r["platform"]: r for r in data["roi_by_platform"]}
    assert roi["wechat"]["rpm"] == 16.0  # 80 / 5000 * 1000
    assert data["roi_by_platform"][0]["platform"] == "wechat"  # revenue desc

    # top_posts 按阅读排序且带 post_id
    assert data["top_posts"][0]["title"] == "爆款文章A"
    assert data["top_posts"][0]["post_id"] == post_ids[0]

    # 建议可追溯：绑定 source_post_id，且只推荐 reads>100 的内容
    suggestions = data["topic_suggestions"]
    assert {s["source_post_id"] for s in suggestions} == {post_ids[0], post_ids[1]}
    assert all("表现优异" in s["suggestion"] for s in suggestions)


def test_dashboard_empty_project_returns_explicit_no_data_suggestion():
    client, headers, _ = _auth_project()
    data = client.get("/api/v1/analytics/dashboard", headers=headers).json()["data"]
    assert data["totals"]["total_posts"] == 0
    assert data["topic_suggestions"][0]["source_post_id"] is None
    assert "暂无足够数据" in data["topic_suggestions"][0]["suggestion"]


def test_ai_feedback_binds_based_on_to_real_posts_and_fails_explicitly(monkeypatch):
    import app.gateway as gateway

    client, headers, project_id = _auth_project()
    post_ids = _seed_posts(project_id)
    calls = []

    def fake_complete(**kwargs):
        calls.append(kwargs)
        assert kwargs["prompt_name"] == "publish.performance_feedback"
        assert kwargs["task_type"] == "performance_feedback"
        # 输入必须携带真实回流数据
        assert "爆款文章A" in kwargs["variables"]["performance_data"]
        return {"topic_suggestions": [
                    {"suggestion": "深耕职场爆款系列", "rationale": "wechat RPM 最高",
                     "based_on": [post_ids[0], "fabricated-post-id"]}],
                "writing_advice": ["标题控制在 18 字内"]}

    monkeypatch.setattr(gateway, "complete", fake_complete)
    result = client.post("/api/v1/analytics/feedback", headers=headers,
                         json={"project_id": project_id})
    assert result.status_code == 200
    data = result.json()["data"]
    assert data["status"] == "ok"
    # 追溯：编造的 post id 被过滤，只保留真实源数据
    assert data["topic_suggestions"][0]["based_on"] == [post_ids[0]]
    assert post_ids[0] in data["source_posts"]
    assert calls, "AI 网关必须被真实调用"

    def failing(**kwargs):
        raise gateway.ProviderError("provider down")

    monkeypatch.setattr(gateway, "complete", failing)
    failed = client.post("/api/v1/analytics/feedback", headers=headers,
                         json={"project_id": project_id})
    assert failed.status_code == 502


def test_ai_feedback_without_data_declines_instead_of_inventing(monkeypatch):
    import app.gateway as gateway

    client, headers, project_id = _auth_project()

    def must_not_call(**kwargs):
        raise AssertionError("no-data path must not invoke the AI gateway")

    monkeypatch.setattr(gateway, "complete", must_not_call)
    result = client.post("/api/v1/analytics/feedback", headers=headers,
                         json={"project_id": project_id}).json()["data"]
    assert result["status"] == "no_data"
    assert result["topic_suggestions"] == []


def test_feedback_requires_project_membership():
    client, headers, _ = _auth_project()
    foreign = client.post("/api/v1/analytics/feedback", headers=headers,
                          json={"project_id": str(uuid.uuid4())})
    assert foreign.status_code == 403
