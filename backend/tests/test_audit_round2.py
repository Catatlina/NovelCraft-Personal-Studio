"""Audit round-2 remediation: de-faked review/audit/matrix (real gateway calls),
explicit hotspot failure semantics, real agent console stats, ai_edit version
branches, honest workflow-executor semantics, and C5-05 autosave retention."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def authed():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"round2-{uuid.uuid4().hex[:6]}@nc.dev"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    return {"client": client, "headers": headers, "project_id": project_id}


# --- de-faked AI helpers: scores come from the gateway, never from len() ------

def test_fabricated_score_formulas_are_gone():
    source = (ROOT / "backend/app/services/providers_and_adapters.py").read_text(encoding="utf-8")
    assert "min(95, 50 + word_count // 100)" not in source
    assert "len(content) > threshold * 10" not in source
    assert '"status": "ready",  # Would call complete() in production' not in source


def test_multi_round_review_uses_real_gateway_scores(authed, monkeypatch):
    import app.gateway as gateway
    from app.services.providers_and_adapters import multi_round_review

    monkeypatch.setattr(gateway, "complete",
                        lambda **kwargs: {"score": 84, "dimensions": {}, "issues": ["示例问题"]})
    result = multi_round_review("测试正文" * 50, rounds=3, project_id=authed["project_id"])
    # score 84 passes 70/80 thresholds, fails 90 honestly — no fabricated pass
    assert result["status"] == "succeeded"
    assert result["final_pass"] is False
    assert [r["passed"] for r in result["rounds"]] == [True, True, False]
    assert all(r["score"] == 84 for r in result["rounds"])


def test_multi_round_review_surfaces_provider_failure(authed, monkeypatch):
    import app.gateway as gateway
    from app.services.providers_and_adapters import multi_round_review

    def _down(**kwargs):
        raise gateway.ProviderError("no provider key configured")

    monkeypatch.setattr(gateway, "complete", _down)
    result = multi_round_review("测试正文", rounds=2, project_id=authed["project_id"])
    assert result["status"] == "failed"
    assert result["final_pass"] is False
    assert result["rounds"][0]["status"] == "failed"


def test_cross_model_audit_reports_gateway_results(authed, monkeypatch):
    import app.gateway as gateway
    from app.services.providers_and_adapters import cross_model_audit

    monkeypatch.setattr(gateway, "complete",
                        lambda **kwargs: {"score": 84, "dimensions": {}, "issues": []})
    result = cross_model_audit("测试正文" * 50, models=["deepseek"], project_id=authed["project_id"])
    assert result["status"] == "succeeded"
    assert result["audits"][0]["score"] == 84
    assert result["audits"][0]["status"] == "succeeded"


def test_matrix_batch_run_actually_executes(authed, monkeypatch):
    import app.gateway as gateway
    from app.services.providers_and_adapters import matrix_batch_run

    calls = []
    monkeypatch.setattr(gateway, "complete",
                        lambda **kwargs: calls.append(kwargs) or {"text": "润色结果"})
    result = matrix_batch_run("editor.polish", [{"selection": "一段文字"}], models=["deepseek"],
                              project_id=authed["project_id"])
    assert result["total_runs"] == 1 and result["succeeded"] == 1
    assert result["results"][0]["output"] == {"text": "润色结果"}
    assert calls and calls[0]["prompt_name"] == "editor.polish"


# --- hotspots: source failures are explicit ------------------------------------

def test_hotspot_source_failures_are_reported(monkeypatch):
    from app.services import hotspot_collector as hc

    class _DownOpener:
        def open(self, *_args, **_kwargs):
            raise OSError("connection refused")

    # The collector routes through its own opener (proxy support); patching
    # urllib.request.urlopen no longer intercepts — and would hit real network.
    monkeypatch.setattr(hc, "_hotspot_opener", lambda: _DownOpener())
    items, status = hc.fetch_hotspots()
    assert items == []
    assert all(value.startswith("error") for value in status.values())


def test_hotspot_endpoint_returns_502_when_all_sources_fail(authed, monkeypatch):
    from app.api.v1 import hotspots as hotspots_api

    monkeypatch.setattr(hotspots_api, "fetch_hotspots",
                        lambda: ([], {"zhihu": "error: down", "weibo": "error: down"}))
    response = authed["client"].get("/api/v1/hotspots", headers=authed["headers"])
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "HOTSPOT_SOURCES_FAILED"


def test_hotspot_collector_has_no_silent_continue():
    source = (ROOT / "backend/app/services/hotspot_collector.py").read_text(encoding="utf-8")
    assert "except Exception:\n            continue" not in source


# --- agent console: real run_nodes aggregation ---------------------------------

def test_agents_status_aggregates_real_run_nodes(authed):
    from app.db import connect, encode, new_id

    client, headers, project_id = authed["client"], authed["headers"], authed["project_id"]
    novel_id = client.post(f"/api/v1/projects/{project_id}/novels", headers=headers,
                           json={"idea": "agent 状态", "genre": "科幻", "style": "紧凑", "target_words": 10000}).json()["data"]["id"]
    db = connect()
    run_id = new_id()
    db.execute(
        "INSERT INTO workflow_runs (id, project_id, novel_id, workflow_key, status, context) VALUES (%s,%s,%s,'bootstrap','running',%s)",
        (run_id, project_id, novel_id, encode({})),
    )
    db.execute(
        "INSERT INTO run_nodes (id, run_id, node_key, kind, agent, title, status, started_at) VALUES (%s,%s,'n1','agent','StoryArchitect','生成书名','succeeded',now())",
        (new_id(), run_id),
    )
    db.commit()
    db.close()

    data = client.get("/api/v1/agents/status", headers=headers).json()["data"]
    architect = next(a for a in data if a["name"] == "StoryArchitect")
    assert architect["task_count"] >= 1
    assert architect["last_run"] != "--"


def test_agents_status_does_not_report_stale_node_as_running(authed):
    from app.db import connect, encode, new_id

    client, headers, project_id = authed["client"], authed["headers"], authed["project_id"]
    novel_id = client.post(f"/api/v1/projects/{project_id}/novels", headers=headers,
                           json={"idea": "过期 agent 状态", "genre": "科幻", "style": "紧凑", "target_words": 10000}).json()["data"]["id"]
    db = connect()
    run_id = new_id()
    db.execute(
        "INSERT INTO workflow_runs (id, project_id, novel_id, workflow_key, status, current_node_key, context) "
        "VALUES (%s,%s,%s,'bootstrap','running','stale_node',%s)",
        (run_id, project_id, novel_id, encode({})),
    )
    db.execute(
        "INSERT INTO run_nodes (id, run_id, node_key, kind, agent, title, status, started_at) "
        "VALUES (%s,%s,'stale_node','agent','StaleAuditAgent','陈旧任务','running',now() - interval '2 hours')",
        (new_id(), run_id),
    )
    db.commit()
    db.close()

    data = client.get("/api/v1/agents/status", headers=headers).json()["data"]
    stale = next(a for a in data if a["name"] == "StaleAuditAgent")
    assert stale["status"] == "stale"


# --- ai_edit leaves a version branch (C5-03) -----------------------------------

def test_ai_edit_creates_version_branch(authed, monkeypatch):
    from app.db import connect, encode, new_id

    client, headers, project_id = authed["client"], authed["headers"], authed["project_id"]
    content_id = new_id()
    db = connect()
    db.execute(
        "INSERT INTO contents (id, project_id, type, title, body, meta, status) VALUES (%s,%s,'chapter','编辑测试',%s,%s,'draft')",
        (content_id, project_id, encode({"type": "doc", "content": [{"type": "paragraph", "text": "原文"}]}), encode({"seq": 1})),
    )
    db.commit()
    db.close()

    import app.main as main_module
    monkeypatch.setattr(main_module, "complete", lambda **kwargs: {"text": "润色后的原文"})
    response = client.post(f"/api/v1/contents/{content_id}/ai/polish", headers=headers,
                           json={"selection": "原文", "instruction": "", "client_mutation_id": f"edit-{content_id}"})
    assert response.status_code == 200

    db = connect()
    version = db.execute(
        "SELECT * FROM versions WHERE entity_id=%s AND label='ai_edit'", (content_id,)
    ).fetchone()
    db.close()
    assert version is not None


def test_ai_edit_returns_review_and_next_chapter_plan(authed, monkeypatch):
    from app.db import connect, encode, new_id

    client, headers, project_id = authed["client"], authed["headers"], authed["project_id"]
    content_id = new_id()
    db = connect()
    db.execute(
        "INSERT INTO contents (id, project_id, type, title, body, meta, status) VALUES (%s,%s,'chapter','整章重写测试',%s,%s,'draft')",
        (content_id, project_id,
         encode({"type": "doc", "content": [{"type": "paragraph", "text": "原文段落"}]}),
         encode({"seq": 3})),
    )
    db.commit()
    db.close()

    calls: list[str] = []

    def fake_complete(**kwargs):
        calls.append(kwargs["task_type"])
        if kwargs["task_type"] == "review_7dim":
            return {"score": 88, "issues": ["节奏可加强"]}
        if kwargs["task_type"] == "plan_next_chapter":
            return {"next_title": "第四章 回声", "goals": ["推进主线"], "conflicts": ["制造新阻力"], "warnings": []}
        return {"text": "重写后的章节正文"}

    import app.main as main_module
    monkeypatch.setattr(main_module, "complete", fake_complete)

    response = client.post(
        f"/api/v1/contents/{content_id}/ai/rewrite_chapter",
        headers=headers,
        json={"selection": "原文段落", "instruction": "整章重写", "client_mutation_id": f"rewrite-{content_id}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["text"] == "重写后的章节正文"
    assert data["review_7dim"]["score"] == 88
    assert data["next_chapter_plan"]["next_title"] == "第四章 回声"
    assert calls == ["editor_rewrite", "review_7dim", "plan_next_chapter"]


# --- workflow executor: honest semantics ---------------------------------------

def test_non_bootstrap_workflow_dispatches_with_nodes(authed):
    from app.db import connect, new_id, encode

    client, headers, project_id = authed["client"], authed["headers"], authed["project_id"]
    novel_id = client.post(f"/api/v1/projects/{project_id}/novels", headers=headers,
                           json={"idea": "wf 测试", "genre": "科幻", "style": "紧凑", "target_words": 10000}).json()["data"]["id"]
    wf_name = f"custom-{uuid.uuid4().hex[:6]}"
    db = connect()
    db.execute("INSERT INTO workflows (id, name, definition) VALUES (%s,%s,%s)",
               (new_id(), wf_name,
                encode({"nodes": [{"key": "n1", "kind": "agent", "title": "测试节点", "task": "gen_titles"}]})))
    db.commit()
    db.close()

    response = authed["client"].post(
        f"/api/v1/admin/workflows/{wf_name}/execute?project_id={project_id}&novel_id={novel_id}",
        headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "dispatched"
    assert data["total_nodes"] == 1


def test_workflow_draft_contract_persists_definition_and_is_project_scoped(authed):
    client, headers, project_id = authed["client"], authed["headers"], authed["project_id"]
    payload = {"project_id": project_id,
               "nodes": [{"key": "n1", "kind": "agent", "title": "设计节点", "task": "gen_titles"}]}
    saved = client.put("/api/v1/admin/workflows/custom-dag", headers=headers, json=payload)
    assert saved.status_code == 200
    assert saved.json()["data"]["definition"]["nodes"][0]["title"] == "设计节点"

    listed = client.get(f"/api/v1/admin/workflows?project_id={project_id}", headers=headers)
    assert listed.status_code == 200
    assert any(item["name"] == "custom-dag" for item in listed.json()["data"])

    email = f"isolated-{uuid.uuid4().hex[:6]}@nc.dev"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()["data"]["access_token"]
    other_headers = {"Authorization": f"Bearer {token}"}
    assert client.get(f"/api/v1/admin/workflows?project_id={project_id}", headers=other_headers).status_code == 403


def test_system_bootstrap_workflow_cannot_be_overwritten(authed):
    response = authed["client"].put(
        "/api/v1/admin/workflows/bootstrap", headers=authed["headers"],
        json={"project_id": authed["project_id"],
              "nodes": [{"key": "n1", "kind": "agent", "title": "伪 Bootstrap"}]},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SYSTEM_WORKFLOW_READ_ONLY"


def test_workflow_scope_migration_adds_real_columns_and_indexes():
    sql = (ROOT / "backend/alembic/versions/nc_audit_workflow_scope.py").read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS project_id" in sql
    assert "workflows_project_name_uq" in sql


def test_no_duplicate_method_path_routes_are_registered():
    from collections import Counter

    from app.main import app

    pairs = [
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if method.upper() not in {"HEAD", "OPTIONS"}
    ]
    assert [pair for pair, count in Counter(pairs).items() if count > 1] == []


def test_budget_update_matches_settings_request_body(authed):
    response = authed["client"].put(
        f"/api/v1/admin/budgets/{authed['project_id']}/bootstrap",
        headers=authed["headers"], json={"limit_cny": 3.25},
    )
    assert response.status_code == 200
    assert float(response.json()["data"]["limit_cny"]) == 3.25


def test_settings_uses_real_knowledge_and_budget_endpoints():
    source = (ROOT / "frontend/src/components/Settings.tsx").read_text(encoding="utf-8")
    assert "/api/v1/import/knowledge_hub" not in source
    assert "/api/v1/admin/knowledge_hub" not in source
    assert "/api/v1/knowledge/import?project_id=" in source
    assert "/api/v1/admin/budgets/${editBudget.pid}/${encodeURIComponent(editBudget.scope)}" in source


def test_frontend_response_contracts_match_backend_wrappers():
    knowledge = (ROOT / "frontend/src/components/KnowledgeBrowser.tsx").read_text(encoding="utf-8")
    hotspots = (ROOT / "frontend/src/components/HotspotDashboard.tsx").read_text(encoding="utf-8")
    fanout = (ROOT / "frontend/src/components/FanoutMatrix.tsx").read_text(encoding="utf-8")
    publishing = (ROOT / "frontend/src/components/PublishDashboard.tsx").read_text(encoding="utf-8")
    assert 'project_id: projectId, query' in knowledge and 'method: "POST"' in knowledge
    assert "r.data || []" in knowledge
    assert "response?.data || {}" in hotspots
    assert "(data.data as any)?.items || []" in fanout
    assert "Promise.allSettled(selected.map(platform" in publishing
    assert 'platform=${selected.join(",")}' not in publishing


def test_short_story_persists_user_idea_and_template(authed, monkeypatch):
    from app.db import connect
    from app.workers import tasks

    monkeypatch.setattr(tasks.bootstrap_short_story_task, "delay",
                        lambda *_args, **_kwargs: type("Task", (), {"id": "task-1"})())
    response = authed["client"].post(
        f"/api/v1/projects/{authed['project_id']}/short-stories",
        headers=authed["headers"],
        json={"idea": "真实用户输入的悬疑短篇", "template": "suspense",
              "genre": "悬疑", "style": "冷峻"},
    )
    assert response.status_code == 200
    db = connect()
    row = db.execute("SELECT meta FROM contents WHERE id=%s", (response.json()["data"]["short_id"],)).fetchone()
    db.close()
    assert row["meta"]["idea"] == "真实用户输入的悬疑短篇"
    assert row["meta"]["template"] == "suspense"


def test_fanout_provider_failure_does_not_create_fake_content(authed, monkeypatch):
    import app.main as main_module
    from app.db import connect, encode, new_id
    from app.gateway import ProviderError

    content_id = new_id()
    db = connect()
    db.execute(
        "INSERT INTO contents (id,project_id,type,title,body,meta,status) VALUES (%s,%s,'chapter','原文',%s,%s,'draft')",
        (content_id, authed["project_id"],
         encode({"type": "doc", "content": [{"type": "paragraph", "text": "这是真实原文"}]}),
         encode({"seq": 1})),
    )
    db.commit(); db.close()
    monkeypatch.setattr(main_module, "complete", lambda **_kwargs: (_ for _ in ()).throw(ProviderError("down")))
    response = authed["client"].post(
        f"/api/v1/contents/{content_id}/fanout?platforms=wechat", headers=authed["headers"])
    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["status"] == "failed"
    db = connect()
    count = db.execute("SELECT COUNT(*) AS c FROM contents WHERE parent_id=%s", (content_id,)).fetchone()["c"]
    db.close()
    assert count == 0


# --- C5-05: autosave retention --------------------------------------------------

def test_purge_keeps_recent_and_semantic_versions(authed):
    from app.db import connect, encode, new_id
    from app.workers.tasks import purge_stale_autosaves

    client, headers, project_id = authed["client"], authed["headers"], authed["project_id"]
    content_id = new_id()
    db = connect()
    db.execute(
        "INSERT INTO contents (id, project_id, type, title, body, meta, status) VALUES (%s,%s,'chapter','保留测试',%s,%s,'draft')",
        (content_id, project_id, encode({"type": "doc", "content": []}), encode({"seq": 1})),
    )
    for index in range(12):
        db.execute(
            "INSERT INTO versions (id, entity_type, entity_id, label, snapshot, created_at) "
            "VALUES (%s,'content',%s,'manual_save',%s, now() - interval '8 days' + (%s * interval '1 minute'))",
            (new_id(), content_id, encode({"n": index}), index),
        )
    db.execute(
        "INSERT INTO versions (id, entity_type, entity_id, label, snapshot, created_at) "
        "VALUES (%s,'content',%s,'ai_edit',%s, now() - interval '30 days')",
        (new_id(), content_id, encode({"keep": True})),
    )
    db.commit()
    db.close()

    purge_stale_autosaves.run()

    db = connect()
    manual = db.execute(
        "SELECT COUNT(*) AS c FROM versions WHERE entity_id=%s AND label='manual_save'", (content_id,)
    ).fetchone()["c"]
    semantic = db.execute(
        "SELECT COUNT(*) AS c FROM versions WHERE entity_id=%s AND label='ai_edit'", (content_id,)
    ).fetchone()["c"]
    db.close()
    assert manual == 10  # 12 stale → newest 10 kept
    assert semantic == 1  # semantic branches never purged
