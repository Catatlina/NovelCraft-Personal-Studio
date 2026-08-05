"""Novel Brain - main brain class."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .state_manager import StoryStateManager
from .goal_system import GoalSystem
from .constraint_system import ConstraintSystem
from .version_control import VersionControl
from .truth_store import TruthStore
from ..quality.rule_learning import RuleLearningStore, QualityPatternLearningStore
from ..repositories.decision import DecisionLogRepository
from ..repositories.event import EventLogRepository


class NovelBrain:
    """
    Novel Brain - the core of V7.
    
    Manages all story state, goals, constraints, versions, and decisions.
    """

    def __init__(self, db: AsyncSession, novel_id: uuid.UUID):
        self.db = db
        self.novel_id = novel_id
        
        # Subsystems
        self.state = StoryStateManager(db, novel_id)
        self.goals = GoalSystem(db, novel_id)
        self.constraints = ConstraintSystem(db, novel_id)
        self.versions = VersionControl(db, novel_id)
        # Existing v7_story_states remains the single source of truth.  These
        # two facades expose structured truth domains and controlled rule
        # learning without introducing a parallel storage system.
        self.truth = TruthStore(self.state)
        self.rules = RuleLearningStore(self.state)
        self.quality_learning = QualityPatternLearningStore(self.state)
        
        # Repositories
        self.decision_repo = DecisionLogRepository(db)
        self.event_repo = EventLogRepository(db)

    async def get_overview(self) -> dict[str, Any]:
        """Get brain overview statistics."""
        # Count states by type
        state_types = [
            "global", "character", "world", "plot", "reader", "chapter",
            "learning_rule", "learning_quality",
        ]
        state_counts = {}
        pending_review_count = 0
        
        for state_type in state_types:
            states = await self.state.list_states(state_type, limit=500)
            state_counts[state_type] = len(states)
            pending_review_count += sum(1 for s in states if s.get("is_pending_review"))

        # Count goals
        goals = await self.goals.list_goals(limit=500)
        goal_counts = {
            "total": len(goals),
            "completed": sum(1 for g in goals if g["status"] == "completed"),
            "in_progress": sum(1 for g in goals if g["status"] == "in_progress"),
            "pending": sum(1 for g in goals if g["status"] == "pending"),
        }

        # Count constraints
        constraints = await self.constraints.list_constraints(limit=500)
        constraint_counts = {
            "total": len(constraints),
            "active": sum(1 for c in constraints if c.get("severity")),
        }

        # Get latest version
        latest_version = await self.versions.get_latest_version()

        # Get recent events
        recent_events = await self.event_repo.list_by_novel(
            self.novel_id, limit=10
        )

        return {
            "novel_id": str(self.novel_id),
            "states": {
                "by_type": state_counts,
                "total": sum(state_counts.values()),
                "pending_review": pending_review_count,
            },
            "goals": goal_counts,
            "constraints": constraint_counts,
            "latest_version": latest_version,
            "recent_events": [
                {
                    "id": str(e.id),
                    "type": e.event_type,
                    "name": e.event_name,
                    "category": e.event_category,
                    "severity": e.severity,
                    "time": e.event_time.isoformat() if e.event_time else None,
                }
                for e in recent_events
            ],
        }

    async def record_decision(
        self,
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
    ) -> dict[str, Any]:
        """Record a decision."""
        decision_log = await self.decision_repo.record_decision(
            self.novel_id,
            decision_type,
            decision,
            decision_reason=decision_reason,
            confidence=confidence,
            permission_level=permission_level,
            status=status,
            run_id=run_id,
            context=context,
            alternatives=alternatives,
            decided_by=decided_by,
        )

        await self.event_repo.record_event(
            self.novel_id,
            "decision_made",
            f"Decision: {decision_type} = {decision}",
            "decision",
            source=decided_by,
            source_run_id=run_id,
            event_data={
                "decision_id": str(decision_log.id),
                "decision_type": decision_type,
                "decision": decision,
                "confidence": confidence,
            },
        )

        return {
            "id": str(decision_log.id),
            "decision_type": decision_log.decision_type,
            "decision": decision_log.decision,
            "confidence": decision_log.confidence,
            "status": decision_log.status,
            "decided_by": decision_log.decided_by,
        }

    async def get_decision_logs(
        self,
        *,
        decision_type: str | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get decision logs."""
        logs = await self.decision_repo.list_by_novel(
            self.novel_id,
            decision_type=decision_type,
            status=status,
            skip=skip,
            limit=limit,
        )
        return [
            {
                "id": str(l.id),
                "decision_type": l.decision_type,
                "decision": l.decision,
                "reason": l.decision_reason,
                "confidence": l.confidence,
                "permission_level": l.permission_level,
                "status": l.status,
                "decided_by": l.decided_by,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ]

    async def get_events(
        self,
        *,
        event_type: str | None = None,
        event_category: str | None = None,
        severity: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get event log."""
        events = await self.event_repo.list_by_novel(
            self.novel_id,
            event_type=event_type,
            event_category=event_category,
            severity=severity,
            skip=skip,
            limit=limit,
        )
        return [
            {
                "id": str(e.id),
                "type": e.event_type,
                "name": e.event_name,
                "category": e.event_category,
                "severity": e.severity,
                "description": e.description,
                "source": e.source,
                "time": e.event_time.isoformat() if e.event_time else None,
                "data": e.event_data,
            }
            for e in events
        ]
