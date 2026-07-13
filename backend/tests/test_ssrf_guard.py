from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize("url", [
    "http://api.deepseek.com",
    "http://169.254.169.254/latest/meta-data",
    "https://127.0.0.1/v1",
    "https://localhost/v1",
    "https://api.deepseek.com:8443/v1",
    "https://user:pass@api.deepseek.com/v1",
    "https://api.deepseek.com/v1?key=secret",
])
def test_ai_base_url_rejects_ssrf_and_credential_shapes(url):
    from app.core.url_security import validate_ai_base_url

    with pytest.raises(ValueError):
        validate_ai_base_url(url)


def test_ai_base_url_accepts_known_and_explicit_hosts(monkeypatch):
    from app.core.url_security import validate_ai_base_url

    assert validate_ai_base_url("https://api.deepseek.com/v1/") == "https://api.deepseek.com/v1"
    monkeypatch.setenv("AI_API_BASE_HOST_ALLOWLIST", "llm.example.com")
    assert validate_ai_base_url("https://llm.example.com/v1") == "https://llm.example.com/v1"


def test_custom_base_url_requires_byok(client):
    response = client.get("/api/v1/healthz", headers={"X-Api-Base-Url": "https://api.deepseek.com"})
    assert response.status_code == 400


def test_custom_base_url_is_rejected_before_request(client):
    response = client.get(
        "/api/v1/healthz",
        headers={"X-Api-Key": "request-key", "X-Api-Base-Url": "http://169.254.169.254"},
    )
    assert response.status_code == 400
