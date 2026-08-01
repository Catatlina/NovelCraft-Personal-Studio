"""Execution trace repositories."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from ..models.trace import AgentRun, AgentTrace


class AgentRunRepository(BaseRepository[AgentRun]):
    """Agent run repository."""

    def __init__(self, db: AsyncSession):
        super().__init__(AgentRun, db)

    async def list_by_novel(
        self,
        novel_id: uuid.UUID,
        *,
        run_type: str | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[AgentRun]:
        """List runs for a novel."""
        query = select(AgentRun).where(AgentRun.novel_id == novel_id)

        if run_type:
            query = query.where(AgentRun.run_type == run_type)
        if status:
            query = query.where(AgentRun.status == status)

        query = query.order_by(AgentRun.started_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def start_run(
        self,
        novel_id: uuid.UUID,
        run_type: str,
        *,
        trigger: str = "manual",
        trigger_by: uuid.UUID | None = None,
        parent_run_id: uuid.UUID | None = None,
        input_data: dict[str, Any] | None = None,
        chapter_number: int | None = None,
    ) -> AgentRun:
        """Start a new run."""
        return await self.create({
            "novel_id": novel_id,
            "run_type": run_type,
            "status": "running",
            "trigger": trigger,
            "trigger_by": trigger_by,
            "parent_run_id": parent_run_id,
            "input_data": input_data or {},
            "chapter_number": chapter_number,
        })

    async def complete_run(
        self,
        run_id: uuid.UUID,
        *,
        output_data: dict[str, Any] | None = None,
        error_message: str | None = None,
        error_type: str | None = None,
    ) -> AgentRun:
        """Complete a run."""
        run = await self.get_or_404(run_id)
        
        if error_message:
            run.status = "failed"
            run.error_message = error_message
            run.error_type = error_type
        else:
            run.status = "completed"
            run.output_data = output_data
        
        run.completed_at = datetime.now(timezone.utc)
        if run.started_at and run.completed_at:
            run.duration_seconds = (run.completed_at - run.started_at).total_seconds()
        
        await self.db.flush()
        await self.db.refresh(run)
        return run

    async def update_run_stats(
        self,
        run_id: uuid.UUID,
        *,
        tokens: int = 0,
        cost: float = 0.0,
    ) -> AgentRun:
        """Update run statistics."""
        run = await self.get_or_404(run_id)
        run.total_tokens += tokens
        run.total_cost += cost
        run.step_count += 1
        await self.db.flush()
        await self.db.refresh(run)
        return run


class AgentTraceRepository(BaseRepository[AgentTrace]):
    """Agent trace repository."""

    def __init__(self, db: AsyncSession):
        super().__init__(AgentTrace, db)

    async def list_by_run(
        self,
        run_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AgentTrace]:
        """List trace steps for a run."""
        result = await self.db.execute(
            select(AgentTrace).where(AgentTrace.run_id == run_id)
            .order_by(AgentTrace.step_order.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def start_step(
        self,
        novel_id: uuid.UUID,
        run_id: uuid.UUID,
        step_name: str,
        step_type: str,
        *,
        step_order: int = 0,
        input_summary: str | None = None,
        input_data: dict[str, Any] | None = None,
        parent_step_id: uuid.UUID | None = None,
    ) -> AgentTrace:
        """Start a new trace step."""
        return await self.create({
            "novel_id": novel_id,
            "run_id": run_id,
            "step_name": step_name,
            "step_type": step_type,
            "step_order": step_order,
            "status": "running",
            "input_summary": input_summary,
            "input_data": input_data,
            "parent_step_id": parent_step_id,
        })

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
        prompt_version: str | None = None,
        confidence: float | None = None,
        error_message: str | None = None,
        error_type: str | None = None,
    ) -> AgentTrace:
        """Complete a trace step."""
        step = await self.get_or_404(step_id)

        # Token/cost accounting must be recorded even for failed steps,
        # otherwise run-level cost statistics silently under-count.
        step.tokens_input = tokens_input
        step.tokens_output = tokens_output
        step.cost = cost
        step.model = model
        step.prompt_version = prompt_version

        if error_message:
            step.status = "failed"
            step.error_message = error_message
            step.error_type = error_type
        else:
            step.status = "completed"
            step.output_summary = output_summary
            step.output_data = output_data
            step.confidence = confidence
        
        step.completed_at = datetime.now(timezone.utc)
        if step.started_at and step.completed_at:
            step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
        
        await self.db.flush()
        await self.db.refresh(step)
        return step
