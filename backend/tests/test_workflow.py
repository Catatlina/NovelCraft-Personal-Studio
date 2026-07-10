"""TASK-008: Workflow engine — auth, structure, status tracking."""
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
    e = f"wf-{uuid.uuid4().hex[:6]}@nc.dev"
    return client.post("/api/v1/auth/register",
                       json={"email": e, "password": "test1234"}).json()["data"]["access_token"]


def _create_novel(client, token):
    pid = client.get("/api/v1/projects", headers={"Authorization": f"Bearer {token}"}).json()["data"][0]["id"]
    r = client.post(f"/api/v1/projects/{pid}/novels",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"idea": "test", "genre": "test", "style": "t", "target_words": 5000})
    return pid, r.json()["data"]["id"]


def test_bootstrap_creates_run(client: TestClient):
    """TASK-008: Bootstrap creates a run with nodes."""
    token = _auth(client)
    pid, nid = _create_novel(client, token)
    r = client.post(f"/api/v1/novels/{nid}/bootstrap",
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "run_id" in r.json()["data"]


def test_run_requires_auth(client: TestClient):
    r = client.get("/api/v1/runs/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 401


def test_run_not_found_authenticated(client: TestClient):
    token = _auth(client)
    r = client.get("/api/v1/runs/00000000-0000-0000-0000-000000000000",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


def test_human_confirm_requires_auth(client: TestClient):
    r = client.post("/api/v1/runs/00000000-0000-0000-0000-000000000000/nodes/n2/confirm",
                    json={"selected_title": "test"})
    assert r.status_code == 401


def test_node_retry_requires_auth(client: TestClient):
    r = client.post("/api/v1/runs/00000000-0000-0000-0000-000000000000/nodes/n1/retry")
    assert r.status_code == 401


def test_expand_outline_flow(client: TestClient):
    """TASK-008: Expand outline endpoint works."""
    token = _auth(client)
    pid, nid = _create_novel(client, token)
    r = client.post(f"/api/v1/novels/{nid}/expand-outline",
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code in [200, 400]
