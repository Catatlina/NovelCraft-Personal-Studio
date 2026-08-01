"""Cost budget repository."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import select, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from ..models.cost import CostBudget
from ..models.trace import AgentRun, AgentTrace
from ..models.prompt import PromptExecution


class CostBudgetRepository(BaseRepository[CostBudget]):
    """Cost budget repository."""

    def __init__(self, db: AsyncSession):
        super().__init__(CostBudget, db)

    async def list_by_novel(
        self,
        novel_id: uuid.UUID,
        *,
        budget_type: str | None = None,
        budget_scope: str | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[CostBudget]:
        """List budgets for a novel."""
        query = select(CostBudget).where(CostBudget.novel_id == novel_id)

        if budget_type:
            query = query.where(CostBudget.budget_type == budget_type)
        if budget_scope:
            query = query.where(CostBudget.budget_scope == budget_scope)
        if is_active is not None:
            query = query.where(CostBudget.is_active == is_active)

        query = query.order_by(CostBudget.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_active_by_type(
        self,
        novel_id: uuid.UUID,
        budget_type: str,
    ) -> CostBudget | None:
        """Get the active budget of a given type."""
        result = await self.db.execute(
            select(CostBudget)
            .where(
                CostBudget.novel_id == novel_id,
                CostBudget.budget_type == budget_type,
                CostBudget.is_active == True,
            )
            .order_by(CostBudget.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_budget(
        self,
        novel_id: uuid.UUID,
        budget_type: str,
        budget_scope: str,
        limit_cny: float,
        *,
        limit_tokens: int | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
        action_on_exceed: str = "warn",
        description: str | None = None,
        cost_policy: dict[str, Any] | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> CostBudget:
        """Create a cost budget."""
        return await self.create({
            "novel_id": novel_id,
            "budget_type": budget_type,
            "budget_scope": budget_scope,
            "limit_cny": limit_cny,
            "spent_cny": 0.0,
            "limit_tokens": limit_tokens,
            "spent_tokens": 0,
            "period_start": period_start,
            "period_end": period_end,
            "alert_threshold_80": False,
            "alert_threshold_95": False,
            "action_on_exceed": action_on_exceed,
            "is_active": True,
            "description": description,
            "cost_policy": cost_policy or {},
            "extra_metadata": extra_metadata or {},
        })

    async def add_spend(
        self,
        budget_id: uuid.UUID,
        *,
        cost_cny: float = 0.0,
        tokens: int = 0,
    ) -> CostBudget:
        """Increment the spent counters of a budget."""
        budget = await self.get_or_404(budget_id)
        budget.spent_cny = (budget.spent_cny or 0.0) + cost_cny
        budget.spent_tokens = (budget.spent_tokens or 0) + tokens
        await self.db.flush()
        await self.db.refresh(budget)
        return budget

    # ── Actual spend aggregation (source of truth: agent runs / prompt execs) ──

    async def sum_run_cost(
        self,
        novel_id: uuid.UUID,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        run_type: str | None = None,
    ) -> dict[str, Any]:
        """Sum actual cost/tokens recorded on agent runs."""
        query = select(
            func.coalesce(func.sum(AgentRun.total_cost), 0.0),
            func.coalesce(func.sum(AgentRun.total_tokens), 0),
            func.count(),
        ).where(AgentRun.novel_id == novel_id)

        if start_date:
            query = query.where(cast(AgentRun.started_at, Date) >= start_date)
        if end_date:
            query = query.where(cast(AgentRun.started_at, Date) <= end_date)
        if run_type:
            query = query.where(AgentRun.run_type == run_type)

        result = await self.db.execute(query)
        row = result.one()
        return {
            "cost_cny": float(row[0] or 0.0),
            "tokens": int(row[1] or 0),
            "run_count": int(row[2] or 0),
        }

    async def sum_cost_by_date(
        self,
        novel_id: uuid.UUID,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Aggregate actual cost grouped by calendar date."""
        day = cast(AgentRun.started_at, Date).label("day")
        query = (
            select(
                day,
                func.coalesce(func.sum(AgentRun.total_cost), 0.0),
                func.coalesce(func.sum(AgentRun.total_tokens), 0),
                func.count(),
            )
            .where(AgentRun.novel_id == novel_id)
        )

        if start_date:
            query = query.where(cast(AgentRun.started_at, Date) >= start_date)
        if end_date:
            query = query.where(cast(AgentRun.started_at, Date) <= end_date)

        query = query.group_by(day).order_by(day)
        result = await self.db.execute(query)
        return [
            {
                "date": row[0].isoformat() if row[0] else None,
                "cost_cny": float(row[1] or 0.0),
                "tokens": int(row[2] or 0),
                "run_count": int(row[3] or 0),
            }
            for row in result.all()
        ]

    async def sum_cost_by_run_type(
        self,
        novel_id: uuid.UUID,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Aggregate actual cost grouped by run type (task type)."""
        query = (
            select(
                AgentRun.run_type,
                func.coalesce(func.sum(AgentRun.total_cost), 0.0),
                func.coalesce(func.sum(AgentRun.total_tokens), 0),
                func.count(),
            )
            .where(AgentRun.novel_id == novel_id)
        )

        if start_date:
            query = query.where(cast(AgentRun.started_at, Date) >= start_date)
        if end_date:
            query = query.where(cast(AgentRun.started_at, Date) <= end_date)

        query = query.group_by(AgentRun.run_type).order_by(AgentRun.run_type)
        result = await self.db.execute(query)
        return [
            {
                "run_type": row[0],
                "cost_cny": float(row[1] or 0.0),
                "tokens": int(row[2] or 0),
                "run_count": int(row[3] or 0),
            }
            for row in result.all()
        ]

    async def sum_cost_by_step_type(
        self,
        novel_id: uuid.UUID,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Aggregate actual cost grouped by trace step type."""
        query = (
            select(
                AgentTrace.step_type,
                func.coalesce(func.sum(AgentTrace.cost), 0.0),
                func.coalesce(
                    func.sum(AgentTrace.tokens_input + AgentTrace.tokens_output), 0
                ),
                func.count(),
            )
            .where(AgentTrace.novel_id == novel_id)
        )

        if start_date:
            query = query.where(cast(AgentTrace.started_at, Date) >= start_date)
        if end_date:
            query = query.where(cast(AgentTrace.started_at, Date) <= end_date)

        query = query.group_by(AgentTrace.step_type).order_by(AgentTrace.step_type)
        result = await self.db.execute(query)
        return [
            {
                "step_type": row[0],
                "cost_cny": float(row[1] or 0.0),
                "tokens": int(row[2] or 0),
                "step_count": int(row[3] or 0),
            }
            for row in result.all()
        ]

    async def sum_prompt_execution_cost(
        self,
        novel_id: uuid.UUID,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """Sum actual cost/tokens recorded on prompt executions."""
        query = select(
            func.coalesce(func.sum(PromptExecution.cost), 0.0),
            func.coalesce(
                func.sum(
                    PromptExecution.tokens_input + PromptExecution.tokens_output
                ),
                0,
            ),
            func.count(),
        ).where(PromptExecution.novel_id == novel_id)

        if start_date:
            query = query.where(cast(PromptExecution.created_at, Date) >= start_date)
        if end_date:
            query = query.where(cast(PromptExecution.created_at, Date) <= end_date)

        result = await self.db.execute(query)
        row = result.one()
        return {
            "cost_cny": float(row[0] or 0.0),
            "tokens": int(row[1] or 0),
            "execution_count": int(row[2] or 0),
        }

    async def sum_prompt_cost_by_date(
        self,
        novel_id: uuid.UUID,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Aggregate prompt execution cost grouped by calendar date."""
        day = cast(PromptExecution.created_at, Date).label("day")
        query = select(
            day,
            func.coalesce(func.sum(PromptExecution.cost), 0.0),
            func.coalesce(
                func.sum(
                    PromptExecution.tokens_input + PromptExecution.tokens_output
                ),
                0,
            ),
            func.count(),
        ).where(PromptExecution.novel_id == novel_id)

        if start_date:
            query = query.where(cast(PromptExecution.created_at, Date) >= start_date)
        if end_date:
            query = query.where(cast(PromptExecution.created_at, Date) <= end_date)

        query = query.group_by(day).order_by(day)
        result = await self.db.execute(query)
        return [
            {
                "date": row[0].isoformat() if row[0] else None,
                "cost_cny": float(row[1] or 0.0),
                "tokens": int(row[2] or 0),
                "execution_count": int(row[3] or 0),
            }
            for row in result.all()
        ]

    async def sum_prompt_cost_by_name(
        self,
        novel_id: uuid.UUID,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Aggregate prompt execution cost grouped by prompt name (task type)."""
        query = select(
            PromptExecution.prompt_name,
            func.coalesce(func.sum(PromptExecution.cost), 0.0),
            func.coalesce(
                func.sum(
                    PromptExecution.tokens_input + PromptExecution.tokens_output
                ),
                0,
            ),
            func.count(),
        ).where(PromptExecution.novel_id == novel_id)

        if start_date:
            query = query.where(cast(PromptExecution.created_at, Date) >= start_date)
        if end_date:
            query = query.where(cast(PromptExecution.created_at, Date) <= end_date)

        query = query.group_by(PromptExecution.prompt_name).order_by(
            PromptExecution.prompt_name
        )
        result = await self.db.execute(query)
        return [
            {
                "prompt_name": row[0],
                "cost_cny": float(row[1] or 0.0),
                "tokens": int(row[2] or 0),
                "execution_count": int(row[3] or 0),
            }
            for row in result.all()
        ]
