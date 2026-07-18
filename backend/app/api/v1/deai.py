"""De-AI API routes: 7-layer pipeline for removing AI taste from novel text."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.db import connect
from app.services.deai_pipeline import DeaiPipeline, deai_score, quick_deai_score

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["deai"])


def ok(data: dict) -> dict:
    return {"code": 0, "message": "ok", "data": data}


def err(code: int, message: str) -> dict:
    return {"code": code, "message": message, "data": None}


def _get_content_project(content_id: str) -> tuple[str, str]:
    """Resolve content_id → (project_id, title), raising 404 if not found."""
    db = connect()
    try:
        row = db.execute(
            "SELECT project_id, title FROM contents WHERE id = %s AND is_deleted = FALSE",
            (content_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "content not found")
        return row["project_id"], row.get("title", "")
    finally:
        db.close()


def _get_content_body(content_id: str) -> str:
    """Extract plain text body from a content record."""
    db = connect()
    try:
        row = db.execute(
            "SELECT body FROM contents WHERE id = %s AND is_deleted = FALSE",
            (content_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "content not found")
        body = row["body"]
        if isinstance(body, dict):
            # body: {"content": [{"text": "..."}, ...]}
            paragraphs = body.get("content", [])
            return "\n\n".join(
                p.get("text", "") if isinstance(p, dict) else str(p)
                for p in paragraphs
            )
        if isinstance(body, list):
            return "\n\n".join(
                p.get("text", "") if isinstance(p, dict) else str(p)
                for p in body
            )
        return str(body) if body else ""
    finally:
        db.close()


class DeaiRunResponse(BaseModel):
    """Response shape for deai pipeline run."""
    original_score: int = Field(ge=0, le=100)
    final_score: int = Field(ge=0, le=100)
    layers: list[dict] = Field(default_factory=list)
    final_text: str = ""


class DeaiScoreResponse(BaseModel):
    """Response shape for deai score query."""
    score: int = Field(ge=0, le=100)
    heuristic_score: int = Field(ge=0, le=100)
    text_preview: str = ""


# ── POST /contents/{content_id}/deai ──────────────────────────────────────

@router.post("/contents/{content_id}/deai")
def run_deai_pipeline(
    content_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """Run the full 7-layer de-AI pipeline on a chapter.

    Hardened (Bug②): any unexpected error degrades to a 200 ``ok({warning})``
    instead of 500. ``HTTPException`` (e.g. 404 not-found) is re-raised to keep
    its semantics; only generic failures are swallowed.
    """
    try:
        project_id, title = _get_content_project(content_id)
        text = _get_content_body(content_id)

        if not text or not text.strip():
            return ok({
                "original_score": 0,
                "final_score": 0,
                "layers": [],
                "final_text": text,
                "warning": "empty content",
            })

        pipeline = DeaiPipeline(
            project_id=project_id,
            content_id=content_id,
            chapter_title=title,
        )
        result = pipeline.run(text)
        return ok(result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("DeAI pipeline degraded for content %s", content_id)
        return ok({
            "original_score": 0,
            "final_score": 0,
            "layers": [],
            "final_text": "",
            "warning": f"deai pipeline degraded: {exc}",
        })


# ── GET /contents/{content_id}/deai/score ──────────────────────────────────

@router.get("/contents/{content_id}/deai/score")
def get_deai_score(
    content_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """Get AI-taste score for a chapter (heuristic + LLM).

    Hardened (Bug②): never returns 500. ``HTTPException`` (e.g. 404) propagates;
    generic failures degrade to a safe 0-score response.
    """
    try:
        project_id, _ = _get_content_project(content_id)
        text = _get_content_body(content_id)

        if not text or not text.strip():
            return ok({
                "score": 0,
                "heuristic_score": 0,
                "text_preview": "",
            })

        heuristic = quick_deai_score(text)

        try:
            score = deai_score(project_id, text)
        except Exception as exc:
            logger.warning("LLM deai scoring failed: %s — using heuristic only", exc)
            score = heuristic + 30

        return ok({
            "score": min(score, 100),
            "heuristic_score": heuristic,
            "text_preview": text[:100] + ("..." if len(text) > 100 else ""),
        })
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("DeAI score degraded for content %s", content_id)
        return ok({
            "score": 0,
            "heuristic_score": 0,
            "text_preview": "",
            "warning": f"deai score degraded: {exc}",
        })


# ── POST /contents/{content_id}/deai/quick-score ──────────────────────────

@router.post("/contents/{content_id}/deai/quick-score")
def quick_score(
    content_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """Fast heuristic-only AI score (no LLM call)."""
    text = _get_content_body(content_id)
    score = quick_deai_score(text)

    return ok({
        "score": score,
        "text_preview": text[:100] + ("..." if len(text) > 100 else ""),
    })
