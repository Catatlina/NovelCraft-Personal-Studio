"""Cost Budget Manager - Sprint 3 Alpha.

Manages cost budgets, tracking, and alerts.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.cost import CostBudgetRepository


class CostBudgetManager:
    """
    Cost budget manager.
    
    Sprint 3 Alpha: Basic budget tracking and alerts.
    Full cost policies and auto-shutdown in V7.1.
    """

    def __init__(self, db: AsyncSession, novel_id: uuid.UUID):
        self.db = db
        self.novel_id = novel_id
        self.budget_repo = CostBudgetRepository(db)

    async def list_budgets(
        self,
        *,
        budget_type: str | None = None,
        is_active: bool | None = None,
    ) -> list[dict[str, Any]]:
        """List all cost budgets."""
        budgets = await self.budget_repo.list_by_novel(
            self.novel_id,
            budget_type=budget_type,
            is_active=is_active,
        )
        return [self._budget_to_dict(b) for b in budgets]

    async def get_budget(self, budget_id: uuid.UUID) -> dict[str, Any] | None:
        """Get a specific budget."""
        budget = await self.budget_repo.get(budget_id)
        if not budget:
            return None
        return self._budget_to_dict(budget)

    async def create_budget(
        self,
        budget_type: str,
        budget_scope: str,
        *,
        limit_cny: float = 100.0,
        limit_tokens: int = 1000000,
        period_days: int = 30,
        alert_threshold_80: float = 0.8,
        alert_threshold_95: float = 0.95,
        action_on_exceed: str = "notify",
        description: str = "",
        cost_policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new cost budget."""
        now = datetime.utcnow()
        period_end = now + timedelta(days=period_days)

        budget = await self.budget_repo.create(
            novel_id=self.novel_id,
            budget_type=budget_type,
            budget_scope=budget_scope,
            limit_cny=limit_cny,
            spent_cny=0.0,
            limit_tokens=limit_tokens,
            spent_tokens=0,
            period_start=now,
            period_end=period_end,
            alert_threshold_80=alert_threshold_80,
            alert_threshold_95=alert_threshold_95,
            action_on_exceed=action_on_exceed,
            is_active=True,
            description=description,
            cost_policy=cost_policy or {},
        )

        return self._budget_to_dict(budget)

    async def record_cost(
        self,
        budget_type: str,
        *,
        cost_cny: float = 0.0,
        tokens: int = 0,
    ) -> dict[str, Any]:
        """
        Record cost usage.
        
        Returns:
            - budget_remaining: remaining budget
            - alerts: list of triggered alerts
            - action_taken: action taken if limit exceeded
        """
        budgets = await self.budget_repo.list_by_novel(
            self.novel_id,
            budget_type=budget_type,
            is_active=True,
        )

        alerts = []
        action_taken = "none"

        for budget in budgets:
            new_spent_cny = budget.spent_cny + cost_cny
            new_spent_tokens = budget.spent_tokens + tokens

            # Check thresholds
            cny_ratio = new_spent_cny / budget.limit_cny if budget.limit_cny > 0 else 0
            token_ratio = new_spent_tokens / budget.limit_tokens if budget.limit_tokens > 0 else 0

            if cny_ratio >= budget.alert_threshold_95 or token_ratio >= budget.alert_threshold_95:
                alerts.append({
                    "level": "critical",
                    "budget_id": str(budget.id),
                    "message": f"Budget at {round(max(cny_ratio, token_ratio) * 100)}%",
                })
                if budget.action_on_exceed == "block":
                    action_taken = "blocked"
            elif cny_ratio >= budget.alert_threshold_80 or token_ratio >= budget.alert_threshold_80:
                alerts.append({
                    "level": "warning",
                    "budget_id": str(budget.id),
                    "message": f"Budget at {round(max(cny_ratio, token_ratio) * 100)}%",
                })

            # Update budget
            await self.budget_repo.update(
                budget.id,
                {
                    "spent_cny": new_spent_cny,
                    "spent_tokens": new_spent_tokens,
                },
            )

        return {
            "cost_recorded": cost_cny,
            "tokens_recorded": tokens,
            "alerts": alerts,
            "action_taken": action_taken,
        }

    async def get_budget_summary(self) -> dict[str, Any]:
        """Get budget summary overview."""
        budgets = await self.budget_repo.list_by_novel(
            self.novel_id,
            is_active=True,
        )

        total_limit = sum(b.limit_cny for b in budgets)
        total_spent = sum(b.spent_cny for b in budgets)
        total_tokens_limit = sum(b.limit_tokens for b in budgets)
        total_tokens_spent = sum(b.spent_tokens for b in budgets)

        return {
            "total_budget_cny": total_limit,
            "total_spent_cny": total_spent,
            "total_remaining_cny": total_limit - total_spent,
            "usage_percentage": (total_spent / total_limit * 100) if total_limit > 0 else 0,
            "total_tokens_limit": total_tokens_limit,
            "total_tokens_spent": total_tokens_spent,
            "active_budgets": len(budgets),
            "budgets": [self._budget_to_dict(b) for b in budgets],
        }

    async def reset_budget(self, budget_id: uuid.UUID) -> dict[str, Any] | None:
        """Reset a budget's spent amount."""
        budget = await self.budget_repo.get(budget_id)
        if not budget:
            return None

        updated = await self.budget_repo.update(
            budget_id,
            {
                "spent_cny": 0.0,
                "spent_tokens": 0,
                "period_start": datetime.utcnow(),
            },
        )

        return self._budget_to_dict(updated) if updated else None

    def _budget_to_dict(self, budget: Any) -> dict[str, Any]:
        cny_ratio = budget.spent_cny / budget.limit_cny if budget.limit_cny > 0 else 0
        token_ratio = budget.spent_tokens / budget.limit_tokens if budget.limit_tokens > 0 else 0
        
        return {
            "id": str(budget.id),
            "budget_type": budget.budget_type,
            "budget_scope": budget.budget_scope,
            "limit_cny": budget.limit_cny,
            "spent_cny": budget.spent_cny,
            "remaining_cny": budget.limit_cny - budget.spent_cny,
            "usage_percentage": round(cny_ratio * 100, 2),
            "limit_tokens": budget.limit_tokens,
            "spent_tokens": budget.spent_tokens,
            "remaining_tokens": budget.limit_tokens - budget.spent_tokens,
            "token_usage_percentage": round(token_ratio * 100, 2),
            "period_start": budget.period_start.isoformat() if budget.period_start else None,
            "period_end": budget.period_end.isoformat() if budget.period_end else None,
            "alert_threshold_80": budget.alert_threshold_80,
            "alert_threshold_95": budget.alert_threshold_95,
            "action_on_exceed": budget.action_on_exceed,
            "is_active": budget.is_active,
            "description": budget.description,
            "cost_policy": budget.cost_policy,
        }
