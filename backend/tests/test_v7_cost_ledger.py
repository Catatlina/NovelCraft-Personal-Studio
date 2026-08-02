from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.services.ai_runtime import _ledger_conditions
from app.v7.cost.cost_manager import CostBudgetManager


def test_ledger_date_filter_uses_half_open_bind_without_double_colon():
    conditions, params = _ledger_conditions(
        project_id="project-1",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 2),
    )

    assert "created_at >= :start_date" in conditions
    assert "created_at < :end_date_exclusive" in conditions
    assert all("::" not in condition for condition in conditions)
    assert params["end_date_exclusive"] == date(2026, 8, 3)


@pytest.mark.asyncio
async def test_cross_version_ledger_uses_authenticated_project_scope(monkeypatch):
    import app.v7.cost.cost_manager as cost_module

    captured = {}

    async def _summary(db, **kwargs):
        captured.update(kwargs)
        return {"source": "ai_execution_ledger", "cost_cny": 0.1}

    monkeypatch.setattr(cost_module, "async_ledger_summary", _summary)
    manager = CostBudgetManager(
        object(), uuid.uuid4(), project_id="project-shared-by-v6-v7"
    )
    result = await manager.get_cross_version_ledger(
        start_date=date(2026, 8, 1), end_date=date(2026, 8, 2)
    )

    assert captured["project_id"] == "project-shared-by-v6-v7"
    assert "novel_id" not in captured
    assert result["scope"]["project_id"] == "project-shared-by-v6-v7"


@pytest.mark.asyncio
async def test_cost_stats_use_shared_ledger_as_the_only_total(monkeypatch):
    import app.v7.cost.cost_manager as cost_module

    async def _by_date(*_args, **_kwargs):
        return [
            {
                "date": "2026-08-02",
                "calls": 2,
                "tokens": 30,
                "cost_cny": 0.0123456789,
            }
        ]

    monkeypatch.setattr(cost_module, "async_ledger_by_date", _by_date)
    manager = CostBudgetManager(object(), uuid.uuid4())
    result = await manager.get_stats_by_date()

    assert result["source"] == "ai_execution_ledger"
    assert result["total_tokens"] == 30
    assert result["total_cost_cny"] == 0.01234568
    assert result["items"][0]["execution_count"] == 2
