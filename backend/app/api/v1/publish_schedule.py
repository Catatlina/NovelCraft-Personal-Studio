"""TASK-043+044: Scheduled publish + ROI data analytics."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.db import connect, encode, new_id

router = APIRouter(prefix="/api/v1", tags=["publish_schedule", "analytics"])


@router.post("/publish/schedule")
def schedule_publish(
    content_id: str, platform: str, scheduled_at: str,
    user: dict = Depends(get_current_user),
):
    """TASK-043: Schedule content for future publishing."""
    db = connect()
    db.execute(
        "INSERT INTO publish_records (id, content_id, platform, status, meta) VALUES (%s,%s,%s,%s,%s)",
        (new_id(), content_id, platform, "scheduled", encode({"scheduled_at": scheduled_at})),
    )
    db.commit(); db.close()
    return {"code": 0, "message": "ok", "data": {"content_id": content_id, "platform": platform, "scheduled_at": scheduled_at}}


@router.get("/publish/schedule")
def list_scheduled_publishes(user: dict = Depends(get_current_user)):
    """TASK-043: List scheduled publishes."""
    db = connect()
    rows = [dict(r) for r in db.execute(
        "SELECT * FROM publish_records WHERE status = 'scheduled' ORDER BY created_at DESC LIMIT 50"
    ).fetchall()]
    db.close()
    return {"code": 0, "message": "ok", "data": rows}


@router.get("/analytics/roi")
def get_roi_analytics(project_id: str = "", user: dict = Depends(get_current_user)):
    """TASK-044: Basic ROI analytics — cost vs output."""
    db = connect()
    total_cost = db.execute(
        "SELECT COALESCE(SUM(cost_cny), 0) as total_cost FROM ai_calls",
    ).fetchone()
    content_count = db.execute(
        "SELECT COUNT(*) as cnt FROM contents WHERE is_deleted = FALSE",
    ).fetchone()
    words = db.execute(
        "SELECT COALESCE(SUM(LENGTH(body::text)), 0) as total_words FROM contents WHERE is_deleted = FALSE",
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
