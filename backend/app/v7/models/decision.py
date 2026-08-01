"""Decision permission and log models."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime,  Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel, NovelScopedMixin


class DecisionPermission(BaseModel, NovelScopedMixin):
    """Decision permission configuration."""
    __tablename__ = "v7_decision_permissions"

    decision_type: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    permission_level: Mapped[str] = mapped_column(String(20), nullable=False, default="auto")
    # auto / notify / approve / forbidden
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    escalation_rule: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)


class DecisionLog(BaseModel, NovelScopedMixin):
    """Decision log record."""
    __tablename__ = "v7_decision_logs"

    decision_type: Mapped[str] = mapped_column(String(100), nullable=False)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)  # approve/reject/defer/escalate
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.9)
    permission_level: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    # pending/completed/rejected/escalated
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    alternatives: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    decided_by: Mapped[str] = mapped_column(String(50), nullable=False, default="ai")  # ai/human/system
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approval_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
