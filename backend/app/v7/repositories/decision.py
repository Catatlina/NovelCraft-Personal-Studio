"""Decision system repositories."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from ..models.decision import DecisionPermission, DecisionLog


class DecisionPermissionRepository(BaseRepository[DecisionPermission]):
    """Decision permission repository."""

    def __init__(self, db: AsyncSession):
        super().__init__(DecisionPermission, db)

    async def get_by_type(
        self,
        novel_id: uuid.UUID,
        decision_type: str,
    ) -> DecisionPermission | None:
        """Get permission by decision type."""
        result = await self.db.execute(
            select(DecisionPermission).where(
                DecisionPermission.novel_id == novel_id,
                DecisionPermission.decision_type == decision_type,
                DecisionPermission.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_novel(
        self,
        novel_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[DecisionPermission]:
        """List permissions for a novel."""
        result = await self.db.execute(
            select(DecisionPermission).where(
                DecisionPermission.novel_id == novel_id,
                DecisionPermission.is_active == True,
            )
            .order_by(DecisionPermission.priority.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_permission_level(
        self,
        novel_id: uuid.UUID,
        decision_type: str,
    ) -> str:
        """Get permission level for a decision type."""
        perm = await self.get_by_type(novel_id, decision_type)
        if perm:
            return perm.permission_level
        return "auto"  # default


class DecisionLogRepository(BaseRepository[DecisionLog]):
    """Decision log repository."""

    def __init__(self, db: AsyncSession):
        super().__init__(DecisionLog, db)

    async def list_by_novel(
        self,
        novel_id: uuid.UUID,
        *,
        decision_type: str | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[DecisionLog]:
        """List decision logs for a novel."""
        query = select(DecisionLog).where(DecisionLog.novel_id == novel_id)

        if decision_type:
            query = query.where(DecisionLog.decision_type == decision_type)
        if status:
            query = query.where(DecisionLog.status == status)

        query = query.order_by(DecisionLog.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_by_run(
        self,
        run_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[DecisionLog]:
        """List decision logs for a run."""
        result = await self.db.execute(
            select(DecisionLog).where(DecisionLog.run_id == run_id)
            .order_by(DecisionLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def record_decision(
        self,
        novel_id: uuid.UUID,
        decision_type: str,
        decision: str,
        *,
        decision_reason: str | None = None,
        confidence: float = 0.9,
        permission_level: str = "auto",
        status: str = "completed",
        run_id: uuid.UUID | None = None,
        context: dict[str, Any] | None = None,
        alternatives: list[dict[str, Any]] | None = None,
        decided_by: str = "ai",
    ) -> DecisionLog:
        """Record a decision.

        ``decision`` is a short verb column (varchar 50). Long text is moved
        into ``decision_reason`` instead of overflowing the column, so a verbose
        caller degrades gracefully rather than aborting the transaction.
        """
        decision = (decision or "").strip()
        if len(decision) > 50:
            overflow = decision
            decision = decision[:47] + "..."
            decision_reason = (
                f"{overflow}\n{decision_reason}" if decision_reason else overflow
            )

        return await self.create({
            "novel_id": novel_id,
            "decision_type": decision_type,
            "decision": decision,
            "decision_reason": decision_reason,
            "confidence": confidence,
            "permission_level": permission_level,
            "status": status,
            "run_id": run_id,
            "context": context or {},
            "alternatives": alternatives or [],
            "decided_by": decided_by,
        })
