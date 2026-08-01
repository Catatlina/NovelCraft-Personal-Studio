"""Human intervention models."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel, NovelScopedMixin


class HumanIntervention(BaseModel, NovelScopedMixin):
    """Human intervention record."""
    __tablename__ = "v7_human_interventions"

    intervention_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # state_edit / decision_approve / decision_reject / rollback / pause / resume / instruction / override
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)  # state/goal/constraint/decision/version/chapter
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    result: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    # success/failed/pending
    metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
