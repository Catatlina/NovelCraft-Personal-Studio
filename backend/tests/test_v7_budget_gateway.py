from __future__ import annotations

import uuid

import pytest

from app.v7.cost.cost_manager import BudgetExceededError
from app.v7.generation.generation_engine import AIGateway, AIGatewayError


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices": [{
                "message": {"content": "真实 provider 输出"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 12, "completion_tokens": 8},
        }


class _Client:
    calls = 0

    def __init__(self, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def post(self, *_args, **_kwargs):
        type(self).calls += 1
        return _Response()


class _Budget:
    checks: list[dict] = []
    records: list[dict] = []
    should_block = False
    should_fail_record = False

    def __init__(self, *_args):
        pass

    async def assert_within_budget(self, **kwargs):
        type(self).checks.append(kwargs)
        if type(self).should_block:
            raise BudgetExceededError("blocked", [{"budget_type": "per_run"}])

    async def record_cost(self, **kwargs):
        if type(self).should_fail_record:
            raise RuntimeError("ledger unavailable")
        type(self).records.append(kwargs)
        return {"action": "none"}


@pytest.mark.asyncio
async def test_v7_gateway_blocks_before_provider_when_budget_is_exceeded(monkeypatch):
    from app.v7.cost import cost_manager
    import app.v7.generation.generation_engine as generation_module

    _Client.calls = 0
    _Budget.checks = []
    _Budget.records = []
    _Budget.should_block = True
    _Budget.should_fail_record = False
    monkeypatch.setattr(cost_manager, "CostBudgetManager", _Budget)
    monkeypatch.setattr(generation_module.httpx, "AsyncClient", _Client)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    gateway = AIGateway(db=object(), novel_id=uuid.uuid4())
    with pytest.raises(AIGatewayError, match="blocked"):
        await gateway.generate("本章正文", max_tokens=100, prompt_name="v7.test")

    assert _Client.calls == 0
    assert _Budget.checks
    assert not _Budget.records


@pytest.mark.asyncio
async def test_v7_gateway_records_provider_reported_spend_after_success(monkeypatch):
    from app.v7.cost import cost_manager
    import app.v7.generation.generation_engine as generation_module

    _Client.calls = 0
    _Budget.checks = []
    _Budget.records = []
    _Budget.should_block = False
    _Budget.should_fail_record = False
    monkeypatch.setattr(cost_manager, "CostBudgetManager", _Budget)
    monkeypatch.setattr(generation_module.httpx, "AsyncClient", _Client)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    gateway = AIGateway(db=object(), novel_id=uuid.uuid4())
    result = await gateway.generate(
        "本章正文", max_tokens=100, prompt_name="v7.test", prompt_version="1.0.0"
    )

    assert result["text"] == "真实 provider 输出"
    assert _Client.calls == 1
    assert _Budget.checks[0]["estimated_tokens"] >= 100
    assert _Budget.records == [{
        "cost_cny": pytest.approx(0.000028),
        "tokens": 20,
        "run_id": None,
        "source": "v7_ai_gateway",
        "description": "V7 provider call: v7.test",
    }]


@pytest.mark.asyncio
async def test_v7_gateway_does_not_repeat_billable_call_when_ledger_write_fails(monkeypatch):
    from app.v7.cost import cost_manager
    import app.v7.generation.generation_engine as generation_module

    _Client.calls = 0
    _Budget.checks = []
    _Budget.records = []
    _Budget.should_block = False
    _Budget.should_fail_record = True
    monkeypatch.setattr(cost_manager, "CostBudgetManager", _Budget)
    monkeypatch.setattr(generation_module.httpx, "AsyncClient", _Client)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    gateway = AIGateway(db=object(), novel_id=uuid.uuid4())
    with pytest.raises(AIGatewayError, match="accounting failed"):
        await gateway.generate("本章正文", max_tokens=100, prompt_name="v7.test")

    assert _Client.calls == 1
