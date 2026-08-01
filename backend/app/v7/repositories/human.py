"""Human intervention repository."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from ..models.human import HumanIntervention


class HumanInterventionRepository(BaseRepository[HumanIntervention]):
    """Human intervention repository."""

    def __init__(self, db: AsyncSession):
        super().__init__(HumanIntervention, db)

    async def list_by_novel(
        self,
        novel_id: uuid.UUID,
        *,
        intervention_type: str | None = None,
        target_type: str | None = None,
        target_id: uuid.UUID | None = None,
        result: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[HumanIntervention]:
        """List interventions for a novel."""
        query = select(HumanIntervention).where(
            HumanIntervention.novel_id == novel_id
        )

        if intervention_type:
            query = query.where(
                HumanIntervention.intervention_type == intervention_type
            )
        if target_type:
            query = query.where(HumanIntervention.target_type == target_type)
        if target_id:
            query = query.where(HumanIntervention.target_id == target_id)
        if result:
            query = query.where(HumanIntervention.result == result)

        query = (
            query.order_by(HumanIntervention.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        db_result = await self.db.execute(query)
        return list(db_result.scalars().all())

    async def count_by_novel(
        self,
        novel_id: uuid.UUID,
        *,
        intervention_type: str | None = None,
        target_type: str | None = None,
        target_id: uuid.UUID | None = None,
        result: str | None = None,
    ) -> int:
        """Count interventions for a novel."""
        query = select(func.count()).select_from(HumanIntervention).where(
            HumanIntervention.novel_id == novel_id
        )

        if intervention_type:
            query = query.where(
                HumanIntervention.intervention_type == intervention_type
            )
        if target_type:
            query = query.where(HumanIntervention.target_type == target_type)
        if target_id:
            query = query.where(HumanIntervention.target_id == target_id)
        if result:
            query = query.where(HumanIntervention.result == result)

        db_result = await self.db.execute(query)
        return db_result.scalar_one()

    async def list_by_target(
        self,
        novel_id: uuid.UUID,
        target_type: str,
        target_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[HumanIntervention]:
        """List interventions against a specific target object."""
        result = await self.db.execute(
            select(HumanIntervention)
            .where(
                HumanIntervention.novel_id == novel_id,
                HumanIntervention.target_type == target_type,
                HumanIntervention.target_id == target_id,
            )
            .order_by(HumanIntervention.created_at.desc())
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
    ) -> list[HumanIntervention]:
        """List interventions attached to a run."""
        result = await self.db.execute(
            select(HumanIntervention)
            .where(HumanIntervention.run_id == run_id)
            .order_by(HumanIntervention.created_at.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_by_type(self, novel_id: uuid.UUID) -> dict[str, int]:
        """Aggregate intervention counts grouped by intervention_type."""
        result = await self.db.execute(
            select(
                HumanIntervention.intervention_type,
                func.count().label("count"),
            )
            .where(HumanIntervention.novel_id == novel_id)
            .group_by(HumanIntervention.intervention_type)
        )
        return {row[0]: row[1] for row in result.all()}

    async def record_intervention(
        self,
        novel_id: uuid.UUID,
        intervention_type: str,
        target_type: str,
        action: str,
        *,
        target_id: uuid.UUID | None = None,
        description: str | None = None,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        reason: str | None = None,
        user_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
        result: str = "success",
        extra_metadata: dict[str, Any] | None = None,
    ) -> HumanIntervention:
        """Record a human intervention."""
        return await self.create({
            "novel_id": novel_id,
            "intervention_type": intervention_type,
            "target_type": target_type,
            "target_id": target_id,
            "action": action,
            "description": description,
            "old_value": old_value,
            "new_value": new_value,
            "reason": reason,
            "user_id": user_id,
            "run_id": run_id,
            "result": result,
            "extra_metadata": extra_metadata or {},
        })
