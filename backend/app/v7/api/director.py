"""V7 Director API routes."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ..db import get_async_db as get_db
from ..director.story_director import StoryDirector
from ..brain.novel_brain import NovelBrain
from ..trace.tracer import ExecutionTracer
from ..events.event_bus import EventBus
from .schemas import SuccessResponse
from ..human.intervention_service import HumanInterventionService
from .schemas import DecisionReviewResponse, ReviewRequest
from ...core.authz import ProjectContext, require_novel_member_dep

router = APIRouter(
    prefix="",
    tags=["v7-director"],
    dependencies=[Depends(require_novel_member_dep())],
)


# ── Request Models ───────────────────────────────────────────────────────

class GenerateChapterRequest(BaseModel):
    chapter_number: int
    prompt: str | None = None
    outline: str | None = None


# ── Dependency ───────────────────────────────────────────────────────────


def get_director(
    novel_id: str,
    context: ProjectContext = Depends(require_novel_member_dep()),
    db: AsyncSession = Depends(get_db),
) -> StoryDirector:
    """Get StoryDirector instance."""
    try:
        novel_uuid = uuid.UUID(novel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid novel_id")
    
    brain = NovelBrain(db, novel_uuid)
    tracer = ExecutionTracer(db, novel_uuid)
    event_bus = EventBus(db, novel_uuid)
    
    return StoryDirector(
        db,
        novel_uuid,
        brain,
        tracer,
        event_bus,
        project_id=context.project_id,
        user_id=str(context.user.get("id") or ""),
    )


# ── Generation ───────────────────────────────────────────────────────────

@router.post("/{novel_id}/generate-chapter")
async def generate_chapter(
    novel_id: str,
    request: GenerateChapterRequest,
    director: StoryDirector = Depends(get_director),
    _editor: ProjectContext = Depends(require_novel_member_dep("editor")),
):
    """
    Generate a chapter using the Story Director.
    
    This is the main entry point for chapter generation.
    """
    result = await director.generate_chapter(
        request.chapter_number,
        prompt=request.prompt,
        outline=request.outline,
    )
    return result


# ── Decisions ────────────────────────────────────────────────────────────

@router.get("/{novel_id}/decisions/pending")
async def get_pending_decisions(
    novel_id: str,
    director: StoryDirector = Depends(get_director),
):
    """Get decisions pending human approval."""
    decisions = await director.get_decision_queue()
    return {"decisions": decisions, "count": len(decisions)}


@router.post(
    "/{novel_id}/decisions/{decision_id}/approve",
    response_model=DecisionReviewResponse,
)
async def approve_decision(
    novel_id: str,
    decision_id: str,
    request: ReviewRequest | None = None,
    db: AsyncSession = Depends(get_db),
    _editor: ProjectContext = Depends(require_novel_member_dep("editor")),
):
    """Approve a pending decision.

    Flips ``v7_decision_logs.status`` pending -> approved, stamps
    ``decided_by='human'`` and records a human intervention.
    """
    return await _review_decision(novel_id, decision_id, True, request, db)


@router.post(
    "/{novel_id}/decisions/{decision_id}/reject",
    response_model=DecisionReviewResponse,
)
async def reject_decision(
    novel_id: str,
    decision_id: str,
    request: ReviewRequest | None = None,
    db: AsyncSession = Depends(get_db),
    _editor: ProjectContext = Depends(require_novel_member_dep("editor")),
):
    """Reject a pending decision.

    Flips ``v7_decision_logs.status`` pending -> rejected, stamps
    ``decided_by='human'`` and records a human intervention.
    """
    return await _review_decision(novel_id, decision_id, False, request, db)


async def _review_decision(
    novel_id: str,
    decision_id: str,
    approved: bool,
    request: ReviewRequest | None,
    db: AsyncSession,
) -> dict[str, Any]:
    """Shared human approve/reject state transition."""
    try:
        novel_uuid = uuid.UUID(novel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid novel_id")
    try:
        decision_uuid = uuid.UUID(decision_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid decision_id")

    payload = request or ReviewRequest()

    service = HumanInterventionService(db, novel_uuid)
    try:
        return await service.review_decision(
            decision_uuid,
            approved,
            reason=payload.reason,
            user_id=payload.user_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


# ── Status ───────────────────────────────────────────────────────────────

@router.get("/{novel_id}/status")
async def get_director_status(
    novel_id: str,
    director: StoryDirector = Depends(get_director),
):
    """Get director status and capabilities."""
    return {
        "status": "alpha",
        "engines": {
            "plot_engine": director.plot_engine.capability.engine_name,
            "memory_engine": director.memory_engine.capability.engine_name,
            "review_engine": director.review_engine.capability.engine_name,
        },
        "permission_system": "active",
        "notes": "Alpha version - limited functionality",
    }
