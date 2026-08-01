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
from .schemas import validate_event_data


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
        self.dispatch_count: int = 0
        self.dispatch_errors: list[dict[str, Any]] = []

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

        1. Validate the payload against the registered Pydantic model (if any)
        2. Record event to database (permanent log)
        3. Notify all subscribers; subscriber failures are recorded, not hidden
        """
        payload = validate_event_data(event_type, event_data)

        event = await self.event_repo.record_event(
            self.novel_id,
            event_type,
            event_name,
            event_category,
            event_data=payload,
            source=source,
            source_run_id=source_run_id,
            source_step_id=source_step_id,
            source_user_id=source_user_id,
            severity=severity,
            description=description,
            correlation_id=correlation_id,
        )

        # Notify subscribers (synchronous, in-process)
        callbacks = list(self._subscribers.get(event_type, []))
        callbacks.extend(self._subscribers.get("*", []))

        for callback in callbacks:
            try:
                await callback(event)
                self.dispatch_count += 1
            except Exception as exc:  # noqa: BLE001 - recorded, never silently dropped
                self.dispatch_errors.append(
                    {
                        "event_type": event_type,
                        "subscriber": getattr(callback, "__qualname__", str(callback)),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                await self.event_repo.record_event(
                    self.novel_id,
                    "subscriber_failed",
                    f"Subscriber failed for {event_type}",
                    "system",
                    source="event_bus",
                    severity="error",
                    event_data={
                        "event_type": event_type,
                        "subscriber": getattr(callback, "__qualname__", str(callback)),
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )

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
