"""Plot node models."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel, NovelScopedMixin


class PlotNode(BaseModel, NovelScopedMixin):
    """Plot tree node."""
    __tablename__ = "v7_plot_nodes"

    node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # arc / volume / chapter / scene / beat / event
    node_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("v7_plot_nodes.id"),
        nullable=True,
    )
    node_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    # planned / in_progress / completed / skipped / revised
    chapter_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    word_count_target: Mapped[int | None] = mapped_column(Integer, nullable=True)
    word_count_actual: Mapped[int | None] = mapped_column(Integer, nullable=True)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    node_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("v7_story_goals.id"),
        nullable=True,
    )
    foreshadowing_ids: Mapped[list[uuid.UUID]] = mapped_column(JSONB, nullable=False, default=list)
    character_ids: Mapped[list[uuid.UUID]] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
