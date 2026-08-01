"""Seed data model."""
from __future__ import annotations

from typing import Any

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class SeedData(BaseModel):
    """Seed data configuration."""
    __tablename__ = "v7_seed_data"

    seed_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # permission / constraint / default_config / strategy / etc.
    seed_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    seed_value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_builtin: Mapped[bool] = mapped_column(default=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
