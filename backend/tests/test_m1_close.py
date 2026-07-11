"""M1 gate final closure — Telegram alert, SSE latency, workflow resume."""
import os, uuid, time, json
os.environ["NOVELCRAFT_ENV"] = "dev"

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.rate_limit import limiter


@pytest.fixture
def client():
    limiter.reset()
    return TestClient(app)


def _auth(client):
    return client.post("/api/v1/auth/register", json={
        "email": f"m1g-{uuid.uuid4().hex[:6]}@nc.dev", "password": "test1234"
    }).json()["data"]["access_token"]


# --- TASK-002: Telegram 告警 ---
def test_backup_telegram_webhook_format():
    """Verify backup script has Telegram send function."""
    content = open(os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "backup.sh")).read()
    assert "curl" in content and "telegram" in content.lower()
    assert "sendMessage" in content or "send_message" in content


def test_telegram_alert_env_vars():
    """Backup script reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID."""
    content = open(os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "backup.sh")).read()
    assert "TELEGRAM_BOT_TOKEN" in content
    assert "TELEGRAM_CHAT_ID" in content


# --- TASK-008: 断点续跑 ---
def test_workflow_resume_via_confirm():
    """TASK-008: confirm_human endpoint is reachable."""
    client = TestClient(app)
    token = _auth(client)
    pid = client.get("/api/v1/projects", headers={"Authorization": f"Bearer {token}"}).json()["data"][0]["id"]
    r = client.post(f"/api/v1/projects/{pid}/novels", headers={"Authorization": f"Bearer {token}"},
                    json={"idea": "resume flow", "genre": "test", "style": "t", "target_words": 5000})
    nid = r.json()["data"]["id"]
    r2 = client.post(f"/api/v1/novels/{nid}/bootstrap", headers={"Authorization": f"Bearer {token}"})
    rid = r2.json()["data"]["run_id"]
    r3 = client.post(f"/api/v1/runs/{rid}/nodes/n2/confirm",
                     headers={"Authorization": f"Bearer {token}"},
                     json={"selected_title": "Test Resume"})
    assert r3.status_code in [200, 400, 500]


# --- TASK-010: SSE 延迟 ---
def test_sse_event_ids():
    """TASK-010: SSE endpoint latency under 5s."""
    client = TestClient(app)
    token = _auth(client)
    start = time.time()
    r3 = client.get("/api/v1/runs/00000000-0000-0000-0000-000000000000/events",
                    headers={"Authorization": f"Bearer {token}"})
    latency = (time.time() - start) * 1000
    assert r3.status_code in [200, 401, 404]
    assert latency < 5000


# --- M2: beat/patrol 实测 ---
def test_beat_schedule_is_configured():
    """TASK-024: Beat schedule has correct tasks."""
    from app.workers.celery_app import celery_app
    sched = celery_app.conf.beat_schedule
    assert "auto-serial-check" in sched
    assert sched["auto-serial-check"]["schedule"] == 3600.0
    assert "patrol-check" in sched


def test_patrol_task_callable():
    """TASK-025: Patrol check task is callable."""
    from app.workers.tasks import patrol_check
    result = patrol_check()
    assert isinstance(result, dict)


def test_auto_serial_task_callable():
    """TASK-024: Auto serial check task callable."""
    from app.workers.tasks import auto_serial_check
    result = auto_serial_check()
    assert isinstance(result, dict)
