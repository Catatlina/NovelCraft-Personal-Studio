"""TASK-047: Collaboration permission — cross-user access tests."""
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


def _register(client, name):
    return client.post("/api/v1/auth/register", json={
        "email": f"collab-{name}-{uuid.uuid4().hex[:4]}@nc.dev",
        "password": "test1234"
    }).json()["data"]["access_token"]


def _create_novel(client, token):
    pid = client.get("/api/v1/projects", headers={"Authorization": f"Bearer {token}"}).json()["data"][0]["id"]
    r = client.post(f"/api/v1/projects/{pid}/novels",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"idea": "test", "genre": "test", "style": "t", "target_words": 5000})
    return pid, r.json()["data"]["id"]


def test_cross_user_content_blocked(client: TestClient):
    """TASK-047: User A's content is blocked for User B."""
    token_a = _register(client, "owner")
    token_b = _register(client, "intruder")
    _, nid = _create_novel(client, token_a)

    # User B tries to access User A's novel
    r = client.get(f"/api/v1/contents/{nid}",
                   headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code in [403, 404]  # Should be blocked (403 or 404)


def test_cross_user_edit_blocked(client: TestClient):
    """TASK-047: User B cannot edit User A's content."""
    token_a = _register(client, "editor")
    token_b = _register(client, "other")
    _, nid = _create_novel(client, token_a)

    r = client.put(f"/api/v1/contents/{nid}",
                   headers={"Authorization": f"Bearer {token_b}"},
                   json={"title": "hacked"})
    assert r.status_code in [403, 404]


def test_cross_user_bootstrap_blocked(client: TestClient):
    """TASK-047: User B cannot bootstrap User A's novel."""
    token_a = _register(client, "boot")
    token_b = _register(client, "evil")
    _, nid = _create_novel(client, token_a)

    r = client.post(f"/api/v1/novels/{nid}/bootstrap",
                    headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code in [403, 404]
