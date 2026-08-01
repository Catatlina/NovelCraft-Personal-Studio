"""Cost budget models."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel, NovelScopedMixin


class CostBudget(BaseModel, NovelScopedMixin):
    """Cost budget configuration."""
    __tablename__ = "v7_cost_budgets"

    budget_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # total / monthly / weekly / daily / per_chapter / per_run
    budget_scope: Mapped[str] = mapped_column(String(50), nullable=False)
    # novel / project / user / global
    limit_cny: Mapped[float] = mapped_column(Float, nullable=False)
    spent_cny: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    limit_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    spent_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    alert_threshold_80: Mapped[bool] = mapped_column(default=False)
    alert_threshold_95: Mapped[bool] = mapped_column(default=False)
    action_on_exceed: Mapped[str] = mapped_column(String(20), nullable=False, default="warn")
    # warn / slow / stop
    is_active: Mapped[bool] = mapped_column(default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_policy: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # { task_type: { max_tokens, max_cost, max_retries, model_preference } }
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
