"""Regression tests for the production defects fixed on 2026-08-09."""

import pytest
from fastapi import HTTPException


def test_production_admin_allowlist_fails_closed(monkeypatch):
    import app.api.v1.config as config

    original_environment = config.settings.environment
    object.__setattr__(config.settings, "environment", "production")
    monkeypatch.delenv("NOVELCRAFT_ADMIN_EMAILS", raising=False)
    try:
        with pytest.raises(HTTPException) as exc_info:
            config.require_admin({"email": "user@example.com"})
        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["code"] == "ADMIN_NOT_CONFIGURED"
    finally:
        object.__setattr__(config.settings, "environment", original_environment)


def test_byok_storage_failure_is_not_a_server_key_fallback(monkeypatch):
    import app.core.byok as byok

    class BrokenRedis:
        def set(self, *_args, **_kwargs):
            raise ConnectionError("redis unavailable")

    monkeypatch.setattr(byok, "_redis", BrokenRedis())
    with pytest.raises(byok.BYOKUnavailableError):
        byok.stash_byok_key("sk-user-key")


def test_byok_expired_reference_is_not_resolved_as_empty_server_key(monkeypatch):
    import app.core.byok as byok

    class EmptyRedis:
        def get(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(byok, "_redis", EmptyRedis())
    with pytest.raises(byok.BYOKUnavailableError):
        byok.resolve_byok_key("expired-ref")


def test_engine_chat_requires_project_scope_and_branch_routes_are_not_doubled():
    from app.engine.router import ChatRequest
    from app.v7.api.branch_generator import router

    with pytest.raises(Exception):
        ChatRequest(messages=[{"role": "user", "content": "hello"}])
    paths = {route.path for route in router.routes}
    assert "/generate" in paths
    assert "/branches/generate" not in paths
    assert not hasattr(__import__("app.v7.api.branch_generator", fromlist=["x"]), "_branch_store")


def test_branch_apply_requires_exact_source_and_preserves_editor_conflict_safety():
    from app.v7.api.branch_generator import _apply_branch_text, _tiptap_body

    assert _apply_branch_text("前文原句后文", "原句", 2, 4, "替换", "replace") == "前文替换后文"
    assert _apply_branch_text("前文原句后文", "原句", 2, 4, "新增", "insert_after") == "前文原句\n\n新增后文"
    assert _tiptap_body("第一段\n\n第二段")["content"][1]["text"] == "第二段"
    with pytest.raises(HTTPException) as exc_info:
        _apply_branch_text("前文已变后文", "原句", 2, 4, "替换", "replace")
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "BRANCH_SOURCE_CONFLICT"


def test_reader_simulation_uses_real_gateway_and_never_returns_example_result(monkeypatch):
    import app.v7.quality.reader_simulation as reader

    provider_payload = {
        "opening_hook_score": 8,
        "opening_hook_comment": "开头直接抛出冲突",
        "continuation_intent_score": 9,
        "continuation_intent_comment": "章末留下明确追读问题",
        "empathy_moments": [],
        "empathy_score": 5,
        "ai_smell_sections": [],
        "ai_smell_severity": "无",
        "top_suggestion": "把第一处反击再提前半段",
        "suggestion_priority": "中",
        "overall_score": 86,
        "overall_comment": "冲突和追读钩子都成立",
    }
    calls = []

    def fake_complete(**kwargs):
        calls.append(kwargs)
        return provider_payload

    monkeypatch.setattr(reader, "complete", fake_complete)
    result = reader.simulate_reader_first_pass(
        "主角推门而入，发现对手已经等在里面。",
        project_id="project-1",
    )
    assert calls and calls[0]["task_type"] == "reader_simulation"
    assert result["result"]["overall_score"] == 86
    assert "note" not in result
    with pytest.raises(reader.ReaderSimulationError):
        reader.simulate_reader_first_pass("正文", project_id=None)


def test_module_toggle_persists_state_without_process_only_success(monkeypatch):
    import json
    import app.platform.modules.manager as manager

    class FakeResult:
        def __init__(self, rows):
            self.rows = rows

        def fetchall(self):
            return self.rows

    class FakeDb:
        def __init__(self):
            self.state = {}

        def execute(self, sql, params=()):
            if sql.lstrip().startswith("SELECT key, value"):
                return FakeResult([{"key": key, "value": value} for key, value in self.state.items()])
            self.state[params[0]] = params[1]
            return FakeResult([])

        def commit(self):
            return None

        def close(self):
            return None

    db = FakeDb()
    monkeypatch.setattr(manager, "connect", lambda: db)
    module = manager.MODULES["novel-editor"]
    original_enabled = module.enabled
    try:
        assert manager.toggle_module("novel-editor", False) is True
        persisted = json.loads(db.state["module_state:novel-editor"])
        assert persisted == {"enabled": False, "installed": True}
        listed = manager.get_all_modules()
        editor = next(item for item in listed["novel"] if item.id == "novel-editor")
        assert editor.enabled is False
    finally:
        module.enabled = original_enabled
