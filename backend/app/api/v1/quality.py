"""User-visible quality configuration endpoints.

The AI-flavor lexicon is editable metadata, not a second review engine.  It
is stored in the existing settings table so the built-in vocabulary remains
versioned in code while a personal studio can tune candidate signals without
changing V7's canonical score or hard quality gates.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.config import require_admin, require_admin_reads
from app.db import connect, encode
from app.core.authz import ok
from app.v7.quality.novel_reviewer_reference import (
    AI_FLAVOR_LEXICON_SETTING_KEY,
    default_ai_flavor_lexicon,
    invalidate_ai_flavor_lexicon_cache,
    load_ai_flavor_lexicon,
    normalize_ai_flavor_lexicon,
    store_ai_flavor_lexicon,
)

router = APIRouter(prefix="/api/v1/quality", tags=["quality"])


class LexiconPhrase(BaseModel):
    phrase: str = Field(min_length=1, max_length=80)
    enabled: bool = True
    note: str = Field(default="", max_length=240)


class LexiconCategory(BaseModel):
    key: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    label: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=240)
    enabled: bool = True
    phrases: list[LexiconPhrase] = Field(default_factory=list, max_length=160)


class LexiconUpdate(BaseModel):
    schema_version: str = Field(default="ai-flavor-lexicon-v2", max_length=64)
    version: int = Field(default=2, ge=1, le=9999)
    mode: str = Field(default="advisory", pattern=r"^advisory$")
    hard_gate: bool = False
    categories: list[LexiconCategory] = Field(default_factory=list, max_length=32)


def _public_config(value: dict[str, Any]) -> dict[str, Any]:
    categories = value.get("categories") or []
    phrase_count = sum(len(category.get("phrases") or []) for category in categories)
    enabled_phrase_count = sum(
        1
        for category in categories
        if category.get("enabled", True)
        for phrase in category.get("phrases") or []
        if phrase.get("enabled", True)
    )
    result = dict(value)
    result.update({
        "setting_key": AI_FLAVOR_LEXICON_SETTING_KEY,
        "source": value.get("source") or "builtin",
        "editable": True,
        "mode": "advisory",
        "hard_gate": False,
        "category_count": len(categories),
        "phrase_count": phrase_count,
        "enabled_phrase_count": enabled_phrase_count,
        "usage_note": "词库只产生候选信号；单个词、标点或题材术语不会单独触发质量门禁。",
    })
    return result


@router.get("/ai-flavor-lexicon")
def get_ai_flavor_lexicon(user: dict = Depends(require_admin_reads)):
    """Return the effective built-in/database lexicon for the settings page."""
    return ok(_public_config(load_ai_flavor_lexicon(force=True)))


@router.put("/ai-flavor-lexicon")
def update_ai_flavor_lexicon(payload: LexiconUpdate, user: dict = Depends(require_admin)):
    """Persist an edited advisory vocabulary after strict shape validation."""
    if payload.hard_gate or payload.mode != "advisory":
        raise HTTPException(status_code=422, detail="AI 味词库只能作为 advisory 候选信号，不能变成硬禁词门禁")
    raw = payload.model_dump()
    total_chars = sum(
        len(item.phrase)
        for category in payload.categories
        for item in category.phrases
    )
    if total_chars > 50000:
        raise HTTPException(status_code=422, detail="词库总长度不能超过 50000 个字符")
    normalised = normalize_ai_flavor_lexicon(raw)
    db = connect()
    try:
        db.execute(
            """INSERT INTO settings (key, value, description)
               VALUES (%s, %s, %s)
               ON CONFLICT(key) DO UPDATE SET
                 value=EXCLUDED.value,
                 description=EXCLUDED.description,
                 updated_at=now()""",
            (
                AI_FLAVOR_LEXICON_SETTING_KEY,
                encode(normalised),
                "可编辑 AI 味候选词库；仅供 V7 审阅复核，不改变总分或硬门禁",
            ),
        )
        db.commit()
    finally:
        db.close()
    stored = store_ai_flavor_lexicon(normalised)
    return ok(_public_config(stored), message="AI 味词库已保存")


@router.post("/ai-flavor-lexicon/reset")
def reset_ai_flavor_lexicon(user: dict = Depends(require_admin)):
    """Restore the code-versioned vocabulary without deleting audit evidence."""
    db = connect()
    try:
        db.execute("DELETE FROM settings WHERE key = %s", (AI_FLAVOR_LEXICON_SETTING_KEY,))
        db.commit()
    finally:
        db.close()
    invalidate_ai_flavor_lexicon_cache()
    return ok(_public_config(default_ai_flavor_lexicon()), message="AI 味词库已恢复内置版本")
