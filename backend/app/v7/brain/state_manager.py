"""Story state manager with confidence gating."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.state import StoryStateRepository, StateChangeRepository
from ..repositories.event import EventLogRepository


class StoryStateManager:
    """
    Story state manager with confidence gating.
    
    Confidence levels:
    - >= 0.9: auto-approve, update directly
    - 0.7 - 0.9: update but flag for review
    - 0.5 - 0.7: pending review, don't update active state
    - < 0.5: discard, don't save
    """

    def __init__(self, db: AsyncSession, novel_id: uuid.UUID):
        self.db = db
        self.novel_id = novel_id
        self.state_repo = StoryStateRepository(db)
        self.change_repo = StateChangeRepository(db)
        self.event_repo = EventLogRepository(db)

    async def get_state(
        self,
        state_type: str,
        state_key: str,
    ) -> dict[str, Any] | None:
        """Get state value."""
        state = await self.state_repo.get_by_key(
            self.novel_id, state_type, state_key
        )
        if state:
            return {
                "value": state.state_value,
                "confidence": state.confidence,
                "version": state.version,
                "source": state.source,
                "is_pending_review": state.is_pending_review,
            }
        return None

    async def list_states(
        self,
        state_type: str,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List states by type."""
        states = await self.state_repo.list_by_type(
            self.novel_id, state_type, skip=skip, limit=limit
        )
        return [
            {
                "id": str(s.id),
                "key": s.state_key,
                "value": s.state_value,
                "confidence": s.confidence,
                "version": s.version,
                "source": s.source,
                "is_pending_review": s.is_pending_review,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in states
        ]

    async def update_state(
        self,
        state_type: str,
        state_key: str,
        value: dict[str, Any],
        confidence: float,
        *,
        source: str = "ai_extracted",
        source_run_id: uuid.UUID | None = None,
        reason: str | None = None,
        confidence_threshold: float = 0.7,
        hard_threshold: float = 0.9,
    ) -> dict[str, Any]:
        """
        Update state with confidence gating.
        
        Returns: {
            "action": "updated" | "pending_review" | "created" | "discarded",
            "state": state_dict | None,
            "confidence": float,
        }
        """
        # Below minimum threshold: discard
        if confidence < 0.5:
            await self.event_repo.record_event(
                self.novel_id,
                "state_update_discarded",
                f"State {state_type}/{state_key} discarded (confidence {confidence:.2f} < 0.5)",
                "state",
                source=source,
                source_run_id=source_run_id,
                severity="warning",
                event_data={"state_type": state_type, "state_key": state_key, "confidence": confidence},
            )
            return {
                "action": "discarded",
                "state": None,
                "confidence": confidence,
                "reason": "confidence below 0.5 threshold",
            }

        # Get existing state
        existing = await self.state_repo.get_by_key(
            self.novel_id, state_type, state_key
        )
        old_value = existing.state_value if existing else None
        old_confidence = existing.confidence if existing else None

        # Update with confidence gating
        state, action = await self.state_repo.update_with_confidence(
            self.novel_id,
            state_type,
            state_key,
            value,
            confidence,
            source=source,
            source_run_id=source_run_id,
            confidence_threshold=confidence_threshold,
        )

        # Record state change
        await self.change_repo.record_change(
            self.novel_id,
            state.id,
            "update" if existing else "create",
            state_type,
            state_key,
            old_value=old_value,
            new_value=value,
            old_confidence=old_confidence,
            new_confidence=confidence,
            reason=reason,
            source=source,
            source_run_id=source_run_id,
        )

        # Record event
        event_type = f"state_{action}"
        await self.event_repo.record_event(
            self.novel_id,
            event_type,
            f"State {state_type}/{state_key} {action} (confidence: {confidence:.2f})",
            "state",
            source=source,
            source_run_id=source_run_id,
            severity="info" if action != "pending_review" else "warning",
            event_data={
                "state_type": state_type,
                "state_key": state_key,
                "confidence": confidence,
                "action": action,
            },
        )

        return {
            "action": action,
            "state": {
                "id": str(state.id),
                "value": state.state_value,
                "confidence": state.confidence,
                "version": state.version,
                "is_pending_review": state.is_pending_review,
            },
            "confidence": confidence,
        }

    async def approve_state(
        self,
        state_id: uuid.UUID,
        *,
        user_id: uuid.UUID | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Approve a pending review state."""
        state = await self.state_repo.get_or_404(state_id)
        
        old_value = state.state_value
        old_confidence = state.confidence
        
        state.is_pending_review = False
        state.confidence = max(state.confidence, 0.9)  # Boost confidence on approval
        
        await self.db.flush()
        await self.db.refresh(state)

        # Record change
        await self.change_repo.record_change(
            self.novel_id,
            state.id,
            "approve",
            state.state_type,
            state.state_key,
            old_value=old_value,
            new_value=state.state_value,
            old_confidence=old_confidence,
            new_confidence=state.confidence,
            reason=reason or "Human approved",
            source="human",
        )

        # Record event
        await self.event_repo.record_event(
            self.novel_id,
            "state_approved",
            f"State {state.state_type}/{state.state_key} approved by human",
            "state",
            source="human",
            source_user_id=user_id,
            severity="info",
            event_data={"state_id": str(state_id)},
        )

        return {
            "id": str(state.id),
            "is_pending_review": state.is_pending_review,
            "confidence": state.confidence,
        }

    async def reject_state(
        self,
        state_id: uuid.UUID,
        *,
        user_id: uuid.UUID | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Reject a pending review state."""
        state = await self.state_repo.get_or_404(state_id)
        
        state.is_active = False
        
        await self.db.flush()
        await self.db.refresh(state)

        # Record event
        await self.event_repo.record_event(
            self.novel_id,
            "state_rejected",
            f"State {state.state_type}/{state.state_key} rejected by human",
            "state",
            source="human",
            source_user_id=user_id,
            severity="warning",
            event_data={"state_id": str(state_id), "reason": reason},
        )

        return {
            "id": str(state.id),
            "is_active": state.is_active,
        }

    async def get_pending_review(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get states pending review."""
        states = await self.state_repo.list_pending_review(
            self.novel_id, skip=skip, limit=limit
        )
        return [
            {
                "id": str(s.id),
                "type": s.state_type,
                "key": s.state_key,
                "value": s.state_value,
                "confidence": s.confidence,
                "source": s.source,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in states
        ]

    async def get_state_changes(
        self,
        state_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get change history for a state."""
        changes = await self.change_repo.list_by_state(
            state_id, skip=skip, limit=limit
        )
        return [
            {
                "id": str(c.id),
                "change_type": c.change_type,
                "old_value": c.old_value,
                "new_value": c.new_value,
                "old_confidence": c.old_confidence,
                "new_confidence": c.new_confidence,
                "reason": c.reason,
                "source": c.source,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in changes
        ]
