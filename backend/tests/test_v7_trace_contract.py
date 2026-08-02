"""Regression tests for the V7 trace response contract."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.v7.api.schemas import RunResponse
from app.v7.trace.tracer import ExecutionTracer


@pytest.mark.asyncio
async def test_list_runs_includes_step_count_for_run_response() -> None:
    run = SimpleNamespace(
        id=uuid4(),
        run_type="chapter_generation",
        status="completed",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        duration_seconds=1.5,
        total_tokens=120,
        total_cost=0.012,
        step_count=4,
        chapter_number=3,
    )

    class FakeRunRepository:
        async def list_by_novel(self, *args, **kwargs):
            return [run]

    tracer = object.__new__(ExecutionTracer)
    tracer.novel_id = uuid4()
    tracer.run_repo = FakeRunRepository()

    rows = await tracer.list_runs()

    assert rows[0]["step_count"] == 4
    validated = RunResponse.model_validate(rows[0])
    assert validated.step_count == 4
