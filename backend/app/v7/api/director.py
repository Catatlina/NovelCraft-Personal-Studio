"""V7 Director API routes."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ..director.story_director import StoryDirector
from ..brain.novel_brain import NovelBrain
from ..trace.tracer import ExecutionTracer
from ..events.event_bus import EventBus
from .schemas import SuccessResponse

router = APIRouter(prefix="", tags=["v7-director"])


# ── Request Models ───────────────────────────────────────────────────────

class GenerateChapterRequest(BaseModel):
    chapter_number: int
    prompt: str | None = None
    outline: str | None = None


# ── Dependency ───────────────────────────────────────────────────────────

async def get_db() -> AsyncSession:
    """Get database session.
    
    NOTE: Placeholder - replace with actual DB session dependency.
    """
    raise HTTPException(status_code=501, detail="Database session not configured")


def get_director(novel_id: str, db: AsyncSession = Depends(get_db)) -> StoryDirector:
    """Get StoryDirector instance."""
    try:
        novel_uuid = uuid.UUID(novel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid novel_id")
    
    brain = NovelBrain(db, novel_uuid)
    tracer = ExecutionTracer(db, novel_uuid)
    event_bus = EventBus(db, novel_uuid)
    
    return StoryDirector(db, novel_uuid, brain, tracer, event_bus)


# ── Generation ───────────────────────────────────────────────────────────

@router.post("/{novel_id}/generate-chapter")
async def generate_chapter(
    novel_id: str,
    request: GenerateChapterRequest,
    director: StoryDirector = Depends(get_director),
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


@router.post("/{novel_id}/decisions/{decision_id}/approve")
async def approve_decision(
    novel_id: str,
    decision_id: str,
    director: StoryDirector = Depends(get_director),
):
    """Approve a pending decision."""
    # Alpha: Placeholder
    return {"status": "approved", "decision_id": decision_id}


@router.post("/{novel_id}/decisions/{decision_id}/reject")
async def reject_decision(
    novel_id: str,
    decision_id: str,
    director: StoryDirector = Depends(get_director),
):
    """Reject a pending decision."""
    # Alpha: Placeholder
    return {"status": "rejected", "decision_id": decision_id}


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
