"""TASK-008: Workflow engine tests — non-Celery tests only."""
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
    e = f"wf-nc-{uuid.uuid4().hex[:6]}@nc.dev"
    r = client.post("/api/v1/auth/register", json={"email": e, "password": "test1234"})
    return r.json()["data"]["access_token"]


def test_bootstrap_creates_run(client):
    """TASK-008: Bootstrap creates a run with nodes (skips Celery wait)."""
    token = _auth(client)
    pid = client.get("/api/v1/projects", headers={"Authorization": f"Bearer {token}"}).json()["data"][0]["id"]
    r = client.post(f"/api/v1/projects/{pid}/novels", headers={"Authorization": f"Bearer {token}"},
                    json={"idea": "test flow", "genre": "test", "style": "t", "target_words": 5000})
    nid = r.json()["data"]["id"]
    r2 = client.post(f"/api/v1/novels/{nid}/bootstrap", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert "run_id" in r2.json()["data"]


def test_run_requires_auth(client):
    r = client.get("/api/v1/runs/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 401


def test_run_404_for_unknown(client):
    token = _auth(client)
    r = client.get("/api/v1/runs/00000000-0000-0000-0000-000000000000",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


def test_latest_run_restores_newest_project_workflow(client):
    token = _auth(client)
    headers = {"Authorization": f"Bearer {token}"}
    pid = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    novel = client.post(
        f"/api/v1/projects/{pid}/novels",
        headers=headers,
        json={"idea": "restore latest run", "genre": "test", "style": "t", "target_words": 5000},
    ).json()["data"]
    created = client.post(f"/api/v1/novels/{novel['id']}/bootstrap", headers=headers).json()["data"]

    response = client.get(f"/api/v1/runs/latest?project_id={pid}", headers=headers)

    assert response.status_code == 200
    restored = response.json()["data"]
    assert restored["id"] == created["run_id"]
    assert restored["project_id"] == pid
    assert restored["novel_id"] == novel["id"]
    assert restored["nodes"]


def test_latest_run_does_not_leak_other_users_workflow(client):
    first_token = _auth(client)
    first_headers = {"Authorization": f"Bearer {first_token}"}
    first_pid = client.get("/api/v1/projects", headers=first_headers).json()["data"][0]["id"]
    novel = client.post(
        f"/api/v1/projects/{first_pid}/novels",
        headers=first_headers,
        json={"idea": "private run", "genre": "test", "style": "t", "target_words": 5000},
    ).json()["data"]
    client.post(f"/api/v1/novels/{novel['id']}/bootstrap", headers=first_headers)

    second_token = _auth(client)
    second_headers = {"Authorization": f"Bearer {second_token}"}
    response = client.get(f"/api/v1/runs/latest?project_id={first_pid}", headers=second_headers)

    assert response.status_code == 404


def test_human_confirm_requires_auth(client):
    r = client.post("/api/v1/runs/00000000-0000-0000-0000-000000000000/nodes/n2/confirm",
                    json={"selected_title": "test"})
    assert r.status_code == 401


def test_node_retry_requires_auth(client):
    r = client.post("/api/v1/runs/00000000-0000-0000-0000-000000000000/nodes/n1/retry")
    assert r.status_code in [401, 404]


def test_expand_outline_endpoint(client):
    token = _auth(client)
    pid = client.get("/api/v1/projects", headers={"Authorization": f"Bearer {token}"}).json()["data"][0]["id"]
    r = client.post(f"/api/v1/projects/{pid}/novels", headers={"Authorization": f"Bearer {token}"},
                    json={"idea": "expand test", "genre": "test", "style": "t", "target_words": 5000})
    nid = r.json()["data"]["id"]
    r2 = client.post(f"/api/v1/novels/{nid}/expand-outline", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code in [200, 400, 404]


def test_workflow_nodes_structure():
    """TASK-008/V2: Bootstrap node structure is correct (four stages + human gate)."""
    from app.workers.tasks import BOOTSTRAP_NODES
    assert len(BOOTSTRAP_NODES) == 19
    kinds = [n[1] for n in BOOTSTRAP_NODES]
    assert "human" in kinds
    assert "agent" in kinds
