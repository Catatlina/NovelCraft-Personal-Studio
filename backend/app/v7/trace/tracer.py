"""Execution tracer - Sprint 1 skeleton."""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.trace import AgentRunRepository, AgentTraceRepository
from ..repositories.event import EventLogRepository


class TraceStepContext:
    """Mutable handle yielded by :meth:`ExecutionTracer.trace_step`.

    Lets the code inside a ``async with`` block report what the step produced
    (summary, structured output, token usage, cost, model, confidence) so the
    tracer can persist real values instead of zeros.
    """

    __slots__ = (
        "step_id",
        "output_summary",
        "output_data",
        "tokens_input",
        "tokens_output",
        "cost",
        "model",
        "confidence",
    )

    def __init__(self, step_id: uuid.UUID):
        self.step_id = step_id
        self.output_summary: str | None = None
        self.output_data: dict[str, Any] | None = None
        self.tokens_input: int = 0
        self.tokens_output: int = 0
        self.cost: float = 0.0
        self.model: str | None = None
        self.confidence: float | None = None

    def set_output(
        self,
        summary: str | None = None,
        *,
        data: dict[str, Any] | None = None,
        tokens_input: int = 0,
        tokens_output: int = 0,
        cost: float = 0.0,
        model: str | None = None,
        confidence: float | None = None,
    ) -> None:
        """Record the step outcome; persisted when the context block exits."""
        if summary is not None:
            self.output_summary = summary
        if data is not None:
            self.output_data = data
        self.tokens_input += tokens_input
        self.tokens_output += tokens_output
        self.cost += cost
        if model:
            self.model = model
        if confidence is not None:
            self.confidence = confidence

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return str(self.step_id)


class ExecutionTracer:
    """
    Execution tracer for tracking AI agent execution.
    
    Sprint 1: Basic skeleton with run and step tracking.
    Sprint 2: Full integration with all engines and director.
    """

    def __init__(self, db: AsyncSession, novel_id: uuid.UUID):
        self.db = db
        self.novel_id = novel_id
        self.run_repo = AgentRunRepository(db)
        self.trace_repo = AgentTraceRepository(db)
        self.event_repo = EventLogRepository(db)
        self._current_run: uuid.UUID | None = None
        self._step_counter: int = 0
        # Stack of currently open steps so nested steps get a parent_step_id.
        self._step_stack: list[uuid.UUID] = []

    async def start_run(
        self,
        run_type: str,
        *,
        trigger: str = "manual",
        input_data: dict[str, Any] | None = None,
        chapter_number: int | None = None,
    ) -> uuid.UUID:
        """Start a new agent run."""
        run = await self.run_repo.start_run(
            self.novel_id,
            run_type,
            trigger=trigger,
            input_data=input_data,
            chapter_number=chapter_number,
        )
        self._current_run = run.id
        self._step_counter = 0
        self._step_stack = []

        await self.event_repo.record_event(
            self.novel_id,
            "run_started",
            f"Run started: {run_type}",
            "trace",
            source="system",
            source_run_id=run.id,
            event_data={"run_type": run_type, "chapter_number": chapter_number},
        )

        return run.id

    async def complete_run(
        self,
        run_id: uuid.UUID | None = None,
        *,
        output_data: dict[str, Any] | None = None,
        error_message: str | None = None,
        error_type: str | None = None,
    ) -> dict[str, Any]:
        """Complete a run."""
        run_id = run_id or self._current_run
        if not run_id:
            raise ValueError("No active run")

        run = await self.run_repo.complete_run(
            run_id,
            output_data=output_data,
            error_message=error_message,
            error_type=error_type,
        )

        await self.event_repo.record_event(
            self.novel_id,
            "run_completed" if not error_message else "run_failed",
            f"Run {'completed' if not error_message else 'failed'}: {run.run_type}",
            "trace",
            source="system",
            source_run_id=run.id,
            severity="info" if not error_message else "error",
            event_data={
                "duration": run.duration_seconds,
                "total_tokens": run.total_tokens,
                "total_cost": run.total_cost,
            },
        )

        self._current_run = None
        self._step_counter = 0
        self._step_stack = []

        return {
            "id": str(run.id),
            "status": run.status,
            "duration_seconds": run.duration_seconds,
            "total_tokens": run.total_tokens,
            "total_cost": run.total_cost,
            "step_count": run.step_count,
        }

    async def start_step(
        self,
        step_name: str,
        step_type: str,
        *,
        input_summary: str | None = None,
        input_data: dict[str, Any] | None = None,
        run_id: uuid.UUID | None = None,
        parent_step_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """Start a new trace step."""
        run_id = run_id or self._current_run
        if not run_id:
            raise ValueError("No active run")

        self._step_counter += 1
        if parent_step_id is None and self._step_stack:
            parent_step_id = self._step_stack[-1]

        step = await self.trace_repo.start_step(
            self.novel_id,
            run_id,
            step_name,
            step_type,
            step_order=self._step_counter,
            input_summary=input_summary,
            input_data=input_data,
            parent_step_id=parent_step_id,
        )

        return step.id

    async def complete_step(
        self,
        step_id: uuid.UUID,
        *,
        output_summary: str | None = None,
        output_data: dict[str, Any] | None = None,
        tokens_input: int = 0,
        tokens_output: int = 0,
        cost: float = 0.0,
        model: str | None = None,
        confidence: float | None = None,
        error_message: str | None = None,
        error_type: str | None = None,
        run_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Complete a trace step."""
        run_id = run_id or self._current_run

        step = await self.trace_repo.complete_step(
            step_id,
            output_summary=output_summary,
            output_data=output_data,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost=cost,
            model=model,
            confidence=confidence,
            error_message=error_message,
            error_type=error_type,
        )

        # Update run stats
        if run_id:
            await self.run_repo.update_run_stats(
                run_id,
                tokens=tokens_input + tokens_output,
                cost=cost,
            )

        return {
            "id": str(step.id),
            "status": step.status,
            "duration_seconds": step.duration_seconds,
            "tokens_input": step.tokens_input,
            "tokens_output": step.tokens_output,
            "cost": step.cost,
        }

    def _pop_step(self, step_id: uuid.UUID) -> None:
        """Remove a step from the open-step stack (tolerates out-of-order exits)."""
        if step_id in self._step_stack:
            index = len(self._step_stack) - 1 - self._step_stack[::-1].index(step_id)
            del self._step_stack[index:]

    @asynccontextmanager
    async def trace_step(
        self,
        step_name: str,
        step_type: str,
        *,
        input_summary: str | None = None,
        input_data: dict[str, Any] | None = None,
    ):
        """Context manager for tracing a step.

        Yields a :class:`TraceStepContext`; callers can attach output summary,
        token usage, cost, model and confidence to it and those values are
        persisted when the block exits::

            async with tracer.trace_step("generate", "ai_generation") as step:
                res = await gateway.generate(prompt)
                step.set_output("3120 chars", tokens_input=..., cost=...)

        The context object also behaves like the step UUID for legacy callers
        that only need ``step.step_id``.
        """
        step_id = await self.start_step(
            step_name,
            step_type,
            input_summary=input_summary,
            input_data=input_data,
        )
        ctx = TraceStepContext(step_id)
        self._step_stack.append(step_id)
        try:
            yield ctx
        except Exception as e:
            self._pop_step(step_id)
            await self.complete_step(
                step_id,
                tokens_input=ctx.tokens_input,
                tokens_output=ctx.tokens_output,
                cost=ctx.cost,
                model=ctx.model,
                error_message=str(e),
                error_type=type(e).__name__,
            )
            raise
        else:
            self._pop_step(step_id)
            await self.complete_step(
                step_id,
                output_summary=ctx.output_summary,
                output_data=ctx.output_data,
                tokens_input=ctx.tokens_input,
                tokens_output=ctx.tokens_output,
                cost=ctx.cost,
                model=ctx.model,
                confidence=ctx.confidence,
            )

    async def get_run(
        self,
        run_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        """Get run details."""
        run = await self.run_repo.get(run_id)
        if not run:
            return None
        return {
            "id": str(run.id),
            "run_type": run.run_type,
            "status": run.status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "duration_seconds": run.duration_seconds,
            "total_tokens": run.total_tokens,
            "total_cost": run.total_cost,
            "step_count": run.step_count,
            "chapter_number": run.chapter_number,
        }

    async def list_runs(
        self,
        *,
        run_type: str | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List runs."""
        runs = await self.run_repo.list_by_novel(
            self.novel_id,
            run_type=run_type,
            status=status,
            skip=skip,
            limit=limit,
        )
        return [
            {
                "id": str(r.id),
                "run_type": r.run_type,
                "status": r.status,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "duration_seconds": r.duration_seconds,
                "total_tokens": r.total_tokens,
                "total_cost": r.total_cost,
                "step_count": r.step_count,
                "chapter_number": r.chapter_number,
            }
            for r in runs
        ]

    async def get_trace_steps(
        self,
        run_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get trace steps for a run."""
        steps = await self.trace_repo.list_by_run(
            run_id, skip=skip, limit=limit
        )
        return [
            {
                "id": str(s.id),
                "step_name": s.step_name,
                "step_type": s.step_type,
                "step_order": s.step_order,
                "status": s.status,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "duration_seconds": s.duration_seconds,
                "input_summary": s.input_summary,
                "output_summary": s.output_summary,
                "tokens_input": s.tokens_input,
                "tokens_output": s.tokens_output,
                "cost": s.cost,
                "model": s.model,
                "confidence": s.confidence,
            }
            for s in steps
        ]
