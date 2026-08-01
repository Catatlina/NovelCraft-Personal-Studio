"""State repositories."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from ..models.state import StoryState, StateChange


class StoryStateRepository(BaseRepository[StoryState]):
    """Story state repository."""

    def __init__(self, db: AsyncSession):
        super().__init__(StoryState, db)

    async def get_by_key(
        self,
        novel_id: uuid.UUID,
        state_type: str,
        state_key: str,
    ) -> StoryState | None:
        """Get state by novel_id + type + key."""
        result = await self.db.execute(
            select(StoryState).where(
                StoryState.novel_id == novel_id,
                StoryState.state_type == state_type,
                StoryState.state_key == state_key,
                StoryState.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_type(
        self,
        novel_id: uuid.UUID,
        state_type: str,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[StoryState]:
        """List states by type."""
        result = await self.db.execute(
            select(StoryState).where(
                StoryState.novel_id == novel_id,
                StoryState.state_type == state_type,
                StoryState.is_active == True,
            )
            .order_by(StoryState.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_pending_review(
        self,
        novel_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> list[StoryState]:
        """List states pending review."""
        result = await self.db.execute(
            select(StoryState).where(
                StoryState.novel_id == novel_id,
                StoryState.is_pending_review == True,
            )
            .order_by(StoryState.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_with_confidence(
        self,
        novel_id: uuid.UUID,
        state_type: str,
        state_key: str,
        new_value: dict[str, Any],
        new_confidence: float,
        *,
        source: str = "ai_extracted",
        source_run_id: uuid.UUID | None = None,
        confidence_threshold: float = 0.7,
    ) -> tuple[StoryState, str]:
        """
        Update state with confidence gating.
        
        Returns: (state, action)
        action: 'updated' | 'pending_review' | 'created'
        """
        existing = await self.get_by_key(novel_id, state_type, state_key)

        if new_confidence >= confidence_threshold:
            if existing:
                existing.state_value = new_value
                existing.confidence = new_confidence
                existing.version += 1
                existing.is_pending_review = False
                await self.db.flush()
                await self.db.refresh(existing)
                return existing, "updated"
            else:
                state = await self.create({
                    "novel_id": novel_id,
                    "state_type": state_type,
                    "state_key": state_key,
                    "state_value": new_value,
                    "confidence": new_confidence,
                    "source": source,
                    "source_run_id": source_run_id,
                    "is_pending_review": False,
                })
                return state, "created"
        else:
            if existing:
                existing.is_pending_review = True
                await self.db.flush()
                await self.db.refresh(existing)
                return existing, "pending_review"
            else:
                state = await self.create({
                    "novel_id": novel_id,
                    "state_type": state_type,
                    "state_key": state_key,
                    "state_value": new_value,
                    "confidence": new_confidence,
                    "source": source,
                    "source_run_id": source_run_id,
                    "is_pending_review": True,
                })
                return state, "pending_review"


class StateChangeRepository(BaseRepository[StateChange]):
    """State change log repository."""

    def __init__(self, db: AsyncSession):
        super().__init__(StateChange, db)

    async def list_by_state(
        self,
        state_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> list[StateChange]:
        """List changes for a state."""
        result = await self.db.execute(
            select(StateChange).where(StateChange.state_id == state_id)
            .order_by(StateChange.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_novel(
        self,
        novel_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[StateChange]:
        """List changes for a novel."""
        result = await self.db.execute(
            select(StateChange).where(StateChange.novel_id == novel_id)
            .order_by(StateChange.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_run(
        self,
        run_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[StateChange]:
        """List changes for a run."""
        result = await self.db.execute(
            select(StateChange).where(StateChange.source_run_id == run_id)
            .order_by(StateChange.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def record_change(
        self,
        novel_id: uuid.UUID,
        state_id: uuid.UUID | None,
        change_type: str,
        state_type: str,
        state_key: str,
        *,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        old_confidence: float | None = None,
        new_confidence: float | None = None,
        reason: str | None = None,
        source: str = "system",
        source_run_id: uuid.UUID | None = None,
        snapshot_id: uuid.UUID | None = None,
    ) -> StateChange:
        """Record a state change."""
        return await self.create({
            "novel_id": novel_id,
            "state_id": state_id,
            "change_type": change_type,
            "state_type": state_type,
            "state_key": state_key,
            "old_value": old_value,
            "new_value": new_value,
            "old_confidence": old_confidence,
            "new_confidence": new_confidence,
            "reason": reason,
            "source": source,
            "source_run_id": source_run_id,
            "snapshot_id": snapshot_id,
        })
