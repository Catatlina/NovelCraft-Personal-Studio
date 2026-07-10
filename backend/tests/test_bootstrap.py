"""Smoke tests for core bootstrap flow."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ["NOVELCRAFT_ENV"] = "dev"
os.environ["DEEPSEEK_API_KEY"] = ""

from app.main import app


@pytest.fixture
def client():
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
