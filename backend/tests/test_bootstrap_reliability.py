"""Reliability and truthfulness contracts for Bootstrap AI nodes (NC-SC-003)."""
from __future__ import annotations

import pytest


class _Cursor:
    def __init__(self, one=None):
        self.one = one

    def fetchone(self):
        return self.one


class _TaskDb:
    def __init__(self):
        self.statements = []

    def execute(self, sql, params=()):
        compact = " ".join(sql.split())
        self.statements.append((compact, params))
        if "SELECT * FROM run_nodes" in compact:
            return _Cursor({"status": "pending", "kind": "agent"})
        if "SELECT * FROM workflow_runs" in compact:
            return _Cursor({"id": "run-1", "project_id": "project-1", "novel_id": "novel-1", "context": {}})
        return _Cursor()

    def commit(self):
        pass

    def close(self):
        pass


@pytest.mark.parametrize(
    ("node_key", "task_type", "invalid_output"),
    [
        # V2 four-stage nodes: malformed output must never persist as success.
        ("plan_idea", "plan_idea", {}),
        ("plan_world_architecture", "plan_world_architecture", {"worldview": {}}),
        ("plan_character_system", "plan_character_system", {"characters": []}),
        ("blueprint_chapter_outline", "blueprint_chapter_outline", {"chapter_outlines": []}),
        ("write_chapter_draft", "write_chapter_draft", {"chapter": {"title": "", "body": []}}),
    ],
)
def test_invalid_or_empty_bootstrap_output_is_not_persisted_or_succeeded(
    monkeypatch, node_key, task_type, invalid_output
):
    from app.workers import tasks

    db = _TaskDb()
    monkeypatch.setattr(tasks, "connect", lambda: db)
    monkeypatch.setattr(tasks.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(tasks, "complete", lambda **_kwargs: invalid_output)
    # Stage enrichment reads real tables; irrelevant to this contract.
    monkeypatch.setattr(tasks, "_enrich_blueprint_context", lambda context, _novel_id: context)
    monkeypatch.setattr(tasks, "_enrich_finalization_context", lambda context, _novel_id: context)
    monkeypatch.setattr(tasks, "_write_before_search", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(tasks, "_create_checkpoint", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(
        tasks,
        "_persist_output",
        lambda *_args: pytest.fail("invalid output must not reach persistence"),
    )

    result = tasks.execute_bootstrap.run("run-1", node_key)

    assert result["status"] == "invalid_output"
    assert result["node_key"] == node_key
    assert any(params and params[0] == "failed" for sql, params in db.statements if sql.startswith("UPDATE"))
    assert not any(params and params[0] == "succeeded" for sql, params in db.statements if sql.startswith("UPDATE"))


def test_mock_route_is_rejected(monkeypatch):
    from app import gateway
    from app.gateway import ProviderError

    monkeypatch.setenv("NOVELCRAFT_ENV", "development")
    class Db:
        def execute(self, _sql, _params=()):
            return _Cursor()

        def close(self):
            pass

    monkeypatch.setattr(gateway, "connect", lambda: Db())
    monkeypatch.setattr(gateway, "_load_prompt_and_route", lambda *_args: ("prompt", "mock", "mock", {}))
    monkeypatch.setattr(gateway, "_assert_budget", lambda *_args: None)

    with pytest.raises(ProviderError, match="mock"):
        gateway.complete(
            run_id="run-1",
            node_key="n3",
            project_id="project-1",
            task_type="gen_synopsis",
            prompt_name="bootstrap.gen_synopsis",
            variables={},
            client_mutation_id="bootstrap:run-1:n3",
        )


def test_test_environment_still_rejects_mock_provider(monkeypatch):
    from app import gateway
    from app.gateway import ProviderError

    class Db:
        def __init__(self):
            self.statements = []

        def execute(self, sql, params=()):
            self.statements.append((" ".join(sql.split()), params))
            return _Cursor()

        def commit(self):
            pass

        def close(self):
            pass

    db = Db()
    monkeypatch.setenv("NOVELCRAFT_ENV", "test")
    monkeypatch.setattr(gateway, "connect", lambda: db)
    monkeypatch.setattr(gateway, "_load_prompt_and_route", lambda *_args: ("prompt", "mock", "mock", {}))
    monkeypatch.setattr(gateway, "_assert_budget", lambda *_args: None)

    with pytest.raises(ProviderError, match="unsupported real provider: mock"):
        gateway.complete(
            run_id="run-1", node_key="n3", project_id="project-1",
            task_type="gen_synopsis", prompt_name="bootstrap.gen_synopsis", variables={},
            client_mutation_id="bootstrap:run-1:n3",
        )


def test_bootstrap_complete_uses_stable_node_mutation_id(monkeypatch):
    from app.workers import tasks

    db = _TaskDb()
    calls = []
    monkeypatch.setattr(tasks, "connect", lambda: db)
    monkeypatch.setattr(tasks.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(tasks, "_create_checkpoint", lambda *_args, **_kwargs: "")

    def complete(**kwargs):
        calls.append(kwargs)
        return {"idea_expanded": "一位创作者发现自己写下的故事正在现实中逐字发生，必须找出幕后执笔者。",
                "core_hook": "你写的每一个字都在杀人",
                "target_audience": "18-35 岁悬疑读者",
                "title_candidates": ["《甲》", "《乙》", "《丙》"]}

    monkeypatch.setattr(tasks, "complete", complete)
    monkeypatch.setattr(tasks, "_persist_output", lambda *_args: None)
    # Stop after plan_idea: the next node lookup returns missing.
    original_execute = db.execute

    def execute(sql, params=()):
        if "SELECT * FROM run_nodes" in sql and params[1] != "plan_idea":
            return _Cursor(None)
        return original_execute(sql, params)

    db.execute = execute

    result = tasks.execute_bootstrap.run("run-1", "plan_idea")

    assert result["status"] == "error"
    assert calls[0]["client_mutation_id"] == "bootstrap:run-1:plan_idea:v2"


def test_gateway_replay_by_mutation_id_returns_existing_output_without_new_writes(monkeypatch):
    from app import gateway

    existing = {"synopsis": "已生成简介", "selling_points": ["卖点"]}

    class Db:
        def __init__(self):
            self.statements = []

        def execute(self, sql, params=()):
            compact = " ".join(sql.split())
            self.statements.append((compact, params))
            if compact.startswith("SELECT output FROM ai_calls"):
                return _Cursor({"output": existing})
            return _Cursor()

        def close(self):
            pass

    db = Db()
    monkeypatch.setattr(gateway, "connect", lambda: db)

    output = gateway.complete(
        run_id="run-1", node_key="n3", project_id="project-1",
        task_type="gen_synopsis", prompt_name="bootstrap.gen_synopsis", variables={},
        client_mutation_id="bootstrap:run-1:n3",
    )

    assert output == existing
    assert len(db.statements) == 1
    assert db.statements[0][0].startswith("SELECT output FROM ai_calls")


def test_bootstrap_task_clears_request_context_after_completion(monkeypatch):
    from app.gateway import _request_api_base_url, _request_api_key, _request_model
    from app.workers import tasks

    db = _TaskDb()
    # No run/node makes the task return immediately; cleanup must still happen in finally.
    db.execute = lambda *_args, **_kwargs: _Cursor(None)
    monkeypatch.setattr(tasks, "connect", lambda: db)

    tasks.execute_bootstrap.run("missing-run", "n3", "secret-key", "https://provider.test", "model-x")

    assert _request_api_key.get() is None
    assert _request_api_base_url.get() is None
    assert _request_model.get() is None
