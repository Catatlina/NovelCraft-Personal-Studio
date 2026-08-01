"""Goal system repositories."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from ..models.goal import StoryGoal, AuthorIntent


class GoalRepository(BaseRepository[StoryGoal]):
    """Story goal repository."""

    def __init__(self, db: AsyncSession):
        super().__init__(StoryGoal, db)

    async def list_by_novel(
        self,
        novel_id: uuid.UUID,
        *,
        goal_type: str | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[StoryGoal]:
        """List goals for a novel."""
        query = select(StoryGoal).where(
            StoryGoal.novel_id == novel_id,
            StoryGoal.is_active == True,
        )

        if goal_type:
            query = query.where(StoryGoal.goal_type == goal_type)
        if status:
            query = query.where(StoryGoal.status == status)

        query = query.order_by(StoryGoal.goal_order.asc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_goal_tree(
        self,
        novel_id: uuid.UUID,
        *,
        goal_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get goal tree structure."""
        goals = await self.list_by_novel(novel_id, goal_type=goal_type, limit=500)
        
        # Build tree
        goal_map = {g.id: g for g in goals}
        root_goals = [g for g in goals if g.parent_goal_id is None]
        
        def build_tree(goal: StoryGoal) -> dict[str, Any]:
            children = [g for g in goals if g.parent_goal_id == goal.id]
            return {
                "id": str(goal.id),
                "name": goal.goal_name,
                "type": goal.goal_type,
                "status": goal.status,
                "progress": goal.progress,
                "priority": goal.priority,
                "children": [build_tree(child) for child in children],
            }
        
        return [build_tree(g) for g in root_goals]

    async def update_progress(
        self,
        goal_id: uuid.UUID,
        progress: float,
        *,
        status: str | None = None,
    ) -> StoryGoal:
        """Update goal progress."""
        goal = await self.get_or_404(goal_id)
        goal.progress = min(1.0, max(0.0, progress))
        
        if status:
            goal.status = status
        elif progress >= 1.0:
            goal.status = "completed"
        elif progress > 0:
            goal.status = "in_progress"
        
        await self.db.flush()
        await self.db.refresh(goal)
        return goal


class IntentRepository(BaseRepository[AuthorIntent]):
    """Author intent repository."""

    def __init__(self, db: AsyncSession):
        super().__init__(AuthorIntent, db)

    async def list_by_novel(
        self,
        novel_id: uuid.UUID,
        *,
        intent_type: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuthorIntent]:
        """List intents for a novel."""
        query = select(AuthorIntent).where(
            AuthorIntent.novel_id == novel_id,
            AuthorIntent.is_active == True,
        )

        if intent_type:
            query = query.where(AuthorIntent.intent_type == intent_type)

        query = query.order_by(AuthorIntent.priority.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())
