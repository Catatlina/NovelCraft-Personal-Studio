"""Goal system."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.goal import GoalRepository, IntentRepository
from ..repositories.event import EventLogRepository


class GoalSystem:
    """Story goal system."""

    def __init__(self, db: AsyncSession, novel_id: uuid.UUID):
        self.db = db
        self.novel_id = novel_id
        self.goal_repo = GoalRepository(db)
        self.intent_repo = IntentRepository(db)
        self.event_repo = EventLogRepository(db)

    async def list_goals(
        self,
        *,
        goal_type: str | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List goals."""
        goals = await self.goal_repo.list_by_novel(
            self.novel_id,
            goal_type=goal_type,
            status=status,
            skip=skip,
            limit=limit,
        )
        return [
            {
                "id": str(g.id),
                "name": g.goal_name,
                "type": g.goal_type,
                "description": g.description,
                "parent_goal_id": str(g.parent_goal_id) if g.parent_goal_id else None,
                "order": g.goal_order,
                "status": g.status,
                "progress": g.progress,
                "target_chapter": g.target_chapter,
                "completed_chapter": g.completed_chapter,
                "priority": g.priority,
                "confidence": g.confidence,
            }
            for g in goals
        ]

    async def get_goal_tree(
        self,
        *,
        goal_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get goal tree structure."""
        return await self.goal_repo.get_goal_tree(
            self.novel_id, goal_type=goal_type
        )

    async def create_goal(
        self,
        goal_type: str,
        goal_name: str,
        *,
        description: str | None = None,
        parent_goal_id: uuid.UUID | None = None,
        goal_order: int = 0,
        target_chapter: int | None = None,
        priority: int = 50,
        confidence: float = 0.8,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new goal."""
        goal = await self.goal_repo.create({
            "novel_id": self.novel_id,
            "goal_type": goal_type,
            "goal_name": goal_name,
            "description": description,
            "parent_goal_id": parent_goal_id,
            "goal_order": goal_order,
            "target_chapter": target_chapter,
            "priority": priority,
            "confidence": confidence,
            "extra_metadata": metadata or {},
        })

        await self.event_repo.record_event(
            self.novel_id,
            "goal_created",
            f"Goal created: {goal_name}",
            "goal",
            source="human",
            event_data={"goal_id": str(goal.id), "goal_name": goal_name},
        )

        return {
            "id": str(goal.id),
            "name": goal.goal_name,
            "type": goal.goal_type,
            "status": goal.status,
            "progress": goal.progress,
        }

    async def update_goal(
        self,
        goal_id: uuid.UUID,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update a goal."""
        goal = await self.goal_repo.update(goal_id, data)

        await self.event_repo.record_event(
            self.novel_id,
            "goal_updated",
            f"Goal updated: {goal.goal_name}",
            "goal",
            source="human",
            event_data={"goal_id": str(goal.id)},
        )

        return {
            "id": str(goal.id),
            "name": goal.goal_name,
            "status": goal.status,
            "progress": goal.progress,
        }

    async def update_progress(
        self,
        goal_id: uuid.UUID,
        progress: float,
        *,
        status: str | None = None,
        source: str = "ai",
        source_run_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Update goal progress."""
        goal = await self.goal_repo.update_progress(
            goal_id, progress, status=status
        )

        await self.event_repo.record_event(
            self.novel_id,
            "goal_progress_updated",
            f"Goal progress: {goal.goal_name} = {progress:.0%}",
            "goal",
            source=source,
            source_run_id=source_run_id,
            event_data={"goal_id": str(goal.id), "progress": progress},
        )

        return {
            "id": str(goal.id),
            "name": goal.goal_name,
            "status": goal.status,
            "progress": goal.progress,
        }

    async def delete_goal(
        self,
        goal_id: uuid.UUID,
    ) -> None:
        """Delete a goal (soft delete)."""
        await self.goal_repo.update(goal_id, {"is_active": False})

        await self.event_repo.record_event(
            self.novel_id,
            "goal_deleted",
            f"Goal deleted: {goal_id}",
            "goal",
            source="human",
            severity="warning",
            event_data={"goal_id": str(goal_id)},
        )

    # Author intents
    async def list_intents(
        self,
        *,
        intent_type: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List author intents."""
        intents = await self.intent_repo.list_by_novel(
            self.novel_id,
            intent_type=intent_type,
            skip=skip,
            limit=limit,
        )
        return [
            {
                "id": str(i.id),
                "type": i.intent_type,
                "key": i.intent_key,
                "value": i.intent_value,
                "description": i.description,
                "priority": i.priority,
            }
            for i in intents
        ]

    async def create_intent(
        self,
        intent_type: str,
        intent_key: str,
        intent_value: dict[str, Any],
        *,
        description: str | None = None,
        priority: int = 50,
    ) -> dict[str, Any]:
        """Create an author intent."""
        intent = await self.intent_repo.create({
            "novel_id": self.novel_id,
            "intent_type": intent_type,
            "intent_key": intent_key,
            "intent_value": intent_value,
            "description": description,
            "priority": priority,
        })

        await self.event_repo.record_event(
            self.novel_id,
            "intent_created",
            f"Intent created: {intent_type}/{intent_key}",
            "goal",
            source="human",
            event_data={"intent_id": str(intent.id)},
        )

        return {
            "id": str(intent.id),
            "type": intent.intent_type,
            "key": intent.intent_key,
            "value": intent.intent_value,
        }

    async def update_intent(
        self,
        intent_id: uuid.UUID,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an author intent."""
        intent = await self.intent_repo.update(intent_id, data)

        await self.event_repo.record_event(
            self.novel_id,
            "intent_updated",
            f"Intent updated: {intent.intent_type}/{intent.intent_key}",
            "goal",
            source="human",
            event_data={"intent_id": str(intent.id)},
        )

        return {
            "id": str(intent.id),
            "type": intent.intent_type,
            "key": intent.intent_key,
            "value": intent.intent_value,
        }
