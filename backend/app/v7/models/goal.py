"""Goal system models."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel, NovelScopedMixin


class AuthorIntent(BaseModel, NovelScopedMixin):
    """Author intent / creative direction."""
    __tablename__ = "v7_author_intents"

    intent_type: Mapped[str] = mapped_column(String(50), nullable=False)  # theme/style/tone/target
    intent_key: Mapped[str] = mapped_column(String(100), nullable=False)
    intent_value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    is_active: Mapped[bool] = mapped_column(default=True)


class StoryGoal(BaseModel, NovelScopedMixin):
    """Story goal."""
    __tablename__ = "v7_story_goals"

    goal_type: Mapped[str] = mapped_column(String(50), nullable=False)  # plot/character/world/reader/market
    goal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_goal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("v7_story_goals.id"),
        nullable=True,
    )
    goal_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending/in_progress/completed/failed/skipped
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    target_chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True)
