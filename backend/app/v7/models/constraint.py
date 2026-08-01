"""Constraint system models."""
from __future__ import annotations

from typing import Any

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel, NovelScopedMixin


class Constraint(BaseModel, NovelScopedMixin):
    """Story constraint / rule."""
    __tablename__ = "v7_constraints"

    constraint_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # character_ooc / world_rule / plot_continuity / style / tone / forbidden / must_have / quality
    constraint_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    constraint_value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning")
    # info/warning/error/blocking
    check_method: Mapped[str] = mapped_column(String(50), nullable=False, default="ai_review")
    # ai_review / rule_based / human / none
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    is_active: Mapped[bool] = mapped_column(default=True)
    violation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_violation_at: Mapped[Any | None] = mapped_column(nullable=True)
    metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
