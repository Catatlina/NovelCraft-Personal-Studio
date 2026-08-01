"""V7 Cost API routes."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_async_db as get_db
from ..cost.cost_manager import CostBudgetManager
from .schemas import (
    BudgetCreateRequest,
    BudgetUpdateRequest,
    CostRecordRequest,
    SuccessResponse,
)

router = APIRouter(prefix="", tags=["v7-cost"])


# ── Dependency ───────────────────────────────────────────────────────────


def get_cost_manager(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
) -> CostBudgetManager:
    """Get CostBudgetManager instance for a novel."""
    try:
        novel_uuid = uuid.UUID(novel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid novel_id")
    return CostBudgetManager(db, novel_uuid)


def _parse_budget_id(budget_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(budget_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid budget_id")


# ── Budgets ──────────────────────────────────────────────────────────────

@router.get("/{novel_id}/budgets", response_model=list[dict])
async def list_budgets(
    budget_type: str | None = Query(None),
    budget_scope: str | None = Query(None),
    is_active: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    manager: CostBudgetManager = Depends(get_cost_manager),
):
    """List cost budgets."""
    return await manager.list_budgets(
        budget_type=budget_type,
        budget_scope=budget_scope,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )


@router.post("/{novel_id}/budgets", response_model=dict)
async def create_budget(
    request: BudgetCreateRequest,
    manager: CostBudgetManager = Depends(get_cost_manager),
):
    """Create a cost budget."""
    try:
        return await manager.create_budget(
            request.budget_type,
            request.budget_scope,
            request.limit_cny,
            limit_tokens=request.limit_tokens,
            period_days=request.period_days,
            action_on_exceed=request.action_on_exceed,
            description=request.description,
            cost_policy=request.cost_policy,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{novel_id}/budgets/{budget_id}", response_model=dict)
async def get_budget(
    budget_id: str,
    manager: CostBudgetManager = Depends(get_cost_manager),
):
    """Get one cost budget."""
    budget = await manager.get_budget(_parse_budget_id(budget_id))
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    return budget


@router.put("/{novel_id}/budgets/{budget_id}", response_model=dict)
async def update_budget(
    budget_id: str,
    request: BudgetUpdateRequest,
    manager: CostBudgetManager = Depends(get_cost_manager),
):
    """Update a cost budget."""
    try:
        budget = await manager.update_budget(
            _parse_budget_id(budget_id),
            request.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    return budget


@router.delete("/{novel_id}/budgets/{budget_id}", response_model=SuccessResponse)
async def delete_budget(
    budget_id: str,
    manager: CostBudgetManager = Depends(get_cost_manager),
):
    """Deactivate a cost budget (soft delete)."""
    ok = await manager.delete_budget(_parse_budget_id(budget_id))
    if not ok:
        raise HTTPException(status_code=404, detail="Budget not found")
    return SuccessResponse(message="Budget deactivated")


@router.post("/{novel_id}/budgets/{budget_id}/reset", response_model=dict)
async def reset_budget(
    budget_id: str,
    manager: CostBudgetManager = Depends(get_cost_manager),
):
    """Reset a budget's spend counters and alert flags."""
    budget = await manager.reset_budget(_parse_budget_id(budget_id))
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    return budget


# ── Live budget state ────────────────────────────────────────────────────

@router.get("/{novel_id}/remaining", response_model=dict)
async def get_remaining(
    manager: CostBudgetManager = Depends(get_cost_manager),
):
    """Live remaining budget."""
    return await manager.get_remaining()


@router.get("/{novel_id}/check", response_model=dict)
async def check_budget(
    estimated_cost_cny: float = Query(0.0, ge=0),
    estimated_tokens: int = Query(0, ge=0),
    budget_type: str | None = Query(None),
    manager: CostBudgetManager = Depends(get_cost_manager),
):
    """Check whether an upcoming operation would breach a budget."""
    return await manager.check_budget(
        estimated_cost_cny=estimated_cost_cny,
        estimated_tokens=estimated_tokens,
        budget_type=budget_type,
    )


@router.post("/{novel_id}/record", response_model=dict)
async def record_cost(
    request: CostRecordRequest,
    manager: CostBudgetManager = Depends(get_cost_manager),
):
    """Record real spend against the active budgets."""
    run_uuid = None
    if request.run_id:
        try:
            run_uuid = uuid.UUID(request.run_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid run_id")

    try:
        return await manager.record_cost(
            cost_cny=request.cost_cny,
            tokens=request.tokens,
            budget_type=request.budget_type,
            run_id=run_uuid,
            source=request.source,
            description=request.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── Statistics ───────────────────────────────────────────────────────────

@router.get("/{novel_id}/summary", response_model=dict)
async def get_summary(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    manager: CostBudgetManager = Depends(get_cost_manager),
):
    """Budget state plus actual recorded spend."""
    return await manager.get_summary(start_date=start_date, end_date=end_date)


@router.get("/{novel_id}/stats/daily", response_model=dict)
async def get_stats_by_date(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    manager: CostBudgetManager = Depends(get_cost_manager),
):
    """Actual spend grouped by calendar date."""
    return await manager.get_stats_by_date(start_date=start_date, end_date=end_date)


@router.get("/{novel_id}/stats/task-type", response_model=dict)
async def get_stats_by_task_type(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    manager: CostBudgetManager = Depends(get_cost_manager),
):
    """Actual spend grouped by task type."""
    return await manager.get_stats_by_task_type(
        start_date=start_date, end_date=end_date
    )
