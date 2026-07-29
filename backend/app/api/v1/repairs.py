"""V3 Repair Engine product API: generate a preview, then explicitly apply it."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.core.authz import require_content_member
from app.core.billing import enforce_quota
from app.core.security import get_current_user
from app.db import connect, decode, encode
from app.gateway import complete
from app.services.novel_export import extract_body_text
from app.workers.tasks import (
    _apply_replacements,
    _preview_chapter_replan,
    _preview_local_repair,
)

router = APIRouter(prefix="/api/v1/chapters", tags=["repairs"])
RepairAction = Literal["repair_local", "rewrite_chapter", "replan_chapter"]


class RepairPreviewRequest(BaseModel):
    action: RepairAction
    issues: list[str] = Field(min_length=1, max_length=50)
    client_mutation_id: str | None = Field(default=None, min_length=8, max_length=100)


class RepairApplyRequest(BaseModel):
    action: RepairAction
    base_updated_at: datetime
    proposal: dict[str, Any]
    signature: str = Field(min_length=64, max_length=64)


def _load_chapter(chapter_id: str) -> dict[str, Any]:
    db = connect()
    row = db.execute(
        """SELECT id, project_id, parent_id, title, body, meta, updated_at
           FROM contents
           WHERE id=%s AND type='chapter' AND is_deleted=FALSE""",
        (chapter_id,),
    ).fetchone()
    db.close()
    if not row:
        raise HTTPException(status_code=404, detail="chapter not found")
    result = dict(row)
    result["body"] = decode(result.get("body"), {})
    result["meta"] = decode(result.get("meta"), {})
    return result


def _signature_payload(
    chapter_id: str,
    action: str,
    base_updated_at: str,
    proposal: dict[str, Any],
) -> bytes:
    return json.dumps(
        {
            "chapter_id": chapter_id,
            "action": action,
            "base_updated_at": base_updated_at,
            "proposal": proposal,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _sign(chapter_id: str, action: str, base_updated_at: str, proposal: dict[str, Any]) -> str:
    secret = settings.jwt_secret or "novelcraft-development-repair-preview"
    return hmac.new(
        secret.encode("utf-8"),
        _signature_payload(chapter_id, action, base_updated_at, proposal),
        hashlib.sha256,
    ).hexdigest()


def _text_to_doc(text: str) -> dict[str, Any]:
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "text": part} for part in paragraphs],
    }


@router.post("/{chapter_id}/repair-preview")
def preview_repair(
    chapter_id: str,
    body: RepairPreviewRequest,
    user: dict = Depends(get_current_user),
):
    project_id = require_content_member(chapter_id, user, write=True)
    enforce_quota(user["id"], None, "max_words_per_month")
    chapter = _load_chapter(chapter_id)
    issues_text = "\n".join(item.strip() for item in body.issues if item.strip())
    if not issues_text:
        raise HTTPException(status_code=422, detail="repair issues are required")

    if body.action == "repair_local":
        proposal = _preview_local_repair(
            chapter_id, str(chapter["parent_id"]), project_id, issues_text
        )
    elif body.action == "replan_chapter":
        proposal = _preview_chapter_replan(
            chapter_id, str(chapter["parent_id"]), project_id, issues_text
        )
    else:
        output = complete(
            run_id=None,
            node_key="repair_rewrite_chapter",
            project_id=project_id,
            task_type="editor_rewrite",
            prompt_name="editor.rewrite",
            variables={
                "selection": extract_body_text(chapter["body"]),
                "instruction": "按以下审阅问题整章重写；保留核心剧情与既有事实：\n" + issues_text,
            },
            client_mutation_id=body.client_mutation_id,
        )
        proposal = {
            "action": "rewrite_chapter",
            "level": "chapter",
            "proposed_body": _text_to_doc(str(output["text"])),
        }

    base_updated_at = chapter["updated_at"].isoformat()
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "action": body.action,
            "base_updated_at": base_updated_at,
            "current_body": chapter["body"],
            "proposal": proposal,
            "signature": _sign(chapter_id, body.action, base_updated_at, proposal),
        },
    }


@router.post("/{chapter_id}/repair-apply")
def apply_repair(
    chapter_id: str,
    body: RepairApplyRequest,
    user: dict = Depends(get_current_user),
):
    require_content_member(chapter_id, user, write=True)
    base_updated_at = body.base_updated_at.isoformat()
    expected = _sign(chapter_id, body.action, base_updated_at, body.proposal)
    if not hmac.compare_digest(expected, body.signature):
        raise HTTPException(status_code=422, detail="repair preview signature is invalid")

    db = connect()
    row = db.execute(
        """SELECT body, meta, updated_at FROM contents
           WHERE id=%s AND type='chapter' AND is_deleted=FALSE FOR UPDATE""",
        (chapter_id,),
    ).fetchone()
    if not row:
        db.close()
        raise HTTPException(status_code=404, detail="chapter not found")
    if row["updated_at"] != body.base_updated_at:
        db.rollback()
        db.close()
        raise HTTPException(status_code=409, detail="chapter changed after preview; generate a new preview")

    current_body = decode(row["body"], {})
    meta = decode(row["meta"], {})
    now = datetime.now(timezone.utc).isoformat()
    if body.action == "repair_local":
        replacements = body.proposal.get("replacements")
        next_body, applied, skipped = _apply_replacements(current_body, replacements)
        if not applied or skipped:
            db.rollback()
            db.close()
            raise HTTPException(status_code=409, detail="repair anchors no longer match the chapter")
        log = list(meta.get("repair_log") or [])
        log.append({"level": "local", "applied": applied, "at": now})
        patch = {"repair_log": log}
        next_status = "needs_review"
    elif body.action == "replan_chapter":
        revised = body.proposal.get("revised_outline")
        rationale = str(body.proposal.get("rationale", ""))
        if not isinstance(revised, dict) or not revised:
            db.rollback()
            db.close()
            raise HTTPException(status_code=422, detail="revised outline is required")
        next_body = current_body
        log = list(meta.get("replan_log") or [])
        log.append({"revised_outline": revised, "rationale": rationale, "at": now})
        patch = {"outline": revised, "replan_log": log}
        next_status = "needs_rewrite"
    else:
        next_body = body.proposal.get("proposed_body")
        if not isinstance(next_body, dict) or next_body.get("type") != "doc":
            db.rollback()
            db.close()
            raise HTTPException(status_code=422, detail="rewritten chapter body is invalid")
        log = list(meta.get("repair_log") or [])
        log.append({"level": "chapter", "applied": ["whole_chapter"], "at": now})
        patch = {"repair_log": log}
        next_status = "needs_review"

    updated = db.execute(
        """UPDATE contents
           SET body=%s, meta=meta || %s, status=%s, updated_at=now()
           WHERE id=%s
           RETURNING body, meta, status, updated_at""",
        (encode(next_body), encode(patch), next_status, chapter_id),
    ).fetchone()
    db.commit()
    db.close()
    result = dict(updated)
    result["body"] = decode(result["body"], {})
    result["meta"] = decode(result["meta"], {})
    return {"code": 0, "message": "ok", "data": result}
