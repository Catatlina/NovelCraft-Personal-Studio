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
    assert result["status"] == "pending_provider"
    assert result["final_pass"] is False
    assert result["rounds"][0]["status"] == "pending_provider"


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
    import urllib.request

    from app.services.hotspot_collector import fetch_hotspots

    def _down(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", _down)
    items, status = fetch_hotspots()
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


# --- workflow executor: honest semantics ---------------------------------------

def test_non_bootstrap_workflow_returns_501(authed):
    from app.db import connect, new_id

    client, headers, project_id = authed["client"], authed["headers"], authed["project_id"]
    novel_id = client.post(f"/api/v1/projects/{project_id}/novels", headers=headers,
                           json={"idea": "wf 测试", "genre": "科幻", "style": "紧凑", "target_words": 10000}).json()["data"]["id"]
    wf_name = f"custom-{uuid.uuid4().hex[:6]}"
    db = connect()
    db.execute("INSERT INTO workflows (id, name, definition) VALUES (%s,%s,'{}')", (new_id(), wf_name))
    db.commit()
    db.close()

    response = authed["client"].post(
        f"/api/v1/admin/workflows/{wf_name}/execute?project_id={project_id}&novel_id={novel_id}",
        headers=headers)
    assert response.status_code == 501
    assert response.json()["detail"]["code"] == "WORKFLOW_EXECUTOR_NOT_IMPLEMENTED"


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
