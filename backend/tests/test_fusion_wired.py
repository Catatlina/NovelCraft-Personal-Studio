"""Fusion integration wiring (audit follow-up 2026-07-13).

The six upstream fusions are only real if the flagship flow actually
exercises them and their API surface is mounted. The full-flow test
(test_v2_bootstrap_full_flow) proves runtime behavior; these tests pin the
structural wiring so a refactor can't silently orphan a fused capability.
"""
import pytest
from fastapi.testclient import TestClient

from app.db import init_db, new_id
from app.main import app
from app.workers.tasks import BOOTSTRAP_NODES


@pytest.fixture()
def client():
    from app.core.rate_limit import limiter

    limiter.reset()
    init_db()
    return TestClient(app)


def _auth_headers(client):
    r = client.post("/api/v1/auth/register", json={
        "email": f"fus-{new_id()[:8]}@test.local", "password": "Str0ngPass!x", "display_name": "F"})
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


def test_fusion_status_endpoint_is_mounted(client):
    """53a3857 shipped fusion.py but never mounted it — /fusion/status 404'd."""
    headers = _auth_headers(client)
    r = client.get("/api/v1/fusion/status", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["deep_workflow"]["available"] is True


def test_flagship_flow_exercises_each_fused_capability():
    node_keys = [n[0] for n in BOOTSTRAP_NODES]
    # harnessNovel: hierarchical planning (plan → blueprint layers)
    assert "plan_story_pattern" in node_keys and "blueprint_volume_plan" in node_keys
    # show-me-the-story: chapter fact reconciliation
    assert "write_fact_reconcile" in node_keys
    # AI_NovelGenerator: six-dimension consistency finalization
    assert "final_consistency_check" in node_keys
    # oh-story: deslop/humanize finalization
    assert "final_humanize" in node_keys


def test_denova_event_ledger_wired_into_bootstrap():
    import inspect

    from app.workers import tasks

    src = inspect.getsource(tasks.execute_bootstrap.run.__wrapped__) if hasattr(
        tasks.execute_bootstrap.run, "__wrapped__") else inspect.getsource(tasks)
    for event in ("run.started", "node.completed", "checkpoint.created", "run.completed"):
        assert event in src, f"event ledger call for {event} missing from bootstrap"


def test_oh_story_skills_and_license_preserved():
    from pathlib import Path

    upstream = Path(__file__).resolve().parents[1] / "app" / "prompts" / "upstream"
    assert (upstream / "LICENSE.oh-story").exists()
    skills = [p.name for p in upstream.iterdir() if p.is_dir()]
    for required in ("story-deslop", "story-review", "story-long-write", "story-setup"):
        assert required in skills, f"upstream skill {required} missing"


def test_methodology_prompts_reference_fused_methods():
    from app.prompt_registry import PROMPT_SEEDS

    by_name = {name: tpl for name, _v, _m, tpl in PROMPT_SEEDS}
    assert "story-long-write" in by_name["bootstrap.write_chapter_draft"]
    assert "story-deslop" in by_name["bootstrap.final_humanize"]
    assert "show-me-the-story" in by_name["bootstrap.write_fact_reconcile"]
    assert "七维" in by_name["bootstrap.final_consistency_check"]
    assert "source_fidelity" in by_name["bootstrap.final_consistency_check"]
