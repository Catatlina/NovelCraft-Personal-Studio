"""V7 Trace API routes."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..trace.tracer import ExecutionTracer
from .schemas import RunResponse, TraceStepResponse, SuccessResponse

router = APIRouter(prefix="/v7/trace", tags=["v7-trace"])


# ── Dependency ───────────────────────────────────────────────────────────

async def get_db() -> AsyncSession:
    """Get database session.
    
    NOTE: Placeholder - replace with actual DB session dependency.
    """
    raise HTTPException(status_code=501, detail="Database session not configured")


def get_tracer(novel_id: str, db: AsyncSession = Depends(get_db)) -> ExecutionTracer:
    """Get ExecutionTracer instance for a novel."""
    try:
        novel_uuid = uuid.UUID(novel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid novel_id")
    return ExecutionTracer(db, novel_uuid)


# ── Runs ─────────────────────────────────────────────────────────────────

@router.get("/{novel_id}/runs", response_model=list[RunResponse])
async def list_runs(
    novel_id: str,
    run_type: str | None = Query(None),
    status: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    tracer: ExecutionTracer = Depends(get_tracer),
):
    """List agent runs."""
    return await tracer.list_runs(
        run_type=run_type,
        status=status,
        skip=skip,
        limit=limit,
    )


@router.get("/{novel_id}/runs/{run_id}", response_model=RunResponse)
async def get_run(
    novel_id: str,
    run_id: str,
    tracer: ExecutionTracer = Depends(get_tracer),
):
    """Get run details."""
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id")
    
    run = await tracer.get_run(run_uuid)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/{novel_id}/runs", response_model=dict)
async def start_run(
    novel_id: str,
    run_type: str = Query(..., description="Run type: chapter_generation/review/analysis"),
    trigger: str = Query("manual"),
    chapter_number: int | None = Query(None),
    tracer: ExecutionTracer = Depends(get_tracer),
):
    """Start a new agent run."""
    run_id = await tracer.start_run(
        run_type,
        trigger=trigger,
        chapter_number=chapter_number,
    )
    return {"run_id": str(run_id), "status": "started"}


@router.post("/{novel_id}/runs/{run_id}/complete", response_model=RunResponse)
async def complete_run(
    novel_id: str,
    run_id: str,
    tracer: ExecutionTracer = Depends(get_tracer),
):
    """Complete a run."""
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id")
    
    return await tracer.complete_run(run_uuid)


# ── Trace Steps ──────────────────────────────────────────────────────────

@router.get("/{novel_id}/runs/{run_id}/steps", response_model=list[TraceStepResponse])
async def list_trace_steps(
    novel_id: str,
    run_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    tracer: ExecutionTracer = Depends(get_tracer),
):
    """List trace steps for a run."""
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id")
    
    return await tracer.get_trace_steps(run_uuid, skip=skip, limit=limit)
