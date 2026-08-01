"""Constraint system repository."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from ..models.constraint import Constraint


class ConstraintRepository(BaseRepository[Constraint]):
    """Constraint repository."""

    def __init__(self, db: AsyncSession):
        super().__init__(Constraint, db)

    async def list_by_novel(
        self,
        novel_id: uuid.UUID,
        *,
        constraint_type: str | None = None,
        severity: str | None = None,
        is_active: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Constraint]:
        """List constraints for a novel."""
        query = select(Constraint).where(
            Constraint.novel_id == novel_id,
            Constraint.is_active == is_active,
        )

        if constraint_type:
            query = query.where(Constraint.constraint_type == constraint_type)
        if severity:
            query = query.where(Constraint.severity == severity)

        query = query.order_by(Constraint.priority.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def check_violation(
        self,
        constraint_id: uuid.UUID,
    ) -> Constraint:
        """Record a constraint violation."""
        constraint = await self.get_or_404(constraint_id)
        constraint.violation_count += 1
        await self.db.flush()
        await self.db.refresh(constraint)
        return constraint
