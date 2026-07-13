"""BUG-006 regression: POST /projects must honor the request body's name/description,
while the legacy ?name= query form keeps working."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def ctx():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"proj-{uuid.uuid4().hex[:8]}@nc.dev"
    reg = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()
    token = reg["data"]["access_token"]
    csrf = client.cookies.get("csrf_token", "")
    return client, {"Authorization": f"Bearer {token}", "X-CSRF-Token": csrf}


def test_create_project_honors_body_name(ctx):
    client, headers = ctx
    r = client.post("/api/v1/projects", headers=headers,
                    json={"name": "QA_TEST_PROJECT", "description": "desc"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["name"] == "QA_TEST_PROJECT"
    assert data.get("description") == "desc"


def test_create_project_query_name_still_works(ctx):
    client, headers = ctx
    r = client.post("/api/v1/projects?name=via_query", headers=headers)
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "via_query"


def test_create_project_defaults_when_nothing_given(ctx):
    client, headers = ctx
    r = client.post("/api/v1/projects", headers=headers)
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "新项目"
