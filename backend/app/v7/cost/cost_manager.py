"""Cost Budget Manager.

Closed loop over ``v7_cost_budgets``:
budget CRUD -> live remaining budget -> spend recording -> threshold alerts
(80% warning / 95% critical / 100% stop) -> generation blocking.

Actual spend statistics use the shared ``ai_execution_ledger`` when its
migration is available.  The V7 run/trace/prompt tables remain visible as
reconciliation references during rollout and are never added to the shared
total a second time.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.cost import CostBudget
from ..repositories.cost import CostBudgetRepository
from ..repositories.event import EventLogRepository
from ...services.ai_runtime import (
    async_ledger_by_date,
    async_ledger_by_task_type,
    async_ledger_summary,
)

WARNING_THRESHOLD = 0.80
CRITICAL_THRESHOLD = 0.95
STOP_THRESHOLD = 1.00

# Budget types whose spend counters are advanced by every recorded cost.
VALID_BUDGET_TYPES = {
    "total", "monthly", "weekly", "daily", "per_chapter", "per_run",
}
VALID_ACTIONS_ON_EXCEED = {"warn", "slow", "stop"}


class BudgetExceededError(RuntimeError):
    """Raised when a hard (``stop``) budget blocks an operation."""

    def __init__(self, message: str, blocking: list[dict[str, Any]]):
        super().__init__(message)
        self.blocking = blocking


class CostBudgetManager:
    """Cost budget manager for one novel."""

    def __init__(
        self,
        db: AsyncSession,
        novel_id: uuid.UUID,
        project_id: str | None = None,
    ):
        self.db = db
        self.novel_id = novel_id
        self.project_id = project_id
        self.budget_repo = CostBudgetRepository(db)
        self.event_repo = EventLogRepository(db)

    # ── CRUD ─────────────────────────────────────────────────────────────

    async def list_budgets(
        self,
        *,
        budget_type: str | None = None,
        budget_scope: str | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List cost budgets."""
        budgets = await self.budget_repo.list_by_novel(
            self.novel_id,
            budget_type=budget_type,
            budget_scope=budget_scope,
            is_active=is_active,
            skip=skip,
            limit=limit,
        )
        return [self._budget_to_dict(b) for b in budgets]

    async def get_budget(self, budget_id: uuid.UUID) -> dict[str, Any] | None:
        """Get one budget."""
        budget = await self.budget_repo.get(budget_id)
        if not budget or budget.novel_id != self.novel_id:
            return None
        return self._budget_to_dict(budget)

    async def create_budget(
        self,
        budget_type: str,
        budget_scope: str,
        limit_cny: float,
        *,
        limit_tokens: int | None = None,
        period_days: int | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
        action_on_exceed: str = "warn",
        description: str | None = None,
        cost_policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a cost budget."""
        if budget_type not in VALID_BUDGET_TYPES:
            raise ValueError(
                f"Invalid budget_type '{budget_type}', "
                f"expected one of {sorted(VALID_BUDGET_TYPES)}"
            )
        if action_on_exceed not in VALID_ACTIONS_ON_EXCEED:
            raise ValueError(
                f"Invalid action_on_exceed '{action_on_exceed}', "
                f"expected one of {sorted(VALID_ACTIONS_ON_EXCEED)}"
            )
        if limit_cny <= 0:
            raise ValueError("limit_cny must be > 0")

        start = period_start or datetime.now(timezone.utc).date()
        end = period_end
        if end is None and period_days:
            end = start + timedelta(days=period_days)

        budget = await self.budget_repo.create_budget(
            self.novel_id,
            budget_type,
            budget_scope,
            limit_cny,
            limit_tokens=limit_tokens,
            period_start=start,
            period_end=end,
            action_on_exceed=action_on_exceed,
            description=description,
            cost_policy=cost_policy or {},
        )

        await self.event_repo.record_event(
            self.novel_id,
            "budget_created",
            f"Budget created: {budget_type} limit {limit_cny} CNY",
            "cost",
            source="human",
            event_data={
                "budget_id": str(budget.id),
                "budget_type": budget_type,
                "limit_cny": limit_cny,
                "action_on_exceed": action_on_exceed,
            },
        )
        return self._budget_to_dict(budget)

    async def update_budget(
        self,
        budget_id: uuid.UUID,
        data: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Update mutable budget fields."""
        budget = await self.budget_repo.get(budget_id)
        if not budget or budget.novel_id != self.novel_id:
            return None

        allowed = {
            "limit_cny", "limit_tokens", "period_start", "period_end",
            "action_on_exceed", "is_active", "description", "cost_policy",
        }
        payload = {k: v for k, v in data.items() if k in allowed and v is not None}

        if "action_on_exceed" in payload and payload["action_on_exceed"] not in VALID_ACTIONS_ON_EXCEED:
            raise ValueError(
                f"Invalid action_on_exceed '{payload['action_on_exceed']}'"
            )
        if "limit_cny" in payload and payload["limit_cny"] <= 0:
            raise ValueError("limit_cny must be > 0")

        # Raising the limit clears already-fired alert flags.
        if "limit_cny" in payload and payload["limit_cny"] > budget.limit_cny:
            payload["alert_threshold_80"] = False
            payload["alert_threshold_95"] = False

        if not payload:
            return self._budget_to_dict(budget)

        updated = await self.budget_repo.update(budget_id, payload)
        return self._budget_to_dict(updated)

    async def delete_budget(self, budget_id: uuid.UUID) -> bool:
        """Deactivate a budget (soft delete, history preserved)."""
        budget = await self.budget_repo.get(budget_id)
        if not budget or budget.novel_id != self.novel_id:
            return False
        await self.budget_repo.update(budget_id, {"is_active": False})
        await self.event_repo.record_event(
            self.novel_id,
            "budget_deactivated",
            f"Budget deactivated: {budget.budget_type}",
            "cost",
            source="human",
            event_data={"budget_id": str(budget_id)},
        )
        return True

    async def reset_budget(self, budget_id: uuid.UUID) -> dict[str, Any] | None:
        """Reset spend counters and alert flags, starting a new period."""
        budget = await self.budget_repo.get(budget_id)
        if not budget or budget.novel_id != self.novel_id:
            return None

        today = datetime.now(timezone.utc).date()
        period_end = budget.period_end
        if budget.period_start and budget.period_end:
            period_end = today + (budget.period_end - budget.period_start)

        updated = await self.budget_repo.update(
            budget_id,
            {
                "spent_cny": 0.0,
                "spent_tokens": 0,
                "alert_threshold_80": False,
                "alert_threshold_95": False,
                "period_start": today,
                "period_end": period_end,
            },
        )
        await self.event_repo.record_event(
            self.novel_id,
            "budget_reset",
            f"Budget reset: {budget.budget_type}",
            "cost",
            source="human",
            event_data={"budget_id": str(budget_id)},
        )
        return self._budget_to_dict(updated)

    # ── Live budget state ────────────────────────────────────────────────

    async def get_remaining(self) -> dict[str, Any]:
        """Live remaining budget across all active budgets."""
        budgets = await self.budget_repo.list_by_novel(
            self.novel_id, is_active=True, limit=500
        )
        details = [self._budget_to_dict(b) for b in budgets]

        limit_cny = sum(b.limit_cny for b in budgets)
        spent_cny = sum(b.spent_cny for b in budgets)
        limit_tokens = sum(b.limit_tokens or 0 for b in budgets)
        spent_tokens = sum(b.spent_tokens for b in budgets)

        tightest = min(
            details, key=lambda d: d["remaining_cny"], default=None
        )

        return {
            "novel_id": str(self.novel_id),
            "active_budgets": len(budgets),
            "total_limit_cny": round(limit_cny, 6),
            "total_spent_cny": round(spent_cny, 6),
            "total_remaining_cny": round(limit_cny - spent_cny, 6),
            "usage_percentage": round(spent_cny / limit_cny * 100, 2) if limit_cny else 0.0,
            "total_limit_tokens": limit_tokens,
            "total_spent_tokens": spent_tokens,
            "total_remaining_tokens": limit_tokens - spent_tokens,
            "tightest_budget": tightest,
            "budgets": details,
        }

    async def check_budget(
        self,
        *,
        estimated_cost_cny: float = 0.0,
        estimated_tokens: int = 0,
        budget_type: str | None = None,
    ) -> dict[str, Any]:
        """Check whether an upcoming operation is allowed.

        Returns ``allowed=False`` when any active budget with
        ``action_on_exceed='stop'`` would be pushed to/over 100%.
        """
        budgets = await self.budget_repo.list_by_novel(
            self.novel_id, budget_type=budget_type, is_active=True, limit=500
        )

        blocking: list[dict[str, Any]] = []
        throttling: list[dict[str, Any]] = []
        alerts: list[dict[str, Any]] = []

        for budget in budgets:
            projected_cny = budget.spent_cny + estimated_cost_cny
            projected_tokens = budget.spent_tokens + estimated_tokens
            ratio = self._ratio(budget, projected_cny, projected_tokens)
            level = self._level(ratio)

            if level:
                alerts.append(self._alert(budget, ratio, level, projected=True))

            if ratio >= STOP_THRESHOLD:
                if budget.action_on_exceed == "stop":
                    blocking.append(self._alert(budget, ratio, "stop", projected=True))
                elif budget.action_on_exceed == "slow":
                    throttling.append(self._alert(budget, ratio, "slow", projected=True))

        return {
            "allowed": not blocking,
            "estimated_cost_cny": estimated_cost_cny,
            "estimated_tokens": estimated_tokens,
            "checked_budgets": len(budgets),
            "blocking": blocking,
            "throttling": throttling,
            "alerts": alerts,
            "action": "stop" if blocking else ("slow" if throttling else "proceed"),
        }

    async def assert_within_budget(
        self,
        *,
        estimated_cost_cny: float = 0.0,
        estimated_tokens: int = 0,
    ) -> dict[str, Any]:
        """Raise ``BudgetExceededError`` when a hard budget blocks the call."""
        check = await self.check_budget(
            estimated_cost_cny=estimated_cost_cny,
            estimated_tokens=estimated_tokens,
        )
        if not check["allowed"]:
            raise BudgetExceededError(
                "Operation blocked: cost budget exceeded", check["blocking"]
            )
        return check

    # ── Spend recording ──────────────────────────────────────────────────

    async def record_cost(
        self,
        *,
        cost_cny: float = 0.0,
        tokens: int = 0,
        budget_type: str | None = None,
        run_id: uuid.UUID | None = None,
        source: str = "system",
        description: str | None = None,
    ) -> dict[str, Any]:
        """Apply a real spend to every matching active budget.

        Fires 80% / 95% alerts exactly once per budget period and reports
        whether generation should now be stopped or throttled.
        """
        if cost_cny < 0 or tokens < 0:
            raise ValueError("cost_cny and tokens must be >= 0")

        budgets = await self.budget_repo.list_by_novel(
            self.novel_id, budget_type=budget_type, is_active=True, limit=500
        )

        alerts: list[dict[str, Any]] = []
        blocking: list[dict[str, Any]] = []
        throttling: list[dict[str, Any]] = []
        updated: list[dict[str, Any]] = []

        for budget in budgets:
            budget.spent_cny = (budget.spent_cny or 0.0) + cost_cny
            budget.spent_tokens = (budget.spent_tokens or 0) + tokens
            ratio = self._ratio(budget, budget.spent_cny, budget.spent_tokens)

            # Fire each threshold alert only once per period.
            if ratio >= CRITICAL_THRESHOLD and not budget.alert_threshold_95:
                budget.alert_threshold_95 = True
                budget.alert_threshold_80 = True
                alert = self._alert(budget, ratio, "critical")
                alerts.append(alert)
                await self._emit_alert_event(budget, alert, run_id)
            elif ratio >= WARNING_THRESHOLD and not budget.alert_threshold_80:
                budget.alert_threshold_80 = True
                alert = self._alert(budget, ratio, "warning")
                alerts.append(alert)
                await self._emit_alert_event(budget, alert, run_id)

            if ratio >= STOP_THRESHOLD:
                exceeded = self._alert(budget, ratio, "exceeded")
                if budget.action_on_exceed == "stop":
                    blocking.append(exceeded)
                elif budget.action_on_exceed == "slow":
                    throttling.append(exceeded)
                if exceeded not in alerts:
                    alerts.append(exceeded)

            await self.db.flush()
            await self.db.refresh(budget)
            updated.append(self._budget_to_dict(budget))

        if cost_cny or tokens:
            await self.event_repo.record_event(
                self.novel_id,
                "cost_recorded",
                description or f"Cost recorded: {cost_cny} CNY / {tokens} tokens",
                "cost",
                source=source,
                source_run_id=run_id,
                severity="warning" if blocking else "info",
                event_data={
                    "cost_cny": cost_cny,
                    "tokens": tokens,
                    "budgets_updated": len(updated),
                    "alerts": len(alerts),
                },
            )

        return {
            "cost_recorded_cny": cost_cny,
            "tokens_recorded": tokens,
            "budgets_updated": len(updated),
            "alerts": alerts,
            "blocking": blocking,
            "throttling": throttling,
            "action": "stop" if blocking else ("slow" if throttling else "none"),
            "budgets": updated,
        }

    # ── Statistics ───────────────────────────────────────────────────────

    async def get_summary(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """Budget state plus actual recorded spend for this novel."""
        remaining = await self.get_remaining()
        runs = await self.budget_repo.sum_run_cost(
            self.novel_id, start_date=start_date, end_date=end_date
        )
        prompts = await self.budget_repo.sum_prompt_execution_cost(
            self.novel_id, start_date=start_date, end_date=end_date
        )

        try:
            shared = await async_ledger_summary(
                self.db,
                novel_id=self.novel_id,
                start_date=start_date,
                end_date=end_date,
            )
            shared_available = True
        except Exception as exc:
            # Keep the legacy counters visible for migration diagnostics, but
            # never label them as the unified source if its table is absent.
            shared = {
                "source": "ai_execution_ledger",
                "status": "unavailable",
                "error_type": type(exc).__name__,
            }
            shared_available = False

        return {
            **remaining,
            "period": {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            },
            "actual_spend": {
                "agent_runs": runs,
                "prompt_executions": prompts,
                # Once the shared ledger is available it is the only total
                # used for billing display; trace/prompt tables remain as a
                # reconciliation reference and are not added again.
                "shared_ledger": shared,
                "total_cost_cny": round(
                    shared["cost_cny"] if shared_available
                    else runs["cost_cny"] + prompts["cost_cny"],
                    6,
                ),
                "total_tokens": (
                    shared["tokens"] if shared_available
                    else runs["tokens"] + prompts["tokens"]
                ),
                "total_source": (
                    "ai_execution_ledger" if shared_available else "legacy_reconciliation"
                ),
            },
        }

    async def get_cross_version_ledger(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """Expose the unified V6/V7 spend source for reconciliation and QA."""
        # V6 rows are project-scoped while V7 rows are both novel- and
        # project-scoped.  Use the authenticated project for the cross-version
        # endpoint so one report contains both gateways; fall back to the novel
        # scope only for legacy callers that cannot resolve a project.
        scope = {"project_id": self.project_id} if self.project_id else {"novel_id": self.novel_id}
        result = await async_ledger_summary(
            self.db, start_date=start_date, end_date=end_date, **scope
        )
        result["scope"] = {
            "project_id": self.project_id,
            "novel_id_fallback": None if self.project_id else str(self.novel_id),
        }
        return result

    async def get_stats_by_date(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """Actual spend grouped by calendar date from the shared ledger."""
        try:
            shared_rows = await async_ledger_by_date(
                self.db,
                novel_id=self.novel_id,
                start_date=start_date,
                end_date=end_date,
            )
            items = [
                {
                    "date": row["date"],
                    "cost_cny": row["cost_cny"],
                    "tokens": row["tokens"],
                    "run_count": 0,
                    "execution_count": row["calls"],
                    "call_count": row["calls"],
                }
                for row in shared_rows
            ]
            return {
                "novel_id": str(self.novel_id),
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "days": len(items),
                "total_cost_cny": round(sum(r["cost_cny"] for r in items), 8),
                "total_tokens": sum(r["tokens"] for r in items),
                "items": items,
                "source": "ai_execution_ledger",
            }
        except Exception:
            # The fallback is intentionally labelled; it is a migration
            # diagnostic and must not be presented as the unified total.
            pass

        run_rows = await self.budget_repo.sum_cost_by_date(
            self.novel_id, start_date=start_date, end_date=end_date
        )
        prompt_rows = await self.budget_repo.sum_prompt_cost_by_date(
            self.novel_id, start_date=start_date, end_date=end_date
        )

        merged: dict[str, dict[str, Any]] = {}
        for row in run_rows:
            merged[row["date"]] = {
                "date": row["date"],
                "cost_cny": row["cost_cny"],
                "tokens": row["tokens"],
                "run_count": row["run_count"],
                "execution_count": 0,
            }
        for row in prompt_rows:
            item = merged.setdefault(
                row["date"],
                {
                    "date": row["date"],
                    "cost_cny": 0.0,
                    "tokens": 0,
                    "run_count": 0,
                    "execution_count": 0,
                },
            )
            item["cost_cny"] = round(item["cost_cny"] + row["cost_cny"], 6)
            item["tokens"] += row["tokens"]
            item["execution_count"] += row["execution_count"]

        items = [merged[key] for key in sorted(merged)]
        return {
            "novel_id": str(self.novel_id),
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "days": len(items),
            "total_cost_cny": round(sum(r["cost_cny"] for r in items), 6),
            "total_tokens": sum(r["tokens"] for r in items),
            "items": items,
            "source": "legacy_reconciliation",
        }

    async def get_stats_by_task_type(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """Actual spend grouped by task type from the shared ledger."""
        try:
            shared_rows = await async_ledger_by_task_type(
                self.db,
                novel_id=self.novel_id,
                start_date=start_date,
                end_date=end_date,
            )
            return {
                "novel_id": str(self.novel_id),
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "total_cost_cny": round(sum(r["cost_cny"] for r in shared_rows), 8),
                "total_tokens": sum(r["tokens"] for r in shared_rows),
                "by_task_type": shared_rows,
                "by_run_type": [],
                "by_step_type": [],
                "by_prompt_name": [],
                "source": "ai_execution_ledger",
            }
        except Exception:
            pass

        by_run = await self.budget_repo.sum_cost_by_run_type(
            self.novel_id, start_date=start_date, end_date=end_date
        )
        by_step = await self.budget_repo.sum_cost_by_step_type(
            self.novel_id, start_date=start_date, end_date=end_date
        )
        by_prompt = await self.budget_repo.sum_prompt_cost_by_name(
            self.novel_id, start_date=start_date, end_date=end_date
        )
        return {
            "novel_id": str(self.novel_id),
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "total_cost_cny": round(
                sum(r["cost_cny"] for r in by_run)
                + sum(r["cost_cny"] for r in by_prompt),
                6,
            ),
            "total_tokens": (
                sum(r["tokens"] for r in by_run)
                + sum(r["tokens"] for r in by_prompt)
            ),
            "by_run_type": by_run,
            "by_step_type": by_step,
            "by_prompt_name": by_prompt,
            "source": "legacy_reconciliation",
        }

    # ── Internals ────────────────────────────────────────────────────────

    @staticmethod
    def _ratio(budget: CostBudget, spent_cny: float, spent_tokens: int) -> float:
        """Highest utilisation ratio across the money and token limits."""
        cny_ratio = spent_cny / budget.limit_cny if budget.limit_cny else 0.0
        token_ratio = (
            spent_tokens / budget.limit_tokens if budget.limit_tokens else 0.0
        )
        return max(cny_ratio, token_ratio)

    @staticmethod
    def _level(ratio: float) -> str | None:
        if ratio >= STOP_THRESHOLD:
            return "exceeded"
        if ratio >= CRITICAL_THRESHOLD:
            return "critical"
        if ratio >= WARNING_THRESHOLD:
            return "warning"
        return None

    @staticmethod
    def _alert(
        budget: CostBudget,
        ratio: float,
        level: str,
        *,
        projected: bool = False,
    ) -> dict[str, Any]:
        return {
            "level": level,
            "budget_id": str(budget.id),
            "budget_type": budget.budget_type,
            "usage_percentage": round(ratio * 100, 2),
            "limit_cny": budget.limit_cny,
            "spent_cny": round(budget.spent_cny, 6),
            "remaining_cny": round(budget.limit_cny - budget.spent_cny, 6),
            "action_on_exceed": budget.action_on_exceed,
            "projected": projected,
            "message": (
                f"Budget '{budget.budget_type}' "
                f"{'projected ' if projected else ''}at {round(ratio * 100, 2)}%"
            ),
        }

    async def _emit_alert_event(
        self,
        budget: CostBudget,
        alert: dict[str, Any],
        run_id: uuid.UUID | None,
    ) -> None:
        await self.event_repo.record_event(
            self.novel_id,
            f"budget_alert_{alert['level']}",
            alert["message"],
            "cost",
            source="system",
            source_run_id=run_id,
            severity="error" if alert["level"] in ("critical", "exceeded") else "warning",
            event_data=alert,
        )

    @staticmethod
    def _budget_to_dict(budget: CostBudget) -> dict[str, Any]:
        cny_ratio = budget.spent_cny / budget.limit_cny if budget.limit_cny else 0.0
        token_ratio = (
            budget.spent_tokens / budget.limit_tokens if budget.limit_tokens else 0.0
        )
        ratio = max(cny_ratio, token_ratio)

        return {
            "id": str(budget.id),
            "novel_id": str(budget.novel_id),
            "budget_type": budget.budget_type,
            "budget_scope": budget.budget_scope,
            "limit_cny": budget.limit_cny,
            "spent_cny": round(budget.spent_cny, 6),
            "remaining_cny": round(budget.limit_cny - budget.spent_cny, 6),
            "usage_percentage": round(cny_ratio * 100, 2),
            "limit_tokens": budget.limit_tokens,
            "spent_tokens": budget.spent_tokens,
            "remaining_tokens": (
                budget.limit_tokens - budget.spent_tokens
                if budget.limit_tokens is not None else None
            ),
            "token_usage_percentage": round(token_ratio * 100, 2),
            "period_start": budget.period_start.isoformat() if budget.period_start else None,
            "period_end": budget.period_end.isoformat() if budget.period_end else None,
            "alert_threshold_80_fired": budget.alert_threshold_80,
            "alert_threshold_95_fired": budget.alert_threshold_95,
            "alert_level": CostBudgetManager._level(ratio),
            "action_on_exceed": budget.action_on_exceed,
            "is_active": budget.is_active,
            "description": budget.description,
            "cost_policy": budget.cost_policy,
            "created_at": budget.created_at.isoformat() if budget.created_at else None,
        }
