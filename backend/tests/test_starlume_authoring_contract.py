"""M1-M7 contract tests for the Starlume human-led authoring control plane."""
from __future__ import annotations

import pytest


def test_authoring_routes_are_registered():
    from app.main import app

    paths = set(app.openapi()["paths"])
    assert "/api/v1/authoring/sessions" in paths
    assert "/api/v1/authoring/sessions/current" in paths
    assert "/api/v1/authoring/context/{content_id}" in paths
    assert "/api/v1/authoring/chapters/{chapter_id}/skeleton" in paths
    assert "/api/v1/authoring/chapters/{chapter_id}/skeletons" in paths
    assert "/api/v1/authoring/chapters/{chapter_id}/skeletons/save" in paths
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


def test_chapter_skeleton_is_structured_and_not_final_prose():
    from app.gateway import validate_task_output
    from app.api.v1.authoring import _skeleton_char_count

    skeleton_text = "骨架节点。" * 140
    assert 700 <= _skeleton_char_count(skeleton_text) <= 1000
    output = validate_task_output("chapter_skeleton", {
        "title": "门后的账本",
        "chapter_goal": "主角拿到关键账本",
        "current_state": "主角被堵在旧仓库",
        "main_conflict": "取证和暴露身份只能选一个",
        "scenes": [
            {"title": "入口", "purpose": "建立压力", "action": "试探", "conflict": "被监视", "outcome": "发现暗门", "characters": ["主角"]},
            {"title": "暗门", "purpose": "推进线索", "action": "取证", "conflict": "证据不完整", "outcome": "留下代价", "characters": ["主角"]},
            {"title": "反咬", "purpose": "形成结果", "action": "选择", "conflict": "身份将暴露", "outcome": "反派先一步认出他", "characters": ["主角", "反派"]},
        ],
        "character_moves": ["主角从试探转为主动承担风险"],
        "mainline_progress": "取得账本并暴露下一层对手",
        "payoff": "主角拿到可验证证据",
        "foreshadowing": ["账本缺少最后一页"],
        "continuity_warnings": [],
        "next_hook": "反派用最后一页反过来设局",
        "skeleton_text": skeleton_text,
    })
    assert output["skeleton_text"] == skeleton_text
