"""Real-provider E2E smoke for the V2 four-stage bootstrap (audit fix item 5).

Runs Journey A against the real DeepSeek API: planning → human confirm →
blueprint → writing → finalization, and requires a real generated chapter.
Skipped without DEEPSEEK_API_KEY (CI provides it as a repo secret).

This is the "真实 provider 端到端冒烟测试（非 mock）" the 2026-07-13
acceptance audit required before the flagship flow may be called deliverable.
"""
import os

import pytest

from app.db import connect, encode, init_db, new_id

pytestmark = pytest.mark.skipif(
    not os.getenv("DEEPSEEK_API_KEY"),
    reason="real-provider V2 bootstrap smoke needs DEEPSEEK_API_KEY (repo secret / local env)",
)


@pytest.fixture()
def real_env(monkeypatch):
    # Leave the test sandbox: real provider, no mock permission.
    monkeypatch.setenv("NOVELCRAFT_ENV", "ci")
    monkeypatch.delenv("NOVELCRAFT_ALLOW_MOCK", raising=False)
    monkeypatch.delenv("ALLOW_MOCK", raising=False)


@pytest.fixture()
def seeded_novel():
    init_db()
    db = connect()
    user_id = new_id()
    db.execute(
        "INSERT INTO users (id, email, password_hash, display_name) VALUES (%s,%s,%s,%s)",
        (user_id, f"real-{user_id[:8]}@test.local", "x", "RealSmoke"),
    )
    project_id = new_id()
    db.execute("INSERT INTO projects (id, name, owner_id) VALUES (%s,%s,%s)",
               (project_id, "真实冒烟", user_id))
    db.execute(
        "INSERT INTO project_members (id, project_id, user_id, role) VALUES (%s,%s,%s,'owner')",
        (new_id(), project_id, user_id),
    )
    # Generous budget so the gate never masks a wiring failure.
    db.execute(
        "INSERT INTO budgets (id, project_id, scope, limit_cny, spent_cny) VALUES (%s,%s,'bootstrap',20.0,0) "
        "ON CONFLICT DO NOTHING",
        (new_id("bdg"), project_id),
    )
    novel_id = new_id()
    db.execute(
        "INSERT INTO contents (id, project_id, type, title, body, meta, status) "
        "VALUES (%s,%s,'novel','未命名',%s,%s,'draft')",
        (novel_id, project_id, encode({}),
         encode({"idea": "深夜电台主播收到一通来自三十年前的求救电话",
                 "genre": "悬疑", "style": "克制、有电影感"})),
    )
    db.commit()
    db.close()
    return project_id, novel_id


def test_real_v2_bootstrap_journey_a(real_env, seeded_novel):
    from app.workers import tasks

    project_id, novel_id = seeded_novel

    def sync_dispatch(rid, start_key, api_key="", api_url="", model=""):
        tasks.execute_bootstrap.run(rid, start_key, api_key, api_url, model)

    original_delay = tasks.execute_bootstrap.delay
    tasks.execute_bootstrap.delay = sync_dispatch  # type: ignore[assignment]
    try:
        run_id = tasks.create_run(project_id, novel_id)

        db = connect()
        run = db.execute("SELECT * FROM workflow_runs WHERE id=%s", (run_id,)).fetchone()
        db.close()
        assert run["status"] == "waiting_human", (run["status"], run.get("current_node_key"))
        titles = run["context"].get("title_candidates") or []
        assert len(titles) >= 3, "planning must yield real title candidates"

        tasks.confirm_human(run_id, titles[0])

        db = connect()
        run = db.execute("SELECT * FROM workflow_runs WHERE id=%s", (run_id,)).fetchone()
        nodes = {n["node_key"]: n["status"] for n in db.execute(
            "SELECT node_key, status FROM run_nodes WHERE run_id=%s", (run_id,)).fetchall()}
        chapter = db.execute(
            "SELECT * FROM contents WHERE parent_id=%s AND type='chapter' AND is_deleted=FALSE",
            (novel_id,),
        ).fetchone()
        calls = db.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(cost_cny),0) AS cost FROM ai_calls WHERE project_id=%s",
            (project_id,),
        ).fetchone()
        db.close()

        assert run["status"] in ("succeeded", "needs_review"), (run["status"], nodes)
        assert nodes["write_chapter_draft"] == "succeeded", nodes
        assert chapter is not None, "real provider must persist a chapter"
        body_text = str(chapter["body"])
        assert len(body_text) > 800, f"chapter too short to be real prose: {len(body_text)}"
        assert int(calls["n"]) >= 18, f"expected ≥18 real AI calls, saw {calls['n']}"
        print(f"[real V2 smoke] run={run_id} status={run['status']} "
              f"calls={calls['n']} cost_cny={float(calls['cost']):.4f} chapter_chars={len(body_text)}")
    finally:
        tasks.execute_bootstrap.delay = original_delay  # type: ignore[assignment]
