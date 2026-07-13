"""Authenticated password change (closes the R03 gap): verifies the old password,
rejects no-op changes, rotates token_version so old tokens die, and keeps the
current session working with freshly issued tokens."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


def _csrf(client) -> str:
    return client.cookies.get("csrf_token", "")


@pytest.fixture
def ctx():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"pw-{uuid.uuid4().hex[:8]}@nc.dev"
    reg = client.post("/api/v1/auth/register", json={"email": email, "password": "oldpass12"}).json()
    token = reg["data"]["access_token"]
    # /api/v1/auth is CSRF-protected once the refresh cookie is set (double-submit).
    headers = {"Authorization": f"Bearer {token}", "X-CSRF-Token": _csrf(client)}
    return client, email, headers


def test_change_password_happy_path_and_old_token_revoked(ctx):
    client, email, headers = ctx
    resp = client.post("/api/v1/auth/change-password",
                       json={"old_password": "oldpass12", "new_password": "newpass34"},
                       headers=headers)
    assert resp.status_code == 200
    new_token = resp.json()["data"]["access_token"]

    # Old access token is now invalid (token_version bumped).
    assert client.get("/api/v1/auth/me", headers={"Authorization": headers["Authorization"]}).status_code == 401
    # New token works.
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_token}"}).status_code == 200
    # New password logs in; old one does not.
    assert client.post("/api/v1/auth/login", json={"email": email, "password": "newpass34"}).status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": email, "password": "oldpass12"}).status_code == 401


def test_change_password_wrong_old_is_rejected(ctx):
    client, _email, headers = ctx
    resp = client.post("/api/v1/auth/change-password",
                       json={"old_password": "WRONGpass", "new_password": "newpass34"},
                       headers=headers)
    assert resp.status_code == 401


def test_change_password_same_password_rejected(ctx):
    client, _email, headers = ctx
    resp = client.post("/api/v1/auth/change-password",
                       json={"old_password": "oldpass12", "new_password": "oldpass12"},
                       headers=headers)
    assert resp.status_code == 400


def test_change_password_requires_auth(ctx):
    client, _email, headers = ctx
    # Valid CSRF but no bearer token -> auth layer rejects with 401.
    resp = client.post("/api/v1/auth/change-password",
                       json={"old_password": "oldpass12", "new_password": "newpass34"},
                       headers={"X-CSRF-Token": headers["X-CSRF-Token"]})
    assert resp.status_code == 401
