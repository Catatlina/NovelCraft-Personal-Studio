"""V7 Prompt version API routes.

``v7_prompt_versions`` is a global table (templates are shared across novels),
so version routes are not novel-scoped. Execution routes accept an optional
``novel_id`` query parameter for scoping.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_async_db as get_db
from ..prompt.prompt_manager import PromptVersionManager, compute_prompt_hash
from .schemas import (
    PromptChangeDetectRequest,
    PromptExecutionCreateRequest,
    PromptVersionCreateRequest,
)

router = APIRouter(prefix="", tags=["v7-prompt"])


# ── Helpers ──────────────────────────────────────────────────────────────


def _parse_uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {field}")


def _parse_optional_uuid(value: str | None, field: str) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    return _parse_uuid(value, field)


def get_prompt_manager(
    novel_id: str | None = Query(None, description="Scope execution records"),
    db: AsyncSession = Depends(get_db),
) -> PromptVersionManager:
    """Get PromptVersionManager (novel_id optional — versions are global)."""
    return PromptVersionManager(db, _parse_optional_uuid(novel_id, "novel_id"))


# ── Prompt names ─────────────────────────────────────────────────────────

@router.get("/names", response_model=dict)
async def list_prompt_names(
    manager: PromptVersionManager = Depends(get_prompt_manager),
):
    """List every registered prompt name."""
    names = await manager.list_prompt_names()
    return {"total": len(names), "prompt_names": names}


# ── Versions ─────────────────────────────────────────────────────────────

@router.get("/versions", response_model=dict)
async def list_versions(
    prompt_name: str | None = Query(None),
    is_active: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    manager: PromptVersionManager = Depends(get_prompt_manager),
):
    """List prompt versions."""
    versions = await manager.list_versions(
        prompt_name=prompt_name,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    total = await manager.count_versions(
        prompt_name=prompt_name, is_active=is_active
    )
    return {"total": total, "skip": skip, "limit": limit, "versions": versions}


@router.post("/versions", response_model=dict)
async def register_version(
    request: PromptVersionCreateRequest,
    manager: PromptVersionManager = Depends(get_prompt_manager),
):
    """Register a prompt version — a new row is created only on content change."""
    try:
        return await manager.register_version(
            request.prompt_name,
            request.template,
            model=request.model,
            parameters=request.parameters,
            output_schema=request.output_schema,
            description=request.description,
            change_notes=request.change_notes,
            created_by=request.created_by,
            make_default=request.make_default,
            force_new=request.force_new,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/versions/detect-change", response_model=dict)
async def detect_change(
    request: PromptChangeDetectRequest,
    manager: PromptVersionManager = Depends(get_prompt_manager),
):
    """Hash a candidate template and compare it with the registered versions."""
    return await manager.detect_change(
        request.prompt_name,
        request.template,
        model=request.model,
        parameters=request.parameters,
        output_schema=request.output_schema,
    )


@router.post("/versions/hash", response_model=dict)
async def hash_prompt(request: PromptChangeDetectRequest):
    """Compute the deterministic prompt hash without touching the database."""
    return {
        "prompt_name": request.prompt_name,
        "prompt_hash": compute_prompt_hash(
            request.template,
            model=request.model,
            parameters=request.parameters,
            output_schema=request.output_schema,
        ),
    }


@router.get("/versions/active/{prompt_name}", response_model=dict)
async def get_active_version(
    prompt_name: str,
    manager: PromptVersionManager = Depends(get_prompt_manager),
):
    """Get the version currently in use for a prompt name."""
    version = await manager.get_active_version(prompt_name)
    if not version:
        raise HTTPException(
            status_code=404, detail=f"No active version for '{prompt_name}'"
        )
    return version


@router.get("/versions/{version_id}", response_model=dict)
async def get_version(
    version_id: str,
    manager: PromptVersionManager = Depends(get_prompt_manager),
):
    """Get one prompt version, including its template."""
    version = await manager.get_version(_parse_uuid(version_id, "version_id"))
    if not version:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    return version


@router.post("/versions/{version_id}/default", response_model=dict)
async def set_default_version(
    version_id: str,
    manager: PromptVersionManager = Depends(get_prompt_manager),
):
    """Make a version the default for its prompt name."""
    version = await manager.set_default(_parse_uuid(version_id, "version_id"))
    if not version:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    return version


@router.post("/versions/{version_id}/deactivate", response_model=dict)
async def deactivate_version(
    version_id: str,
    manager: PromptVersionManager = Depends(get_prompt_manager),
):
    """Deactivate a version without deleting it."""
    version = await manager.deactivate_version(_parse_uuid(version_id, "version_id"))
    if not version:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    return version


# ── Executions ───────────────────────────────────────────────────────────

@router.post("/executions", response_model=dict)
async def record_execution(
    request: PromptExecutionCreateRequest,
    manager: PromptVersionManager = Depends(get_prompt_manager),
):
    """Record one prompt execution bound to a concrete prompt version."""
    try:
        return await manager.record_execution(
            request.prompt_name,
            prompt_version_id=_parse_optional_uuid(
                request.prompt_version_id, "prompt_version_id"
            ),
            version=request.version,
            input_variables=request.input_variables,
            rendered_prompt=request.rendered_prompt,
            output=request.output,
            output_raw=request.output_raw,
            model=request.model,
            tokens_input=request.tokens_input,
            tokens_output=request.tokens_output,
            cost=request.cost,
            duration_seconds=request.duration_seconds,
            status=request.status,
            error_message=request.error_message,
            run_id=_parse_optional_uuid(request.run_id, "run_id"),
            step_id=_parse_optional_uuid(request.step_id, "step_id"),
            novel_id=_parse_optional_uuid(request.novel_id, "novel_id"),
            validation_passed=request.validation_passed,
            validation_errors=request.validation_errors,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/executions", response_model=dict)
async def list_executions(
    prompt_name: str | None = Query(None),
    prompt_version_id: str | None = Query(None),
    status: str | None = Query(None),
    run_id: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    manager: PromptVersionManager = Depends(get_prompt_manager),
):
    """List prompt execution records."""
    executions = await manager.get_execution_history(
        prompt_name=prompt_name,
        prompt_version_id=_parse_optional_uuid(
            prompt_version_id, "prompt_version_id"
        ),
        status=status,
        run_id=_parse_optional_uuid(run_id, "run_id"),
        novel_scoped=manager.novel_id is not None,
        skip=skip,
        limit=limit,
    )
    return {
        "novel_id": str(manager.novel_id) if manager.novel_id else None,
        "count": len(executions),
        "skip": skip,
        "limit": limit,
        "executions": executions,
    }


@router.get("/executions/stats/{prompt_name}", response_model=dict)
async def get_execution_stats(
    prompt_name: str,
    manager: PromptVersionManager = Depends(get_prompt_manager),
):
    """Per-version execution statistics for a prompt."""
    return await manager.get_execution_stats(
        prompt_name, novel_scoped=manager.novel_id is not None
    )
