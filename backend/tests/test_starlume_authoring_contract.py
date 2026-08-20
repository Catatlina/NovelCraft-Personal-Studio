"""M1-M7 contract tests for the Starlume human-led authoring control plane."""
from __future__ import annotations

import pytest


def test_authoring_routes_are_registered():
    from app.main import app

    paths = set(app.openapi()["paths"])
    assert "/api/v1/authoring/sessions" in paths
    assert "/api/v1/authoring/sessions/current" in paths
    assert "/api/v1/authoring/context/{content_id}" in paths
    assert "/api/v1/authoring/story-bible/{item_id}/impact" in paths
    assert "/api/v1/authoring/provider-roles" in paths
    assert "/api/v1/authoring/writing-events" in paths
    assert "/api/v1/authoring/runs/{run_id}/clean" in paths
    assert "/api/v1/authoring/publication-variants/{variant_id}/human-receipt" in paths


def test_role_provider_status_never_claims_unconfigured_provider(monkeypatch):
    from app.api.v1.authoring import _provider_status

    monkeypatch.delenv("DOUBAO_API_KEY", raising=False)
    status = _provider_status("doubao")
    assert status["implemented"] is True
    assert status["key_configured"] is False
    assert status["status"] == "needs_key"


def test_doubao_adapter_fails_closed_without_real_credentials(monkeypatch):
    from app.ai.providers import call_doubao

    monkeypatch.delenv("DOUBAO_API_KEY", raising=False)
    monkeypatch.delenv("DOUBAO_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="DOUBAO_API_KEY"):
        call_doubao("{}")


def test_editor_role_key_is_bounded():
    from app.schemas import AiEditRequest

    assert AiEditRequest(selection="当前正文", role_key="scene_expander").role_key == "scene_expander"
    with pytest.raises(ValueError):
        AiEditRequest(selection="当前正文", role_key="fake_writer")


def test_context_body_extraction_is_lossless_for_tiptap_shape():
    from app.api.v1.authoring import _text_from_body

    assert _text_from_body({"type": "doc", "content": [{"type": "paragraph", "text": "第一段"}, {"text": "第二段"}]}) == "第一段\n\n第二段"
    assert _text_from_body("人工正文") == "人工正文"
