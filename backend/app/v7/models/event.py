"""Event log models."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel, NovelScopedMixin


class EventLog(BaseModel, NovelScopedMixin):
    """Event log - permanent record of all events."""
    __tablename__ = "v7_event_logs"

    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # chapter_completed / state_changed / decision_made / human_intervention / error / etc.
    event_name: Mapped[str] = mapped_column(String(200), nullable=False)
    event_category: Mapped[str] = mapped_column(String(50), nullable=False)
    # generation / state / decision / human / system / error
    event_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    # ai / human / system
    source_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    source_step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    source_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    # debug / info / warning / error / critical
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    # For grouping related events
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    # Event schema version
    metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
