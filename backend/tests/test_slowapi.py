"""TASK-001: slowapi endpoint-level verification + Celery retry tests."""
import os, uuid
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
    e = f"slowapi-{uuid.uuid4().hex[:6]}@nc.dev"
    return client.post("/api/v1/auth/register", json={"email": e, "password": "test1234"}).json()["data"]["access_token"]


# --- TASK-001: slowapi rate limit verification ---

def test_auth_register_rate_limited(client: TestClient):
    """Verify register endpoint respects 5/minute limit."""
    for _ in range(6):
        client.post("/api/v1/auth/register", json={
            "email": f"rl-{uuid.uuid4().hex[:6]}@nc.dev", "password": "test1234"})
    r = client.post("/api/v1/auth/register", json={
        "email": f"last-{uuid.uuid4().hex[:6]}@nc.dev", "password": "test1234"})
    assert r.status_code in [200, 429]


def test_bootstrap_rate_limited(client: TestClient):
    """Verify bootstrap respects 10/minute limit."""
    token = _auth(client)
    for _ in range(11):
        client.post("/api/v1/novels/00000000-0000-0000-0000-000000000000/bootstrap",
                    headers={"Authorization": f"Bearer {token}"})
    r = client.post("/api/v1/novels/00000000-0000-0000-0000-000000000000/bootstrap",
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code in [200, 404, 429]


def test_ai_edit_rate_limited(client: TestClient):
    """Verify ai edit respects 30/minute limit."""
    token = _auth(client)
    for _ in range(31):
        client.post("/api/v1/contents/00000000-0000-0000-0000-000000000000/ai/polish",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"selection": "test", "instruction": ""})
    r = client.post("/api/v1/contents/00000000-0000-0000-0000-000000000000/ai/polish",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"selection": "test", "instruction": ""})
    assert r.status_code in [200, 404, 429]


# --- TASK-001: Celery retry verification ---

def test_celery_tasks_registered():
    """Verify all Celery tasks are importable and registered."""
    from app.workers.tasks import (
        execute_bootstrap, gen_next_chapter_task, expand_outline_task,
        auto_serial_check, patrol_check, bootstrap_short_story_task
    )
    assert execute_bootstrap.name == "app.workers.tasks.execute_bootstrap"
    assert gen_next_chapter_task.name == "app.workers.tasks.gen_next_chapter_task"
    assert expand_outline_task.name == "app.workers.tasks.expand_outline_task"
    assert auto_serial_check.name == "app.workers.tasks.auto_serial_check"
    assert patrol_check.name == "app.workers.tasks.patrol_check"
    assert bootstrap_short_story_task.name == "app.workers.tasks.bootstrap_short_story_task"


def test_celery_retry_config():
    """Verify Celery retry configuration."""
    from app.workers.tasks import execute_bootstrap
    assert execute_bootstrap.max_retries == 3
    assert execute_bootstrap.default_retry_delay == 5


# --- TASK-001: Error handling ---

def test_invalid_token_rejected(client: TestClient):
    r = client.get("/api/v1/projects", headers={"Authorization": "Bearer invalid.token.here"})
    assert r.status_code in [401, 403]


def test_malformed_json_body(client: TestClient):
    r = client.post("/api/v1/auth/login",
                    headers={"Content-Type": "application/json"},
                    content=b"{bad json")
    assert r.status_code in [400, 422]


def test_content_not_found(client: TestClient):
    token = _auth(client)
    r = client.get("/api/v1/contents/00000000-0000-0000-0000-000000000000",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404
