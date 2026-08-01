"""Story state models."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel, NovelScopedMixin


class StoryState(BaseModel, NovelScopedMixin):
    """Story state with confidence."""
    __tablename__ = "v7_story_states"

    state_type: Mapped[str] = mapped_column(String(50), nullable=False)  # global/character/world/plot/reader
    state_key: Mapped[str] = mapped_column(String(200), nullable=False)
    state_value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.9)
    confidence_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="ai_extracted")  # ai_extracted/human_set/imported
    source_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_pending_review: Mapped[bool] = mapped_column(default=False)

    __table_args__ = (
        # Unique constraint on novel_id + state_type + state_key + version
    )


class StateChange(BaseModel, NovelScopedMixin):
    """State change log."""
    __tablename__ = "v7_state_changes"

    state_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("v7_story_states.id"),
        nullable=True,
    )
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)  # create/update/delete/rollback
    state_type: Mapped[str] = mapped_column(String(50), nullable=False)
    state_key: Mapped[str] = mapped_column(String(200), nullable=False)
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    old_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    new_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # ai/human/system
    source_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    version_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("v7_brain_snapshots.id"),
        nullable=True,
    )
