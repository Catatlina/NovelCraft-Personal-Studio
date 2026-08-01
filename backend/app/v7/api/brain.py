"""V7 Brain API routes."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..brain.novel_brain import NovelBrain
from .schemas import (
    BrainOverviewResponse,
    StateResponse, StateCreateRequest, StateUpdateRequest, StateUpdateResponse, StateListResponse,
    GoalResponse, GoalCreateRequest, GoalUpdateRequest, GoalTreeResponse,
    ConstraintResponse, ConstraintCreateRequest, ConstraintUpdateRequest,
    VersionResponse, VersionCreateRequest, SnapshotResponse, RollbackRequest, RollbackResponse,
    DecisionLogResponse,
    EventResponse,
    SuccessResponse,
)

router = APIRouter(prefix="", tags=["v7-brain"])


# ── Dependency ───────────────────────────────────────────────────────────

from ..db import get_async_db as get_db


def get_brain(novel_id: str, db: AsyncSession = Depends(get_db)) -> NovelBrain:
    """Get NovelBrain instance for a novel."""
    try:
        novel_uuid = uuid.UUID(novel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid novel_id")
    return NovelBrain(db, novel_uuid)


# ── Overview ─────────────────────────────────────────────────────────────

@router.get("/{novel_id}/overview", response_model=BrainOverviewResponse)
async def get_overview(brain: NovelBrain = Depends(get_brain)):
    """Get brain overview statistics."""
    return await brain.get_overview()


# ── Story States ─────────────────────────────────────────────────────────

@router.get("/{novel_id}/states", response_model=StateListResponse)
async def list_states(
    state_type: str = Query(..., description="State type: global/character/world/plot/reader"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    brain: NovelBrain = Depends(get_brain),
):
    """List states by type."""
    states = await brain.state.list_states(state_type, skip=skip, limit=limit)
    return {
        "items": states,
        "total": len(states),  # TODO: add actual count
    }


@router.post("/{novel_id}/states", response_model=StateUpdateResponse)
async def create_state(
    request: StateCreateRequest,
    brain: NovelBrain = Depends(get_brain),
):
    """Create or update a state."""
    result = await brain.state.update_state(
        request.state_type,
        request.state_key,
        request.state_value,
        request.confidence,
        source=request.source,
        reason=request.reason,
    )
    return result


@router.put("/{novel_id}/states/{state_id}", response_model=StateResponse)
async def update_state(
    state_id: str,
    request: StateUpdateRequest,
    brain: NovelBrain = Depends(get_brain),
):
    """Update a state."""
    # TODO: implement state update with confidence gating
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/{novel_id}/states/{state_id}/approve", response_model=StateResponse)
async def approve_state(
    state_id: str,
    brain: NovelBrain = Depends(get_brain),
):
    """Approve a pending review state."""
    try:
        state_uuid = uuid.UUID(state_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid state_id")
    
    result = await brain.state.approve_state(state_uuid)
    return result


@router.post("/{novel_id}/states/{state_id}/reject", response_model=StateResponse)
async def reject_state(
    state_id: str,
    brain: NovelBrain = Depends(get_brain),
):
    """Reject a pending review state."""
    try:
        state_uuid = uuid.UUID(state_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid state_id")
    
    result = await brain.state.reject_state(state_uuid)
    return result


@router.get("/{novel_id}/states/pending-review", response_model=list[dict])
async def list_pending_review(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    brain: NovelBrain = Depends(get_brain),
):
    """List states pending review."""
    return await brain.state.get_pending_review(skip=skip, limit=limit)


@router.get("/{novel_id}/states/{state_id}/changes", response_model=list[dict])
async def get_state_changes(
    state_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    brain: NovelBrain = Depends(get_brain),
):
    """Get state change history."""
    try:
        state_uuid = uuid.UUID(state_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid state_id")
    
    return await brain.state.get_state_changes(state_uuid, skip=skip, limit=limit)


# ── Goals ────────────────────────────────────────────────────────────────

@router.get("/{novel_id}/goals", response_model=list[GoalResponse])
async def list_goals(
    goal_type: str | None = Query(None),
    status: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    brain: NovelBrain = Depends(get_brain),
):
    """List goals."""
    return await brain.goals.list_goals(
        goal_type=goal_type, status=status, skip=skip, limit=limit
    )


@router.get("/{novel_id}/goals/tree", response_model=GoalTreeResponse)
async def get_goal_tree(
    goal_type: str | None = Query(None),
    brain: NovelBrain = Depends(get_brain),
):
    """Get goal tree structure."""
    tree = await brain.goals.get_goal_tree(goal_type=goal_type)
    return {"tree": tree}


@router.post("/{novel_id}/goals", response_model=GoalResponse)
async def create_goal(
    request: GoalCreateRequest,
    brain: NovelBrain = Depends(get_brain),
):
    """Create a new goal."""
    parent_id = uuid.UUID(request.parent_goal_id) if request.parent_goal_id else None
    return await brain.goals.create_goal(
        request.goal_type,
        request.goal_name,
        description=request.description,
        parent_goal_id=parent_id,
        goal_order=request.goal_order,
        target_chapter=request.target_chapter,
        priority=request.priority,
        confidence=request.confidence,
        metadata=request.metadata,
    )


@router.put("/{novel_id}/goals/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: str,
    request: GoalUpdateRequest,
    brain: NovelBrain = Depends(get_brain),
):
    """Update a goal."""
    try:
        goal_uuid = uuid.UUID(goal_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid goal_id")
    
    data = request.model_dump(exclude_unset=True)
    return await brain.goals.update_goal(goal_uuid, data)


@router.delete("/{novel_id}/goals/{goal_id}", response_model=SuccessResponse)
async def delete_goal(
    goal_id: str,
    brain: NovelBrain = Depends(get_brain),
):
    """Delete a goal (soft delete)."""
    try:
        goal_uuid = uuid.UUID(goal_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid goal_id")
    
    await brain.goals.delete_goal(goal_uuid)
    return SuccessResponse(message="Goal deleted")


# ── Constraints ──────────────────────────────────────────────────────────

@router.get("/{novel_id}/constraints", response_model=list[ConstraintResponse])
async def list_constraints(
    constraint_type: str | None = Query(None),
    severity: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    brain: NovelBrain = Depends(get_brain),
):
    """List constraints."""
    return await brain.constraints.list_constraints(
        constraint_type=constraint_type, severity=severity, skip=skip, limit=limit
    )


@router.post("/{novel_id}/constraints", response_model=ConstraintResponse)
async def create_constraint(
    request: ConstraintCreateRequest,
    brain: NovelBrain = Depends(get_brain),
):
    """Create a new constraint."""
    return await brain.constraints.create_constraint(
        request.constraint_type,
        request.constraint_name,
        request.constraint_value,
        description=request.description,
        severity=request.severity,
        check_method=request.check_method,
        priority=request.priority,
    )


@router.put("/{novel_id}/constraints/{constraint_id}", response_model=ConstraintResponse)
async def update_constraint(
    constraint_id: str,
    request: ConstraintUpdateRequest,
    brain: NovelBrain = Depends(get_brain),
):
    """Update a constraint."""
    try:
        constraint_uuid = uuid.UUID(constraint_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid constraint_id")
    
    data = request.model_dump(exclude_unset=True)
    return await brain.constraints.update_constraint(constraint_uuid, data)


@router.delete("/{novel_id}/constraints/{constraint_id}", response_model=SuccessResponse)
async def delete_constraint(
    constraint_id: str,
    brain: NovelBrain = Depends(get_brain),
):
    """Delete a constraint (soft delete)."""
    try:
        constraint_uuid = uuid.UUID(constraint_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid constraint_id")
    
    await brain.constraints.delete_constraint(constraint_uuid)
    return SuccessResponse(message="Constraint deleted")


# ── Versions ─────────────────────────────────────────────────────────────

@router.get("/{novel_id}/versions", response_model=list[VersionResponse])
async def list_versions(
    branch_name: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    brain: NovelBrain = Depends(get_brain),
):
    """List versions."""
    return await brain.versions.list_versions(
        branch_name=branch_name, skip=skip, limit=limit
    )


@router.post("/{novel_id}/versions", response_model=VersionResponse)
async def create_version(
    request: VersionCreateRequest,
    brain: NovelBrain = Depends(get_brain),
):
    """Create a new version."""
    return await brain.versions.create_version(
        version_type=request.version_type,
        description=request.description,
        branch_name=request.branch_name,
        tag_name=request.tag_name,
        created_by="human",
    )


@router.get("/{novel_id}/snapshots", response_model=list[SnapshotResponse])
async def list_snapshots(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    brain: NovelBrain = Depends(get_brain),
):
    """List snapshots."""
    return await brain.versions.list_snapshots(skip=skip, limit=limit)


@router.post("/{novel_id}/snapshots", response_model=SnapshotResponse)
async def create_snapshot(
    brain: NovelBrain = Depends(get_brain),
):
    """Create a new snapshot."""
    return await brain.versions.create_snapshot(
        description="Manual snapshot",
        created_by="human",
    )


@router.post("/{novel_id}/rollback", response_model=RollbackResponse)
async def rollback_to_snapshot(
    request: RollbackRequest,
    brain: NovelBrain = Depends(get_brain),
):
    """Rollback to a snapshot."""
    try:
        snapshot_uuid = uuid.UUID(request.snapshot_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid snapshot_id")
    
    return await brain.versions.rollback_to_snapshot(
        snapshot_uuid,
        reason=request.reason,
    )


# ── Decisions ────────────────────────────────────────────────────────────

@router.get("/{novel_id}/decisions", response_model=list[DecisionLogResponse])
async def list_decisions(
    decision_type: str | None = Query(None),
    status: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    brain: NovelBrain = Depends(get_brain),
):
    """List decision logs."""
    return await brain.get_decision_logs(
        decision_type=decision_type, status=status, skip=skip, limit=limit
    )


# ── Events ───────────────────────────────────────────────────────────────

@router.get("/{novel_id}/events", response_model=list[EventResponse])
async def list_events(
    event_type: str | None = Query(None),
    event_category: str | None = Query(None),
    severity: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    brain: NovelBrain = Depends(get_brain),
):
    """List event log."""
    return await brain.get_events(
        event_type=event_type,
        event_category=event_category,
        severity=severity,
        skip=skip,
        limit=limit,
    )
