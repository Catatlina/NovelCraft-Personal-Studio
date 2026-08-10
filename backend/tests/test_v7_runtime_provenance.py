from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from app.services.ai_runtime import execution_key, prompt_hash
from app.v7.generation.generation_engine import AIGateway
from app.v7.prompt.prompt_manager import PromptVersionManager


def test_shared_execution_key_is_stable_and_attempts_are_distinct():
    first = execution_key("v7", scope="novel-1", client_mutation_id="run-1", attempt=1)
    replay = execution_key("v7", scope="novel-1", client_mutation_id="run-1", attempt=1)
    second = execution_key("v7", scope="novel-1", client_mutation_id="run-1", attempt=2)

    assert first == replay
    assert first != second


def test_prompt_hash_includes_system_and_history():
    base = prompt_hash("正文", system_prompt="系统", history=[])
    changed_system = prompt_hash("正文", system_prompt="另一个系统", history=[])
    changed_history = prompt_hash(
        "正文", system_prompt="系统", history=[{"role": "user", "content": "前文"}]
    )

    assert base != changed_system
    assert base != changed_history


class _AsyncDb:
    def __init__(self):
        self.calls = []
        self.flushed = 0

    async def execute(self, statement, params):
        self.calls.append((statement, params))

    async def flush(self):
        self.flushed += 1


class _PromptManager:
    records = []

    def __init__(self, *_args):
        pass

    async def record_runtime_execution(self, *args, **kwargs):
        type(self).records.append((args, kwargs))
        return {"id": str(uuid.uuid4())}


@pytest.mark.asyncio
async def test_v7_success_closes_prompt_and_shared_ledger(monkeypatch):
    import app.v7.prompt.prompt_manager as prompt_module

    _PromptManager.records = []
    db = _AsyncDb()
    monkeypatch.setattr(prompt_module, "PromptVersionManager", _PromptManager)
    gateway = AIGateway(db=db, novel_id=uuid.uuid4(), project_id="project-1")

    await gateway._record_shared_provenance(
        prompt="正文输入",
        system_prompt="系统约束",
        history=[{"role": "user", "content": "上一段"}],
        result={
            "text": "provider 输出",
            "model": "deepseek-chat",
            "tokens_input": 12,
            "tokens_output": 8,
            "cost": 0.000028,
        },
        prompt_name="v7.generation.chapter",
        prompt_version="1.0.0",
        json_mode=False,
        attempt=1,
        logical_mutation_id="mutation-1",
        started=0.0,
    )

    assert _PromptManager.records
    kwargs = _PromptManager.records[0][1]
    assert kwargs["version_label"] == "1.0.0"
    assert kwargs["rendered_prompt"] == "正文输入"
    assert kwargs["input_variables"]["rendered_prompt_hash"]
    assert db.calls
    statement, params = db.calls[0]
    assert "ai_execution_ledger" in str(statement)
    assert params["gateway_version"] == "v7"
    assert params["prompt_name"] == "v7.generation.chapter"
    assert params["prompt_hash"] == kwargs["input_variables"]["rendered_prompt_hash"]
    assert db.flushed == 1


@pytest.mark.asyncio
async def test_prompt_registration_reuses_concurrent_winner_after_unique_conflict():
    winner = SimpleNamespace(
        id=uuid.uuid4(),
        prompt_name="v7.review.33_dimension",
        version=5,
        version_label="1.4.1",
        model="deepseek-chat",
        parameters={},
        output_schema=None,
        prompt_hash="hash",
        description=None,
        change_notes=None,
        is_active=True,
        is_default=True,
        created_by="runtime",
        extra_metadata={},
        created_at=None,
        template="runtime-managed:v7.review.33_dimension:1.4.1",
        golden_cases=[],
    )

    class Db:
        def __init__(self):
            self.rollbacks = 0

        async def rollback(self):
            self.rollbacks += 1

    class Repo:
        def __init__(self):
            self.lookup_count = 0

        async def get_by_hash(self, _name, _hash):
            self.lookup_count += 1
            return None if self.lookup_count == 1 else winner

        async def get_default(self, _name):
            return None

        async def create_version(self, *_args, **_kwargs):
            raise IntegrityError("insert", {}, Exception("duplicate"))

    db = Db()
    manager = object.__new__(PromptVersionManager)
    manager.db = db
    manager.version_repo = Repo()

    result = await manager.register_version(
        "v7.review.33_dimension",
        winner.template,
        model=winner.model,
        parameters=winner.parameters,
        version_label=winner.version_label,
    )

    assert result["created"] is False
    assert result["version"]["id"] == str(winner.id)
    assert db.rollbacks == 1
