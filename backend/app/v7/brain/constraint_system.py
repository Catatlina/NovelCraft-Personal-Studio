"""Constraint system."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.constraint import ConstraintRepository
from ..repositories.event import EventLogRepository


class ConstraintSystem:
    """Story constraint system."""

    def __init__(self, db: AsyncSession, novel_id: uuid.UUID):
        self.db = db
        self.novel_id = novel_id
        self.constraint_repo = ConstraintRepository(db)
        self.event_repo = EventLogRepository(db)

    async def list_constraints(
        self,
        *,
        constraint_type: str | None = None,
        severity: str | None = None,
        is_active: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List constraints."""
        constraints = await self.constraint_repo.list_by_novel(
            self.novel_id,
            constraint_type=constraint_type,
            severity=severity,
            is_active=is_active,
            skip=skip,
            limit=limit,
        )
        return [
            {
                "id": str(c.id),
                "type": c.constraint_type,
                "name": c.constraint_name,
                "description": c.description,
                "value": c.constraint_value,
                "severity": c.severity,
                "check_method": c.check_method,
                "priority": c.priority,
                "violation_count": c.violation_count,
                "last_violation_at": c.last_violation_at.isoformat() if c.last_violation_at else None,
            }
            for c in constraints
        ]

    async def create_constraint(
        self,
        constraint_type: str,
        constraint_name: str,
        constraint_value: dict[str, Any],
        *,
        description: str | None = None,
        severity: str = "warning",
        check_method: str = "ai_review",
        priority: int = 50,
    ) -> dict[str, Any]:
        """Create a new constraint."""
        constraint = await self.constraint_repo.create({
            "novel_id": self.novel_id,
            "constraint_type": constraint_type,
            "constraint_name": constraint_name,
            "description": description,
            "constraint_value": constraint_value,
            "severity": severity,
            "check_method": check_method,
            "priority": priority,
        })

        await self.event_repo.record_event(
            self.novel_id,
            "constraint_created",
            f"Constraint created: {constraint_name} ({severity})",
            "constraint",
            source="human",
            event_data={"constraint_id": str(constraint.id)},
        )

        return {
            "id": str(constraint.id),
            "name": constraint.constraint_name,
            "type": constraint.constraint_type,
            "severity": constraint.severity,
        }

    async def update_constraint(
        self,
        constraint_id: uuid.UUID,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update a constraint."""
        constraint = await self.constraint_repo.update(constraint_id, data)

        await self.event_repo.record_event(
            self.novel_id,
            "constraint_updated",
            f"Constraint updated: {constraint.constraint_name}",
            "constraint",
            source="human",
            event_data={"constraint_id": str(constraint.id)},
        )

        return {
            "id": str(constraint.id),
            "name": constraint.constraint_name,
            "severity": constraint.severity,
            "is_active": constraint.is_active,
        }

    async def delete_constraint(
        self,
        constraint_id: uuid.UUID,
    ) -> None:
        """Delete a constraint (soft delete)."""
        await self.constraint_repo.update(constraint_id, {"is_active": False})

        await self.event_repo.record_event(
            self.novel_id,
            "constraint_deleted",
            f"Constraint deleted: {constraint_id}",
            "constraint",
            source="human",
            severity="warning",
            event_data={"constraint_id": str(constraint_id)},
        )

    async def record_violation(
        self,
        constraint_id: uuid.UUID,
        *,
        source: str = "ai",
        source_run_id: uuid.UUID | None = None,
        details: str | None = None,
    ) -> dict[str, Any]:
        """Record a constraint violation."""
        constraint = await self.constraint_repo.check_violation(constraint_id)

        await self.event_repo.record_event(
            self.novel_id,
            "constraint_violation",
            f"Constraint violation: {constraint.constraint_name} ({constraint.severity})",
            "constraint",
            source=source,
            source_run_id=source_run_id,
            severity="error" if constraint.severity in ("error", "blocking") else "warning",
            event_data={
                "constraint_id": str(constraint_id),
                "violation_count": constraint.violation_count,
                "details": details,
            },
        )

        return {
            "id": str(constraint.id),
            "name": constraint.constraint_name,
            "violation_count": constraint.violation_count,
            "severity": constraint.severity,
        }

    async def check_constraints(
        self,
        text: str,
        *,
        constraint_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Check constraints against text.
        
        Alpha implementation: returns list of constraints that need AI review.
        Actual checking will be done by Review Engine in Sprint 2.
        """
        constraints = await self.constraint_repo.list_by_novel(
            self.novel_id,
            is_active=True,
        )

        if constraint_types:
            constraints = [
                c for c in constraints
                if c.constraint_type in constraint_types
            ]

        # Return constraints that need AI review
        return [
            {
                "id": str(c.id),
                "name": c.constraint_name,
                "type": c.constraint_type,
                "severity": c.severity,
                "check_method": c.check_method,
                "value": c.constraint_value,
            }
            for c in constraints
            if c.check_method == "ai_review"
        ]
