"""V3-P3-⑩: Author Style Card 强化 API。

- POST /{project_id}/signals  记录编辑器 diff 信号（修改/删除/保留）
- POST /{project_id}/like     标记喜欢表达
- POST /{project_id}/learn    触发 Learning Agent 异步重建 style_card
- GET  /{project_id}/card     读取当前 style_card
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.authz import require_project_member
from app.core.security import get_current_user
from app.services import author_style

router = APIRouter(prefix="/api/v1/author-style", tags=["author-style"])


class SignalIn(BaseModel):
    signal_type: str = "edit"
    kept_text: str = ""
    deleted_text: str = ""
    edited_text: str = ""
    liked_text: str = ""


class SignalsBody(BaseModel):
    content_id: str | None = None
    signals: list[SignalIn] = []


class LikeBody(BaseModel):
    content_id: str | None = None
    text: str = ""


@router.post("/{project_id}/signals")
def post_signals(project_id: str, body: SignalsBody, user: dict = Depends(get_current_user)):
    require_project_member(project_id, user, write=True)
    count = author_style.record_signals(
        project_id, body.content_id, user.get("id"),
        [s.model_dump() for s in body.signals],
    )
    return {"code": 0, "message": "ok", "data": {"recorded": count}}


@router.post("/{project_id}/like")
def post_like(project_id: str, body: LikeBody, user: dict = Depends(get_current_user)):
    require_project_member(project_id, user, write=True)
    count = author_style.record_signals(
        project_id, body.content_id, user.get("id"),
        [{"signal_type": "like", "liked_text": body.text}],
    )
    return {"code": 0, "message": "ok", "data": {"recorded": count}}


@router.post("/{project_id}/learn")
def trigger_learning(project_id: str, user: dict = Depends(get_current_user)):
    require_project_member(project_id, user, write=True)
    from app.workers.m3_tasks import run_author_style_learning
    result = run_author_style_learning.delay(project_id)
    return {"code": 0, "message": "ok", "data": {"task_id": result.id, "status": "dispatched"}}


@router.get("/{project_id}/card")
def get_card(project_id: str, user: dict = Depends(get_current_user)):
    require_project_member(project_id, user, write=False)
    return {"code": 0, "message": "ok", "data": {"card": author_style.get_card(project_id)}}
