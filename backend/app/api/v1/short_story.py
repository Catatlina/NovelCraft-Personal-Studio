"""M3: Short story API — trigger generation and return results."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.db import connect, encode, new_id
from app.workers.tasks import bootstrap_short_story_task

router = APIRouter(prefix="/api/v1/short-stories", tags=["short_stories"])


@router.post("/{short_id}/generate")
def trigger_short_story(short_id: str, user: dict = Depends(get_current_user)):
    """Trigger AI generation for a short story."""
    db = connect()
    story = db.execute("SELECT * FROM contents WHERE id = %s AND type='short_story'", (short_id,)).fetchone()
    if not story:
        db.close()
        raise HTTPException(status_code=404, detail="short story not found")
    db.close()
    result = bootstrap_short_story_task.delay(story["project_id"], short_id)
    return {"code": 0, "message": "ok", "data": {"task_id": result.id, "short_id": short_id, "status": "dispatched"}}


@router.get("/templates")
def list_templates():
    """List available short story templates."""
    from app.services.short_story import SHORT_STORY_TEMPLATES
    return {"code": 0, "message": "ok", "data": SHORT_STORY_TEMPLATES}
