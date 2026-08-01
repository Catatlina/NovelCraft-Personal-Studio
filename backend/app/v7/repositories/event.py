"""Event log repository."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from ..models.event import EventLog


class EventLogRepository(BaseRepository[EventLog]):
    """Event log repository."""

    def __init__(self, db: AsyncSession):
        super().__init__(EventLog, db)

    async def list_by_novel(
        self,
        novel_id: uuid.UUID,
        *,
        event_type: str | None = None,
        event_category: str | None = None,
        severity: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[EventLog]:
        """List events for a novel."""
        query = select(EventLog).where(EventLog.novel_id == novel_id)

        if event_type:
            query = query.where(EventLog.event_type == event_type)
        if event_category:
            query = query.where(EventLog.event_category == event_category)
        if severity:
            query = query.where(EventLog.severity == severity)

        query = query.order_by(EventLog.event_time.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_by_run(
        self,
        run_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[EventLog]:
        """List events for a run."""
        result = await self.db.execute(
            select(EventLog).where(EventLog.source_run_id == run_id)
            .order_by(EventLog.event_time.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_correlation(
        self,
        correlation_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 200,
    ) -> list[EventLog]:
        """List events by correlation ID."""
        result = await self.db.execute(
            select(EventLog).where(EventLog.correlation_id == correlation_id)
            .order_by(EventLog.event_time.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def record_event(
        self,
        novel_id: uuid.UUID,
        event_type: str,
        event_name: str,
        event_category: str,
        *,
        event_data: dict[str, Any] | None = None,
        source: str = "system",
        source_run_id: uuid.UUID | None = None,
        source_step_id: uuid.UUID | None = None,
        source_user_id: uuid.UUID | None = None,
        severity: str = "info",
        description: str | None = None,
        correlation_id: uuid.UUID | None = None,
    ) -> EventLog:
        """Record an event."""
        return await self.create({
            "novel_id": novel_id,
            "event_type": event_type,
            "event_name": event_name,
            "event_category": event_category,
            "event_data": event_data or {},
            "source": source,
            "source_run_id": source_run_id,
            "source_step_id": source_step_id,
            "source_user_id": source_user_id,
            "severity": severity,
            "description": description,
            "correlation_id": correlation_id,
        })
