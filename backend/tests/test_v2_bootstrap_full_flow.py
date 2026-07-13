"""T2 full-flow: the audit's "Journey A" (从零建书 → 一键生成) end to end.

Runs the complete V2 four-stage workflow synchronously against the real test
database with the mock provider: create_run seeds 19 nodes, planning runs to
the human gate, title confirmation resumes the run, and blueprint → writing →
finalization persist a real chapter row, knowledge items and an event ledger.

The 2026-07-13 acceptance audit proved this journey died at the first node
(no routes / no prompts / fictional model). This test locks the journey shut.
"""
import os

import pytest

from app.db import connect, encode, init_db, new_id


V2_TASK_TYPES = [
    "plan_idea", "plan_market_fit", "plan_story_pattern", "plan_core_gameplay",
    "plan_world_architecture", "plan_character_system", "plan_conflict_map",
    "blueprint_volume_plan", "blueprint_chapter_outline", "blueprint_scene_beat",
    "write_chapter_draft", "write_self_review", "write_polish",
    "write_length_check", "write_fact_reconcile",
    "final_consistency_check", "final_continuity_audit", "final_humanize",
]


@pytest.fixture()
def seeded_novel(monkeypatch):
    # Several legacy test modules overwrite NOVELCRAFT_ENV at import time and
    # never restore it; pin the mock-gate env for this flow explicitly.
    monkeypatch.setenv("NOVELCRAFT_ENV", "test")
    monkeypatch.setenv("NOVELCRAFT_ALLOW_MOCK", "true")
    init_db()
    db = connect()
    # Explicit test boundary: route the V2 nodes through the guarded mock
    # provider so the orchestration/persistence chain runs without a real key.
    db.execute(
        "UPDATE model_routes SET provider='mock', model='mock' WHERE task_type = ANY(%s)",
        (V2_TASK_TYPES,),
    )
    db.commit()
    user_id = new_id()
    db.execute(
        "INSERT INTO users (id, email, password_hash, display_name) VALUES (%s,%s,%s,%s)",
        (user_id, f"t2-{user_id[:8]}@test.local", "x", "T2"),
    )
    project_id = new_id()
    db.execute(
        "INSERT INTO projects (id, name, owner_id) VALUES (%s,%s,%s)",
        (project_id, "T2 全链", user_id),
    )
    db.execute(
        "INSERT INTO project_members (id, project_id, user_id, role) VALUES (%s,%s,%s,'owner')",
        (new_id(), project_id, user_id),
    )
    novel_id = new_id()
    db.execute(
        "INSERT INTO contents (id, project_id, type, title, body, meta, status) "
        "VALUES (%s,%s,'novel','未命名',%s,%s,'draft')",
        (novel_id, project_id, encode({}),
         encode({"idea": "一个作者发现自己写的故事正在现实中发生", "genre": "悬疑", "style": "克制"})),
    )
    db.commit()
    db.close()
    yield project_id, novel_id
    # Restore the real routes so wiring tests in the same DB stay truthful.
    db = connect()
    db.execute(
        "UPDATE model_routes SET provider='deepseek', model='deepseek-chat' WHERE task_type = ANY(%s)",
        (V2_TASK_TYPES,),
    )
    db.commit()
    db.close()


def _run_state(run_id):
    db = connect()
    run = db.execute("SELECT * FROM workflow_runs WHERE id=%s", (run_id,)).fetchone()
    nodes = db.execute(
        "SELECT node_key, status FROM run_nodes WHERE run_id=%s", (run_id,)
    ).fetchall()
    db.close()
    return run, {n["node_key"]: n["status"] for n in nodes}


def test_journey_a_full_v2_flow_mock_provider(seeded_novel):
    from app.workers import tasks

    project_id, novel_id = seeded_novel

    # celery eager-ish: call the underlying function synchronously
    run_id = None

    def sync_dispatch(rid, start_key, api_key="", api_url="", model=""):
        tasks.execute_bootstrap.run(rid, start_key, api_key, api_url, model)

    original_delay = tasks.execute_bootstrap.delay
    tasks.execute_bootstrap.delay = sync_dispatch  # type: ignore[assignment]
    try:
        run_id = tasks.create_run(project_id, novel_id)

        run, node_status = _run_state(run_id)
        # 19 nodes seeded, planning succeeded, human gate reached
        assert len(node_status) == 19
        assert run["status"] == "waiting_human"
        for key in ("plan_idea", "plan_market_fit", "plan_story_pattern", "plan_core_gameplay",
                    "plan_world_architecture", "plan_character_system", "plan_conflict_map"):
            assert node_status[key] == "succeeded", (key, node_status[key])
        assert node_status["human_confirm_title"] == "waiting_human"

        # Human gate has real title candidates in context (frontend renders these)
        titles = run["context"].get("title_candidates") or []
        assert len(titles) >= 3, run["context"].keys()

        # Confirm title → workflow resumes through blueprint/writing/finalization
        tasks.confirm_human(run_id, titles[0])

        run, node_status = _run_state(run_id)
        assert run["status"] == "succeeded", (run["status"], node_status)
        for key in ("blueprint_volume_plan", "blueprint_chapter_outline", "blueprint_scene_beat",
                    "write_chapter_draft", "write_self_review", "write_polish",
                    "write_length_check", "write_fact_reconcile",
                    "final_consistency_check", "final_continuity_audit", "final_humanize"):
            assert node_status[key] == "succeeded", (key, node_status[key])
    finally:
        tasks.execute_bootstrap.delay = original_delay  # type: ignore[assignment]

    db = connect()
    # Novel got the confirmed title
    novel = db.execute("SELECT title FROM contents WHERE id=%s", (novel_id,)).fetchone()
    assert novel["title"] == titles[0]
    # A real chapter row exists with narrative body
    chapter = db.execute(
        "SELECT * FROM contents WHERE parent_id=%s AND type='chapter' AND is_deleted=FALSE",
        (novel_id,),
    ).fetchone()
    assert chapter is not None
    assert len(str(chapter["body"])) > 200
    # Worldview + characters landed in the knowledge hub
    kinds = [r["kind"] for r in db.execute(
        "SELECT kind FROM knowledge_items WHERE content_id=%s AND is_deleted=FALSE", (novel_id,)
    ).fetchall()]
    assert "worldview" in kinds and "character" in kinds
    # Event ledger (denova, mapped onto audit_logs) recorded the run lifecycle
    events = [r["action"] for r in db.execute(
        "SELECT action FROM audit_logs WHERE entity_type='workflow_run' AND entity_id=%s ORDER BY created_at",
        (run_id,),
    ).fetchall()]
    assert "run.started" in events and "run.completed" in events, events
    db.close()


def test_journey_a_resumes_after_provider_failure(seeded_novel, monkeypatch):
    """Checkpoint contract: a provider failure marks pending_provider, and a
    redrive resumes from the failed node instead of restarting or crashing
    (the P0 ledger-poisoning regression fixed on 2026-07-13)."""
    from app import gateway
    from app.workers import tasks

    project_id, novel_id = seeded_novel

    fail_on = {"plan_story_pattern"}
    real_complete = tasks.complete

    def flaky_complete(**kwargs):
        if kwargs.get("task_type") in fail_on:
            raise gateway.ProviderError("simulated provider outage")
        return real_complete(**kwargs)

    monkeypatch.setattr(tasks, "complete", flaky_complete)

    def sync_dispatch(rid, start_key, api_key="", api_url="", model=""):
        tasks.execute_bootstrap.run(rid, start_key, api_key, api_url, model)

    original_delay = tasks.execute_bootstrap.delay
    tasks.execute_bootstrap.delay = sync_dispatch  # type: ignore[assignment]
    try:
        run_id = tasks.create_run(project_id, novel_id)
        run, node_status = _run_state(run_id)
        assert node_status["plan_story_pattern"] == "pending_provider"
        assert node_status["plan_idea"] == "succeeded"

        # Provider recovers; redrive from the failed node
        fail_on.clear()
        tasks.execute_bootstrap.run(run_id, "plan_story_pattern")
        run, node_status = _run_state(run_id)
        assert run["status"] == "waiting_human"
        assert node_status["plan_story_pattern"] == "succeeded"
    finally:
        tasks.execute_bootstrap.delay = original_delay  # type: ignore[assignment]
