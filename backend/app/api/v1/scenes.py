"""V3-P3-⑪: 场景层 Scene + Scene Director API。

- POST /chapters/{chapter_id}/scene-direct  触发 Scene Director 异步规划分镜
- GET  /chapters/{chapter_id}/scenes        读取本章场景分镜
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.db import connect, row_to_dict
from app.services import scene_director
from app.services.chapter_scope import ChapterScopeError, require_canonical_v7_chapter

router = APIRouter(prefix="/api/v1/chapters", tags=["scenes"])


def _chapter_project(chapter_id: str, *, require_scope: bool = False) -> tuple[str, str]:
    """返回 (project_id, title)；找不到章节抛 404。"""
    db = connect()
    row = row_to_dict(db.execute(
        "SELECT * FROM contents WHERE id = %s AND is_deleted = FALSE",
        (chapter_id,),
    ).fetchone())
    if not row:
        db.close()
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="chapter not found")
    if row.get("type") != "chapter":
        db.close()
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="content is not a chapter")
    if require_scope:
        try:
            require_canonical_v7_chapter(db, row, operation="scene_direct")
        except ChapterScopeError as exc:
            db.close()
            from fastapi import HTTPException
            raise HTTPException(
                status_code=409,
                detail={"code": exc.code, "message": exc.message, **exc.details},
            ) from exc
    db.close()
    return row.get("project_id") or "", row.get("title", "")


@router.post("/{chapter_id}/scene-direct")
def trigger_scene_direction(chapter_id: str, user: dict = Depends(get_current_user)):
    from app.core.authz import require_project_member
    from app.workers.m3_tasks import run_scene_direction
    project_id, _ = _chapter_project(chapter_id, require_scope=True)
    require_project_member(project_id, user, write=True)
    result = run_scene_direction.delay(project_id, chapter_id)
    return {"code": 0, "message": "ok", "data": {"task_id": result.id, "status": "dispatched"}}


@router.get("/{chapter_id}/scenes")
def get_chapter_scenes(chapter_id: str, user: dict = Depends(get_current_user)):
    from app.core.authz import require_project_member
    project_id, _ = _chapter_project(chapter_id)
    require_project_member(project_id, user, write=False)
    return {"code": 0, "message": "ok", "data": {"scenes": scene_director.get_scenes(chapter_id)}}
