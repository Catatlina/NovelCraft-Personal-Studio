from __future__ import annotations

import uuid
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]


def _auth_project():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"auditfix-{uuid.uuid4().hex[:8]}@nc.dev"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    return client, headers, project_id


def test_daily_briefing_uses_real_collected_hotspots_only(monkeypatch):
    from app.services import hotspot as hotspot_service
    from app.services import hotspot_collector

    def fake_fetch_hotspots(user_id: str = ""):
        return ([{"title": "真实采集热点", "source": "baidu", "category": "tech", "url": "https://example.com/h"}],
                {"baidu": "ok"})

    calls = []

    def fake_complete(**kwargs):
        calls.append(kwargs)
        assert kwargs["task_type"] == "hm_daily_brief"
        assert kwargs["variables"]["topic"] == "真实采集热点"
        return {"wechat_draft": "草稿", "toutiao_draft": "草稿", "xhs_draft": "草稿"}

    monkeypatch.setattr(hotspot_collector, "fetch_hotspots", fake_fetch_hotspots)
    monkeypatch.setattr(hotspot_collector, "store_hotspots", lambda items: len(items))
    monkeypatch.setattr(hotspot_service, "complete", fake_complete)

    result = hotspot_service.generate_daily_briefing(project_id=str(uuid.uuid4()), user_id=str(uuid.uuid4()))
    assert result["source"] == "real_collector"
    assert result["topics"][0]["title"] == "真实采集热点"
    assert calls and calls[0]["prompt_name"] == "social.gen_daily_brief"

    source = (ROOT / "backend/app/services/hotspot.py").read_text(encoding="utf-8")
    assert 'task_type="fetch_hotspots"' not in source
    assert "列出当前中文互联网最热门" not in source


def test_book_analysis_workbench_uses_gateway_not_heuristics(monkeypatch):
    from app.services import providers_and_adapters as pa

    calls = []

    def fake_complete(**kwargs):
        calls.append(kwargs)
        return {
            "title": kwargs["variables"]["title"],
            "total_paragraphs": 8,
            "opening_hook": "开篇钩子明确",
            "detected_tropes": ["系统流"],
            "rhythm": "快节奏",
            "avg_paragraph_length": 88,
            "structure_cards": {"three_act": "成立", "save_the_cat": "关键节拍清晰"},
            "style_profile": {"tone": "爽文"},
            "risks": [],
            "recommendations": ["加强反派压迫感"],
        }

    import app.gateway as gateway

    monkeypatch.setattr(gateway, "complete", fake_complete)
    result = pa.book_analysis_workbench("测试书", "第一段\n第二段" * 100, project_id=str(uuid.uuid4()))

    assert result["title"] == "测试书"
    assert calls and calls[0]["task_type"] == "book_analysis"
    assert calls[0]["prompt_name"] == "book.analysis_workbench"

    source = (ROOT / "backend/app/services/providers_and_adapters.py").read_text(encoding="utf-8")
    assert "Estimated beats" not in source
    assert "len(paragraphs) // 15" not in source


def test_hm_content_generation_uses_gateway_contracts(monkeypatch):
    from app.services import hm_content
    import app.gateway as gateway

    calls = []

    def fake_complete(**kwargs):
        calls.append(kwargs)
        task_type = kwargs["task_type"]
        if task_type == "gen_daily_brief":
            return {"title": "标题", "body": ["正文"], "meta": {"tags": ["热点"]}}
        if task_type == "hm_title_variants":
            return {"titles": ["标题1", "标题2"]}
        if task_type == "gen_video_script":
            return {"title": "视频", "scenes": [{"time": "0-3s", "action": "开场", "text": "口播"}]}
        if task_type == "hm_material_suggestions":
            return {"cover_image_prompt": "封面", "suggested_charts": [], "data_sources": [], "recommended_tags": []}
        raise AssertionError(task_type)

    monkeypatch.setattr(gateway, "complete", fake_complete)
    project_id = str(uuid.uuid4())

    article = hm_content.generate_article_variants({"title": "真实热点", "source": "baidu", "url": "https://e.test"}, "wechat", project_id=project_id)
    titles = hm_content.generate_title_variants("真实热点", project_id=project_id)
    script = hm_content.generate_video_script("真实热点", project_id=project_id)
    materials = hm_content.generate_material_suggestions("真实热点", "正文", project_id=project_id)

    assert article["draft"]["title"] == "标题"
    assert titles == ["标题1", "标题2"]
    assert script["scenes"][0]["time"] == "0-3s"
    assert materials["cover_image_prompt"] == "封面"
    assert {call["task_type"] for call in calls} == {
        "gen_daily_brief", "hm_title_variants", "gen_video_script", "hm_material_suggestions",
    }

    source = (ROOT / "backend/app/services/hm_content.py").read_text(encoding="utf-8")
    assert "震惊" not in source
    assert "prompt_name=\"social.hm_title_variants\"" in source
    assert "prompt_name=\"social.hm_material_suggestions\"" in source


def test_budget_tracking_syncs_real_ai_call_spend():
    from app.db import connect, encode, new_id
    from app.workers.tasks import _track_budget

    _client, _headers, project_id = _auth_project()
    run_id = new_id()
    db = connect()
    db.execute(
        "INSERT INTO workflow_runs (id, project_id, workflow_key, status) VALUES (%s,%s,'bootstrap','running')",
        (run_id, project_id),
    )
    db.execute(
        """INSERT INTO ai_calls (id, project_id, run_id, node_key, provider, model, prompt_name, task_type,
               input, output, prompt_tokens, completion_tokens, cost_cny, latency_ms, status)
           VALUES (%s,%s,%s,'n1','deepseek','deepseek-chat','p','gen_synopsis',%s,%s,10,20,0.1234,100,'succeeded')""",
        (new_id("call"), project_id, run_id, encode({}), encode({"ok": True})),
    )
    db.execute(
        """INSERT INTO budgets (id, project_id, scope, limit_cny, spent_cny)
           VALUES (%s,%s,'bootstrap',1.0,0)
           ON CONFLICT(project_id, scope) DO UPDATE SET limit_cny=1.0, spent_cny=0""",
        (new_id("bdg"), project_id),
    )
    db.commit()
    db.close()

    result = _track_budget(run_id, "n1", 0.1234)
    assert result["status"] == "ok"
    assert result["spent"] == 0.1234
    assert result["limit"] == 1.0

    db = connect()
    row = db.execute("SELECT spent_cny FROM budgets WHERE project_id=%s AND scope='bootstrap'", (project_id,)).fetchone()
    db.close()
    assert float(row["spent_cny"]) == 0.1234


def test_fusion_browseract_removed_not_active():
    from app.services.fusion_governance import FUSION_ENTRY_MAP, get_fusion_integration_status

    entry = FUSION_ENTRY_MAP["BrowserAct.chrome_publish"]
    assert entry["expected_state"] == "removed"
    assert not entry["route"]
    status = get_fusion_integration_status()
    assert "BrowserAct.chrome_publish" not in [
        key for key, item in status["entries"].items() if item["status"] == "verified"
    ]
    assert status["entries"]["BrowserAct.chrome_publish"]["status"] == "removed"


def test_publish_execution_reads_stored_platform_credentials(monkeypatch):
    from app.db import connect, encode, new_id
    from app.services.publish_hub import register_platform_account
    from app.workers import m4_tasks

    client, headers, project_id = _auth_project()
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["data"]["id"]
    register_platform_account(
        "wordpress",
        "blog",
        {"wp_url": "https://example.com", "wp_user": "alice", "wp_pass": "stored-secret"},
        user_id=user_id,
    )

    content_id = new_id()
    db = connect()
    db.execute(
        """INSERT INTO contents (id, project_id, type, title, body, meta, status, owner_id)
           VALUES (%s,%s,'wechat_article','待发布',%s,%s,'draft',%s)""",
        (content_id, project_id,
         encode({"type": "doc", "content": [{"type": "paragraph", "text": "正文"}]}),
         encode({}), user_id),
    )
    db.commit()
    db.close()

    seen = {}

    def fake_wordpress(title, body, wp_url, wp_user, wp_pass):
        seen.update({"wp_url": wp_url, "wp_user": wp_user, "wp_pass": wp_pass})
        return {"status": "draft_created", "url": "https://example.com/p/1"}

    monkeypatch.setattr(m4_tasks, "_publish_to_wordpress", fake_wordpress)
    result = m4_tasks.auto_publish_article.run(content_id, "wordpress", None)
    assert result["status"] == "draft_created"
    assert seen == {"wp_url": "https://example.com", "wp_user": "alice", "wp_pass": "stored-secret"}


def test_one_off_publish_reads_stored_credentials(monkeypatch):
    from app.services import providers_and_adapters as pa

    client, headers, _project_id = _auth_project()
    client.post("/api/v1/platform-connections", headers=headers, json={
        "platform": "x",
        "account_name": "default",
        "credentials": {"bearer_token": "stored-token"},
    })

    seen = {}

    def fake_x(title, body, token=""):
        seen["token"] = token
        return {"status": "submitted", "platform": "x", "mode": "api"}

    monkeypatch.setattr(pa, "_publish_x", fake_x)
    response = client.post(
        "/api/v1/publish/x",
        params={"title": "标题", "body": "正文"},
        headers=headers,
        json={},
    )
    assert response.status_code == 200
    assert seen["token"] == "stored-token"


def test_provider_test_failure_is_not_wrapped_as_success(monkeypatch):
    from app.services import providers_and_adapters as pa

    client, headers, project_id = _auth_project()
    monkeypatch.setattr(pa, "_openai_complete",
                        lambda *args, **kwargs: {"provider": "openai", "degraded": True, "error": "bad key"})
    response = client.get(
        "/api/v1/providers/test/openai",
        params={"project_id": project_id, "model": "gpt-4o"},
        headers={**headers, "X-Api-Key": "invalid"},
    )
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "PROVIDER_TEST_FAILED"


def test_responsive_css_targets_real_layout():
    css = (ROOT / "frontend/src/styles.css").read_text(encoding="utf-8")
    media = css.split("@media (max-width: 768px)", 1)[1]
    assert ".layout" in media
    assert "display: flex" in media
    assert ".app-shell" not in media


def test_costs_tab_uses_response_data_arrays():
    app = (ROOT / "frontend/src/App.tsx").read_text(encoding="utf-8")
    costs = (ROOT / "frontend/src/components/Costs.tsx").read_text(encoding="utf-8")
    assert "setBudgets(response.data || [])" in app
    assert "setRoutes(response.data || [])" in app
    assert "Array.isArray(aiCalls)" in costs
    assert "safeRoutes.slice(0,10)" in costs


def test_env_example_documents_real_runtime_config():
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    for key in [
        "NOVELCRAFT_CREDENTIALS_KEY",
        "DATABASE_URL",
        "REDIS_URL",
        "CLAUDE_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "HOTSPOT_HTTP_PROXY",
        "TELEGRAM_BOT_TOKEN",
        "SENTRY_DSN",
        "METRICS_TOKEN",
    ]:
        assert key in env
