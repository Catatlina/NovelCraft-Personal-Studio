"""Human Checkpoint API (§10.2)

Three explicit confirmation nodes in the production pipeline:
  - checkpoint_1: book setup confirmation (draft → outline_confirmed)
  - checkpoint_2: per-volume confirmation (after arc_summary, human reviews)
  - checkpoint_3: per-100-chapter audit confirmation (after audit_report)

All transitions are user-initiated — the system never auto-advances past a
checkpoint without human approval.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.db import connect, row_to_dict, decode
from app.repositories.loop_repos import record_book_status, get_book_config
from app.api.v1.auth import get_current_user

router = APIRouter(prefix="/checkpoint", tags=["checkpoint"])


class CheckpointRequest(BaseModel):
    novel_id: str
    notes: str = ""


# ── Checkpoint 1: book setup → outline_confirmed ────────────────────────────
@router.post("/1/confirm")
def confirm_checkpoint_1(req: CheckpointRequest, user: dict = Depends(get_current_user)):
    """Confirm book setup is complete. Transitions: draft/worldbuilding → outline_confirmed."""
    cfg = get_book_config(req.novel_id, req.novel_id)
    if not cfg:
        raise HTTPException(404, "novel not found or no book_config")
    record_book_status(req.novel_id, req.novel_id, "outline_confirmed",
                       reason=f"checkpoint_1 confirmed by user. {req.notes}".strip())
    return {"ok": True, "status": "outline_confirmed"}


# ── Checkpoint 2: per-volume review ──────────────────────────────────────────
@router.post("/2/confirm")
def confirm_checkpoint_2(req: CheckpointRequest, user: dict = Depends(get_current_user)):
    """Confirm a volume review. The system pauses after arc_summary and waits."""
    conn = connect()
    try:
        row = row_to_dict(conn.execute(
            "SELECT id, volume_seq, summary FROM arc_summary "
            "WHERE novel_id=%s AND is_deleted=FALSE ORDER BY volume_seq DESC LIMIT 1",
            (req.novel_id,),
        ).fetchone())
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "no arc_summary found for this novel")
    return {"ok": True, "volume_seq": row.get("volume_seq"),
            "summary": row.get("summary", ""), "confirmed": True,
            "notes": req.notes}


# ── Checkpoint 3: per-100-chapter audit ──────────────────────────────────────
@router.post("/3/confirm")
def confirm_checkpoint_3(req: CheckpointRequest, user: dict = Depends(get_current_user)):
    """Confirm a 100-chapter audit report."""
    conn = connect()
    try:
        row = row_to_dict(conn.execute(
            "SELECT id, at_chapter, character_changes, capability_changes, "
            "foreshadowing_status FROM chapter_audit_report "
            "WHERE novel_id=%s AND is_deleted=FALSE ORDER BY at_chapter DESC LIMIT 1",
            (req.novel_id,),
        ).fetchone())
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "no audit report found for this novel")
    return {"ok": True, "at_chapter": row.get("at_chapter"),
            "character_changes": decode(row.get("character_changes"), []),
            "capability_changes": decode(row.get("capability_changes"), []),
            "foreshadowing_status": decode(row.get("foreshadowing_status"), {}),
            "confirmed": True, "notes": req.notes}


# ── Status query ─────────────────────────────────────────────────────────────
@router.get("/status/{novel_id}")
def get_checkpoint_status(novel_id: str, user: dict = Depends(get_current_user)):
    """Get current checkpoint status for a novel."""
    conn = connect()
    try:
        bs = row_to_dict(conn.execute(
            "SELECT status, reason, created_at FROM book_status "
            "WHERE novel_id=%s AND is_deleted=FALSE ORDER BY created_at DESC LIMIT 1",
            (novel_id,),
        ).fetchone())
        vol = row_to_dict(conn.execute(
            "SELECT MAX(volume_seq) AS last_vol FROM arc_summary "
            "WHERE novel_id=%s AND is_deleted=FALSE",
            (novel_id,),
        ).fetchone())
        audit = row_to_dict(conn.execute(
            "SELECT MAX(at_chapter) AS last_audit FROM chapter_audit_report "
            "WHERE novel_id=%s AND is_deleted=FALSE",
            (novel_id,),
        ).fetchone())
    finally:
        conn.close()
    return {
        "novel_id": novel_id,
        "book_status": bs.get("status") if bs else "draft",
        "last_volume": vol.get("last_vol") if vol else 0,
        "last_audit_chapter": audit.get("last_audit") if audit else 0,
    }
