"""Event Bus - Sprint 1 skeleton.

Alpha implementation: synchronous in-process event bus.
Future: can swap to Redis/RabbitMQ/Kafka without changing API.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.event import EventLogRepository


class EventBus:
    """
    Event bus for publishing and subscribing to events.
    
    All state changes must go through the event bus for auditability.
    Events are permanently recorded in event_logs table.
    """

    def __init__(self, db: AsyncSession, novel_id: uuid.UUID):
        self.db = db
        self.novel_id = novel_id
        self.event_repo = EventLogRepository(db)
        self._subscribers: dict[str, list[Callable]] = {}

    async def publish(
        self,
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
    ) -> uuid.UUID:
        """
        Publish an event.
        
        1. Record event to database (permanent log)
        2. Notify all subscribers
        """
        event = await self.event_repo.record_event(
            self.novel_id,
            event_type,
            event_name,
            event_category,
            event_data=event_data or {},
            source=source,
            source_run_id=source_run_id,
            source_step_id=source_step_id,
            source_user_id=source_user_id,
            severity=severity,
            description=description,
            correlation_id=correlation_id,
        )

        # Notify subscribers (synchronous in Alpha)
        subscribers = self._subscribers.get(event_type, [])
        for callback in subscribers:
            try:
                await callback(event)
            except Exception:
                # Don't let subscriber errors break the event flow
                pass

        # Also notify wildcard subscribers
        wildcard_subscribers = self._subscribers.get("*", [])
        for callback in wildcard_subscribers:
            try:
                await callback(event)
            except Exception:
                pass

        return event.id

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """Subscribe to an event type. Use '*' for all events."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Unsubscribe from an event type."""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                cb for cb in self._subscribers[event_type] if cb != callback
            ]

    async def replay(
        self,
        *,
        event_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        """
        Replay events (for state reconstruction).
        
        Returns count of replayed events.
        Alpha: basic implementation, full replay in Sprint 3.
        """
        events = await self.event_repo.list_by_novel(
            self.novel_id,
            event_type=event_type,
            limit=10000,
        )

        count = 0
        for event in events:
            subscribers = self._subscribers.get(event.event_type, [])
            for callback in subscribers:
                try:
                    await callback(event)
                    count += 1
                except Exception:
                    pass

        return count
