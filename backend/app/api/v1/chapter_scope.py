"""Legacy chapter scope reconciliation endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ...core.authz import ensure_project_member, ok
from ...core.security import get_current_user
from ...db import connect
from ...services.chapter_scope import (
    ChapterScopeError,
    bind_legacy_chapter,
    list_legacy_resolutions,
    scan_legacy_chapters,
    scope_summary,
)


router = APIRouter(prefix="/api/v1/chapter-scope", tags=["chapter-scope"])


class LegacyScanRequest(BaseModel):
    project_id: str = Field(min_length=1)
    apply: bool = False
    auto_bind: bool = True


class LegacyBindRequest(BaseModel):
    novel_id: str = Field(min_length=1)


def _require_write(db: Any, project_id: str, user: dict[str, Any]) -> None:
    ensure_project_member(db, project_id, user, {"owner", "editor"})


@router.get("/summary")
def get_scope_summary(project_id: str = Query(..., min_length=1), user: dict = Depends(get_current_user)):
    db = connect()
    try:
        _require_write(db, project_id, user)
        return ok(scope_summary(db, project_id=project_id))
    finally:
        db.close()


@router.get("/resolutions")
def get_scope_resolutions(
    project_id: str = Query(..., min_length=1),
    status: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    db = connect()
    try:
        _require_write(db, project_id, user)
        return ok({"items": list_legacy_resolutions(db, project_id=project_id, status=status)})
    finally:
        db.close()


@router.post("/scan")
def scan_scope(payload: LegacyScanRequest, user: dict = Depends(get_current_user)):
    """Dry-run by default; apply only records scope states and safe bindings."""
    db = connect()
    try:
        _require_write(db, payload.project_id, user)
        result = scan_legacy_chapters(
            db,
            project_id=payload.project_id,
            apply=payload.apply,
            auto_bind=payload.auto_bind,
        )
        return ok(result)
    except ChapterScopeError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": exc.message, **exc.details},
        ) from exc
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/chapters/{chapter_id}/bind")
def bind_scope(
    chapter_id: str,
    payload: LegacyBindRequest,
    user: dict = Depends(get_current_user),
):
    db = connect()
    try:
        chapter = db.execute(
            "SELECT project_id FROM contents WHERE id=%s AND is_deleted=FALSE",
            (chapter_id,),
        ).fetchone()
        if not chapter:
            raise HTTPException(status_code=404, detail="chapter not found")
        _require_write(db, str(chapter["project_id"]), user)
        result = bind_legacy_chapter(
            db,
            chapter_id=chapter_id,
            novel_id=payload.novel_id,
            user_id=str(user.get("id") or "") or None,
        )
        db.commit()
        return ok(result)
    except ChapterScopeError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": exc.message, **exc.details},
        ) from exc
    finally:
        db.close()
