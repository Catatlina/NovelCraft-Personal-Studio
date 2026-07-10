"""TASK-043+044: Scheduled publish + ROI data analytics."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.db import connect, encode, new_id

router = APIRouter(prefix="/api/v1", tags=["publish_schedule", "analytics"])


def _require_content_role(db, content_id: str, user_id: str, roles: set[str] | None = None) -> dict:
    row = db.execute(
        """
        SELECT c.*, pm.role FROM contents c
        JOIN project_members pm ON pm.project_id = c.project_id
        WHERE c.id = %s AND pm.user_id = %s AND c.is_deleted = FALSE
        """,
        (content_id, user_id),
    ).fetchone()
    if not row or (roles and row["role"] not in roles):
        db.close()
        raise HTTPException(status_code=403, detail="insufficient permissions")
    return row


def _require_project_member(db, project_id: str, user_id: str) -> None:
    member = db.execute(
        "SELECT 1 FROM project_members WHERE project_id = %s AND user_id = %s",
        (project_id, user_id),
    ).fetchone()
    if not member:
        db.close()
        raise HTTPException(status_code=403, detail="not a project member")


@router.post("/publish/schedule")
def schedule_publish(
    content_id: str, platform: str, scheduled_at: str,
    user: dict = Depends(get_current_user),
):
    """TASK-043: Schedule content for future publishing."""
    db = connect()
    _require_content_role(db, content_id, user["id"], {"owner", "editor"})
    try:
        scheduled = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
    except ValueError as exc:
        db.close()
        raise HTTPException(status_code=422, detail="invalid scheduled_at") from exc
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)
    if scheduled <= datetime.now(timezone.utc):
        db.close()
        raise HTTPException(status_code=422, detail="scheduled_at must be in the future")
    db.execute(
        "INSERT INTO publish_records (id, content_id, platform, status, scheduled_at, meta) VALUES (%s,%s,%s,%s,%s,%s)",
        (new_id(), content_id, platform, "scheduled", scheduled, encode({"scheduled_at": scheduled_at})),
    )
    db.commit()
    db.close()
    return {"code": 0, "message": "ok", "data": {"content_id": content_id, "platform": platform, "scheduled_at": scheduled_at}}


@router.get("/publish/schedule")
def list_scheduled_publishes(user: dict = Depends(get_current_user)):
    """TASK-043: List scheduled publishes."""
    db = connect()
    rows = [dict(r) for r in db.execute(
        """
        SELECT pr.* FROM publish_records pr
        JOIN contents c ON c.id = pr.content_id
        JOIN project_members pm ON pm.project_id = c.project_id
        WHERE pr.status = 'scheduled' AND pm.user_id = %s
        ORDER BY pr.scheduled_at LIMIT 50
        """,
        (user["id"],),
    ).fetchall()]
    db.close()
    return {"code": 0, "message": "ok", "data": rows}


@router.get("/analytics/roi")
def get_roi_analytics(project_id: str | None = None, user: dict = Depends(get_current_user)):
    """TASK-044: Basic ROI analytics — cost vs output."""
    db = connect()
    if project_id:
        _require_project_member(db, project_id, user["id"])
        project_ids = [project_id]
    else:
        project_ids = [
            str(row["project_id"])
            for row in db.execute(
                "SELECT project_id FROM project_members WHERE user_id = %s",
                (user["id"],),
            ).fetchall()
        ]
    total_cost = db.execute(
        "SELECT COALESCE(SUM(cost_cny), 0) as total_cost FROM ai_calls WHERE project_id = ANY(%s::uuid[])",
        (project_ids,),
    ).fetchone()
    content_count = db.execute(
        "SELECT COUNT(*) as cnt FROM contents WHERE project_id = ANY(%s::uuid[]) AND is_deleted = FALSE",
        (project_ids,),
    ).fetchone()
    words = db.execute(
        "SELECT COALESCE(SUM(LENGTH(body::text)), 0) as total_words FROM contents WHERE project_id = ANY(%s::uuid[]) AND is_deleted = FALSE",
        (project_ids,),
    ).fetchone()
    db.close()
    cost = float(total_cost["total_cost"]) if total_cost else 0
    cnt = int(content_count["cnt"]) if content_count else 0
    total_words = int(words["total_words"]) if words else 0
    return {"code": 0, "message": "ok", "data": {
        "total_cost_cny": round(cost, 4),
        "content_count": cnt,
        "total_words": total_words,
        "cost_per_1k_words": round(cost / max(total_words / 1000, 1), 6) if total_words > 0 else 0,
    }}
