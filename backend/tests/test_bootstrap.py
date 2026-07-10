"""Smoke tests for core bootstrap flow."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ["NOVELCRAFT_ENV"] = "dev"
os.environ["DEEPSEEK_API_KEY"] = ""

from app.main import app
from app.core.rate_limit import limiter


@pytest.fixture
def client():
    limiter.reset()
    return TestClient(app)


def test_healthz(client: TestClient):
    r = client.get("/api/v1/healthz")
    assert r.status_code == 200
    data = r.json()
    assert data["data"]["status"] == "ok"


def test_auth_register(client: TestClient):
    import uuid
    email = f"test-{uuid.uuid4().hex[:8]}@novelcraft.local"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data["data"]


def test_auth_login(client: TestClient):
    import uuid
    email = f"test-{uuid.uuid4().hex[:8]}@novelcraft.local"
    client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"})
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "test1234"})
    assert r.status_code == 200
    assert "access_token" in r.json()["data"]


def test_auth_register_is_rate_limited(client: TestClient):
    import uuid
    statuses = []
    for idx in range(6):
        email = f"limited-{uuid.uuid4().hex[:8]}-{idx}@novelcraft.local"
        response = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"})
        statuses.append(response.status_code)
    assert statuses[-1] == 429


def test_projects_require_auth(client: TestClient):
    r = client.get("/api/v1/projects")
    assert r.status_code == 401  # Unauthorized without token


def test_projects_with_token(client: TestClient):
    import uuid
    email = f"test-{uuid.uuid4().hex[:8]}@novelcraft.local"
    client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"})
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "test1234"})
    token = login.json()["data"]["access_token"]
    r = client.get("/api/v1/projects", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_admin_routes_require_auth(client: TestClient):
    assert client.get("/api/v1/admin/providers").status_code == 401
    token, _project_id = _register_user(client, "admin-smoke")
    response = client.get("/api/v1/admin/providers", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def _register_user(client: TestClient, prefix: str):
    import uuid
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@novelcraft.local"
    response = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"})
    assert response.status_code == 200
    data = response.json()["data"]
    token = data["access_token"]
    projects = client.get("/api/v1/projects", headers={"Authorization": f"Bearer {token}"}).json()["data"]
    return token, projects[0]["id"]


def _create_novel(client: TestClient, token: str, project_id: str):
    response = client.post(
        f"/api/v1/projects/{project_id}/novels",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "idea": "一个写作者发现被删除的章节正在现实里发生。",
            "genre": "都市奇幻",
            "style": "克制悬疑",
            "target_words": 800000,
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["id"]


def test_content_object_endpoints_require_auth(client: TestClient):
    token, project_id = _register_user(client, "owner")
    novel_id = _create_novel(client, token, project_id)

    assert client.get(f"/api/v1/contents/{novel_id}").status_code == 401
    assert client.put(f"/api/v1/contents/{novel_id}", json={"title": "x"}).status_code == 401
    assert client.post(f"/api/v1/novels/{novel_id}/bootstrap").status_code == 401


def test_content_object_endpoints_block_cross_project_access(client: TestClient):
    owner_token, owner_project_id = _register_user(client, "owner")
    other_token, _other_project_id = _register_user(client, "other")
    novel_id = _create_novel(client, owner_token, owner_project_id)

    headers = {"Authorization": f"Bearer {other_token}"}
    assert client.get(f"/api/v1/contents/{novel_id}", headers=headers).status_code == 403
    assert client.put(f"/api/v1/contents/{novel_id}", headers=headers, json={"title": "x"}).status_code == 403
    assert client.post(f"/api/v1/novels/{novel_id}/bootstrap", headers=headers).status_code == 403
