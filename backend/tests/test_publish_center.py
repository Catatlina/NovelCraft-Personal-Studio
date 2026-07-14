"""发布中心推进到待验收：状态机行为、全自动调度、数据回流 sweep。

真实平台发布回执需有效平台凭据，属验收证据（配置就绪状态见《23》§5）；
此处以真库钉住状态机、调度与回流协议。
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _auth_project():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"pub-{uuid.uuid4().hex[:8]}@nc.dev"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    return client, headers, project_id


def _make_content(project_id: str, title: str = "待发布文章") -> str:
    from app.db import connect, encode, new_id

    cid = new_id()
    db = connect()
    db.execute(
        "INSERT INTO contents (id,project_id,type,title,body,meta,status) VALUES (%s,%s,'social_post',%s,%s,%s,'draft')",
        (cid, project_id, title,
         encode({"type": "doc", "content": [{"type": "paragraph", "text": "正文内容"}]}), encode({})),
    )
    db.commit(); db.close()
    return cid


def test_publish_state_machine_full_lifecycle_and_invalid_transitions():
    from app.services.publish_hub import publish_state_machine

    _, _, project_id = _auth_project()
    content_id = _make_content(project_id)

    # First state must be draft
    premature = publish_state_machine(content_id, "wechat", "published")
    assert premature["status"] == "error" and "draft" in premature["message"]

    for state in ("draft", "scheduled", "submitted", "published"):
        result = publish_state_machine(content_id, "wechat", state)
        assert result["status"] == "ok", f"{state}: {result}"
    assert result["from"] == "submitted" and result["to"] == "published"

    # published → submitted is invalid
    invalid = publish_state_machine(content_id, "wechat", "submitted")
    assert invalid["status"] == "error" and "invalid transition" in invalid["message"]

    # published → retracted → draft is the sanctioned recovery loop
    assert publish_state_machine(content_id, "wechat", "retracted")["status"] == "ok"
    assert publish_state_machine(content_id, "wechat", "draft")["status"] == "ok"

    bogus = publish_state_machine("not-a-uuid", "wechat", "draft")
    assert bogus["status"] == "error"


def test_check_scheduled_publishes_dispatches_due_records(monkeypatch):
    from datetime import datetime, timedelta, timezone

    from app.db import connect, encode, new_id
    from app.workers import m4_tasks

    _, _, project_id = _auth_project()
    content_id = _make_content(project_id)

    record_id = new_id()
    db = connect()
    db.execute(
        "INSERT INTO publish_records (id, content_id, platform, status, scheduled_at, meta) VALUES (%s,%s,%s,'scheduled',%s,%s)",
        (record_id, content_id, "wordpress",
         # Earliest due record so the LIMIT-10 sweep is guaranteed to pick it up
         # even when older test runs left scheduled rows behind.
         datetime.now(timezone.utc) - timedelta(days=3650), encode({})),
    )
    db.commit(); db.close()

    dispatched = []

    class _FakeAsync:
        id = "fake-task-id"

    monkeypatch.setattr(m4_tasks.auto_publish_article, "delay",
                        lambda *args: dispatched.append(args) or _FakeAsync())
    summary = m4_tasks.check_scheduled_publishes.run()
    assert summary["status"] == "ok"
    assert summary["dispatched"] >= 1
    assert any(args[3] == record_id for args in dispatched)

    db = connect()
    row = db.execute("SELECT status, meta FROM publish_records WHERE id=%s", (record_id,)).fetchone()
    db.close()
    assert row["status"] == "submitted"
    assert row["meta"]["celery_task_id"] == "fake-task-id"


def test_metrics_backflow_sweep_aggregates_collected_platform_data():
    from app.db import connect, encode, new_id
    from app.services.publish_hub import collect_platform_data
    from app.workers import m4_tasks

    _, _, project_id = _auth_project()
    content_id = _make_content(project_id)
    platform = f"wp-{uuid.uuid4().hex[:6]}"  # isolate from other rows

    db = connect()
    db.execute(
        "INSERT INTO publish_records (id, content_id, platform, status, result, meta) VALUES (%s,%s,%s,'published',%s,%s)",
        (new_id(), content_id, platform, encode({}), encode({})),
    )
    db.commit(); db.close()

    # Real backflow input: engagement data recorded for the published post
    collect_platform_data(platform, content_id,
                          {"project_id": project_id, "reads": 120, "likes": 15, "shares": 4, "revenue": 3.5})

    summary = m4_tasks.collect_publish_metrics_sweep.run()
    assert summary["status"] == "ok"
    assert summary["refreshed"] >= 1
    assert not summary["failures"]

    db = connect()
    row = db.execute(
        "SELECT result FROM publish_records WHERE content_id=%s AND platform=%s ORDER BY created_at DESC LIMIT 1",
        (content_id, platform),
    ).fetchone()
    db.close()
    assert row["result"]["reads"] == 120
    assert row["result"]["likes"] == 15
    assert row["result"]["last_checked"]


def test_beat_schedule_covers_publish_automation():
    from app.workers.celery_app import celery_app

    beat = celery_app.conf.beat_schedule
    assert beat["process-scheduled-publishes"]["task"] == "app.workers.m4_tasks.check_scheduled_publishes"
    assert beat["process-scheduled-publishes"]["schedule"] <= 300
    assert beat["collect-publish-metrics"]["task"] == "app.workers.m4_tasks.collect_publish_metrics_sweep"
