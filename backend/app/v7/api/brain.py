"""V7 Brain API routes."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..brain.novel_brain import NovelBrain
from ..human.intervention_service import HumanInterventionService
from .schemas import (
    BrainOverviewResponse,
    StateResponse, StateCreateRequest, StateUpdateRequest, StateUpdateResponse, StateListResponse,
    GoalResponse, GoalCreateRequest, GoalUpdateRequest, GoalTreeResponse,
    ConstraintResponse, ConstraintCreateRequest, ConstraintUpdateRequest,
    VersionResponse, VersionCreateRequest, SnapshotResponse, RollbackRequest, RollbackResponse,
    SnapshotCompareRequest, SnapshotCompareResponse,
    DecisionLogResponse,
    EventResponse,
    SuccessResponse,
    HumanInterventionListResponse, ReviewRequest,
    InstructionRequest, InstructionResponse,
)
from ...core.authz import require_novel_member_dep

router = APIRouter(
    prefix="",
    tags=["v7-brain"],
    dependencies=[Depends(require_novel_member_dep())],
)


# ── Dependency ───────────────────────────────────────────────────────────

from ..db import get_async_db as get_db


def _parse_novel_id(novel_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(novel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid novel_id")


def _parse_optional_uuid(value: str | None, field: str) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {field}")


def _user_uuid(value: str | None) -> uuid.UUID | None:
    """Coerce a caller identity to a UUID, tolerating free-text operator names.

    Non-UUID identities are still recorded by the human layer as
    ``extra_metadata.user_label``, so they must not fail the request.
    """
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def get_brain(novel_id: str, db: AsyncSession = Depends(get_db)) -> NovelBrain:
    """Get NovelBrain instance for a novel."""
    return NovelBrain(db, _parse_novel_id(novel_id))


def get_human(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
) -> HumanInterventionService:
    """Get HumanInterventionService instance for a novel."""
    return HumanInterventionService(db, _parse_novel_id(novel_id))


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


@router.post(
    "/{novel_id}/states",
    response_model=StateUpdateResponse,
    dependencies=[Depends(require_novel_member_dep("editor"))],
)
async def create_state(
    request: StateCreateRequest,
    brain: NovelBrain = Depends(get_brain),
    human: HumanInterventionService = Depends(get_human),
):
    """Create or update a state."""
    existing = await brain.state.state_repo.get_by_key(
        brain.novel_id, request.state_type, request.state_key
    )
    old_value = existing.state_value if existing else None

    result = await brain.state.update_state(
        request.state_type,
        request.state_key,
        request.state_value,
        request.confidence,
        source=request.source,
        reason=request.reason,
    )

    # Any human-sourced write is an intervention and must be auditable.
    if request.source.startswith("human"):
        state_info = result.get("state") or {}
        await human.record_state_edit(
            _parse_optional_uuid(state_info.get("id"), "state_id"),
            state_type=request.state_type,
            state_key=request.state_key,
            old_value=old_value,
            new_value=request.state_value,
            reason=request.reason,
        )

    return result


@router.put(
    "/{novel_id}/states/{state_id}",
    response_model=StateUpdateResponse,
    dependencies=[Depends(require_novel_member_dep("editor"))],
)
async def update_state(
    state_id: str,
    request: StateUpdateRequest,
    brain: NovelBrain = Depends(get_brain),
    human: HumanInterventionService = Depends(get_human),
):
    """Update a state manually (human edit, always recorded as intervention)."""
    try:
        state_uuid = uuid.UUID(state_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid state_id")

    state = await brain.state.state_repo.get(state_uuid)
    if not state or state.novel_id != brain.novel_id:
        raise HTTPException(status_code=404, detail="State not found")

    if request.state_value is None and request.confidence is None:
        raise HTTPException(
            status_code=400,
            detail="At least one of state_value / confidence must be provided",
        )

    old_value = state.state_value
    new_value = request.state_value if request.state_value is not None else state.state_value
    # A manual edit is authoritative unless the caller lowers confidence explicitly.
    new_confidence = request.confidence if request.confidence is not None else 1.0

    result = await brain.state.update_state(
        state.state_type,
        state.state_key,
        new_value,
        new_confidence,
        source="human_set",
        reason=request.reason or "Human manual edit",
    )

    state_info = result.get("state") or {}
    await human.record_state_edit(
        _parse_optional_uuid(state_info.get("id"), "state_id") or state_uuid,
        state_type=state.state_type,
        state_key=state.state_key,
        old_value=old_value,
        new_value=new_value,
        reason=request.reason,
    )

    return result


@router.post(
    "/{novel_id}/states/{state_id}/approve",
    response_model=dict,
    dependencies=[Depends(require_novel_member_dep("editor"))],
)
async def approve_state(
    state_id: str,
    request: ReviewRequest | None = None,
    brain: NovelBrain = Depends(get_brain),
    human: HumanInterventionService = Depends(get_human),
):
    """Approve a pending review state."""
    try:
        state_uuid = uuid.UUID(state_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid state_id")

    state = await brain.state.state_repo.get(state_uuid)
    if not state or state.novel_id != brain.novel_id:
        raise HTTPException(status_code=404, detail="State not found")

    payload = request or ReviewRequest()
    user_uuid = _user_uuid(payload.user_id)
    old_value = {
        "is_pending_review": state.is_pending_review,
        "confidence": state.confidence,
    }
    state_type, state_key = state.state_type, state.state_key

    result = await brain.state.approve_state(
        state_uuid, user_id=user_uuid, reason=payload.reason
    )

    await human.record_state_review(
        state_uuid,
        True,
        state_type=state_type,
        state_key=state_key,
        old_value=old_value,
        new_value=result,
        reason=payload.reason,
        user_id=payload.user_id,
    )
    return result


@router.post(
    "/{novel_id}/states/{state_id}/reject",
    response_model=dict,
    dependencies=[Depends(require_novel_member_dep("editor"))],
)
async def reject_state(
    state_id: str,
    request: ReviewRequest | None = None,
    brain: NovelBrain = Depends(get_brain),
    human: HumanInterventionService = Depends(get_human),
):
    """Reject a pending review state."""
    try:
        state_uuid = uuid.UUID(state_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid state_id")

    state = await brain.state.state_repo.get(state_uuid)
    if not state or state.novel_id != brain.novel_id:
        raise HTTPException(status_code=404, detail="State not found")

    payload = request or ReviewRequest()
    user_uuid = _user_uuid(payload.user_id)
    old_value = {"is_active": state.is_active, "value": state.state_value}
    state_type, state_key = state.state_type, state.state_key

    result = await brain.state.reject_state(
        state_uuid, user_id=user_uuid, reason=payload.reason
    )

    await human.record_state_review(
        state_uuid,
        False,
        state_type=state_type,
        state_key=state_key,
        old_value=old_value,
        new_value=result,
        reason=payload.reason,
        user_id=payload.user_id,
    )
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


@router.post(
    "/{novel_id}/goals",
    response_model=GoalResponse,
    dependencies=[Depends(require_novel_member_dep("editor"))],
)
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


@router.put(
    "/{novel_id}/goals/{goal_id}",
    response_model=GoalResponse,
    dependencies=[Depends(require_novel_member_dep("editor"))],
)
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


@router.delete(
    "/{novel_id}/goals/{goal_id}",
    response_model=SuccessResponse,
    dependencies=[Depends(require_novel_member_dep("editor"))],
)
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


@router.post(
    "/{novel_id}/constraints",
    response_model=ConstraintResponse,
    dependencies=[Depends(require_novel_member_dep("editor"))],
)
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


@router.put(
    "/{novel_id}/constraints/{constraint_id}",
    response_model=ConstraintResponse,
    dependencies=[Depends(require_novel_member_dep("editor"))],
)
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


@router.delete(
    "/{novel_id}/constraints/{constraint_id}",
    response_model=SuccessResponse,
    dependencies=[Depends(require_novel_member_dep("editor"))],
)
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


@router.post(
    "/{novel_id}/versions",
    response_model=VersionResponse,
    dependencies=[Depends(require_novel_member_dep("editor"))],
)
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


@router.post(
    "/{novel_id}/snapshots",
    response_model=SnapshotResponse,
    dependencies=[Depends(require_novel_member_dep("editor"))],
)
async def create_snapshot(
    brain: NovelBrain = Depends(get_brain),
):
    """Create a new snapshot."""
    return await brain.versions.create_snapshot(
        description="Manual snapshot",
        created_by="human",
    )


@router.get("/{novel_id}/snapshots/{snapshot_id}", response_model=dict)
async def get_snapshot(
    snapshot_id: str,
    brain: NovelBrain = Depends(get_brain),
):
    """Get a snapshot with its full state payload."""
    try:
        snapshot_uuid = uuid.UUID(snapshot_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid snapshot_id")

    snapshot = await brain.versions.get_snapshot(snapshot_uuid)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snapshot


@router.post(
    "/{novel_id}/snapshots/compare",
    response_model=SnapshotCompareResponse,
    dependencies=[Depends(require_novel_member_dep("editor"))],
)
async def compare_snapshots(
    request: SnapshotCompareRequest,
    brain: NovelBrain = Depends(get_brain),
):
    """Compare two snapshots and return their state differences."""
    try:
        a_uuid = uuid.UUID(request.snapshot_a_id)
        b_uuid = uuid.UUID(request.snapshot_b_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid snapshot id")

    try:
        return await brain.versions.compare_snapshots(a_uuid, b_uuid)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/{novel_id}/rollback",
    response_model=RollbackResponse,
    dependencies=[Depends(require_novel_member_dep("editor"))],
)
async def rollback_to_snapshot(
    request: RollbackRequest,
    brain: NovelBrain = Depends(get_brain),
    human: HumanInterventionService = Depends(get_human),
):
    """Rollback story state to a snapshot (real state restoration)."""
    try:
        snapshot_uuid = uuid.UUID(request.snapshot_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid snapshot_id")

    try:
        result = await brain.versions.rollback_to_snapshot(
            snapshot_uuid,
            reason=request.reason,
        )
    except ValueError as exc:
        await human.record_rollback(
            snapshot_uuid,
            reason=request.reason,
            result="failed",
        )
        raise HTTPException(status_code=404, detail=str(exc))

    await human.record_rollback(
        snapshot_uuid,
        version_id=uuid.UUID(result["version_id"]),
        restored_states=result["restored_states"],
        deactivated_states=result["deactivated_states"],
        safety_snapshot_id=uuid.UUID(result["safety_snapshot_id"]),
        reason=request.reason,
    )
    return result


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


# ── Human Interventions ──────────────────────────────────────────────────

@router.get("/{novel_id}/interventions", response_model=HumanInterventionListResponse)
async def list_interventions(
    intervention_type: str | None = Query(None),
    target_type: str | None = Query(None),
    target_id: str | None = Query(None),
    result: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    human: HumanInterventionService = Depends(get_human),
):
    """List every human intervention recorded for this novel."""
    target_uuid = _parse_optional_uuid(target_id, "target_id")

    items = await human.list_interventions(
        intervention_type=intervention_type,
        target_type=target_type,
        target_id=target_uuid,
        result=result,
        skip=skip,
        limit=limit,
    )
    total = await human.count_interventions(
        intervention_type=intervention_type,
        target_type=target_type,
        target_id=target_uuid,
        result=result,
    )
    stats = await human.get_stats()
    return {"items": items, "total": total, "stats": stats}


@router.post(
    "/{novel_id}/instructions",
    response_model=InstructionResponse,
    dependencies=[Depends(require_novel_member_dep("editor"))],
)
async def inject_instruction(
    request: InstructionRequest,
    human: HumanInterventionService = Depends(get_human),
):
    """Inject a human instruction consumed by the next generation run."""
    try:
        return await human.inject_instruction(
            request.instruction,
            scope=request.scope,
            target_chapter=request.target_chapter,
            priority=request.priority,
            reason=request.reason,
            user_id=request.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{novel_id}/instructions", response_model=dict)
async def list_instructions(
    target_chapter: int | None = Query(None),
    human: HumanInterventionService = Depends(get_human),
):
    """List pending human instructions awaiting the next generation run."""
    pending = await human.get_pending_instructions(target_chapter=target_chapter)
    return {"pending": pending, "count": len(pending)}
