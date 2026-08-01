"""Human intervention service.

Single write-path for everything a human does to a novel's brain:
state edits, approvals, rejections, rollbacks and instruction injection.
Every operation lands in ``v7_human_interventions`` and mirrors an entry
into ``v7_event_logs`` so the audit trail stays consistent.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.human import HumanIntervention
from ..repositories.human import HumanInterventionRepository
from ..repositories.event import EventLogRepository
from ..repositories.decision import DecisionLogRepository
from ..repositories.state import StoryStateRepository, StateChangeRepository

# State slot used to hand human instructions over to the generation pipeline.
INSTRUCTION_STATE_TYPE = "global"
INSTRUCTION_STATE_KEY = "human_instructions"

# Severity mapping per intervention type for the mirrored event log entry.
_EVENT_SEVERITY = {
    "state_edit": "info",
    "decision_approve": "info",
    "decision_reject": "warning",
    "state_approve": "info",
    "state_reject": "warning",
    "rollback": "warning",
    "instruction": "info",
    "pause": "warning",
    "resume": "info",
    "override": "warning",
}


class HumanInterventionService:
    """Records and queries human interventions for one novel."""

    def __init__(self, db: AsyncSession, novel_id: uuid.UUID):
        self.db = db
        self.novel_id = novel_id
        self.repo = HumanInterventionRepository(db)
        self.event_repo = EventLogRepository(db)
        self.decision_repo = DecisionLogRepository(db)
        self.state_repo = StoryStateRepository(db)
        self.change_repo = StateChangeRepository(db)

    # ── Core write path ──────────────────────────────────────────────────

    async def record(
        self,
        intervention_type: str,
        target_type: str,
        action: str,
        *,
        target_id: uuid.UUID | None = None,
        description: str | None = None,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        reason: str | None = None,
        user_id: uuid.UUID | str | None = None,
        run_id: uuid.UUID | None = None,
        result: str = "success",
        extra_metadata: dict[str, Any] | None = None,
        emit_event: bool = True,
    ) -> dict[str, Any]:
        """Record one human intervention and mirror it to the event log."""
        user_uuid, user_label = self._normalize_user(user_id)
        if user_label:
            extra_metadata = {**(extra_metadata or {}), "user_label": user_label}

        intervention = await self.repo.record_intervention(
            self.novel_id,
            intervention_type,
            target_type,
            action,
            target_id=target_id,
            description=description,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            user_id=user_uuid,
            run_id=run_id,
            result=result,
            extra_metadata=extra_metadata,
        )

        if emit_event:
            await self.event_repo.record_event(
                self.novel_id,
                f"human_{intervention_type}",
                description or f"Human {action} on {target_type}",
                "human",
                source="human",
                source_run_id=run_id,
                source_user_id=user_uuid,
                severity=_EVENT_SEVERITY.get(intervention_type, "info"),
                description=reason,
                event_data={
                    "intervention_id": str(intervention.id),
                    "intervention_type": intervention_type,
                    "target_type": target_type,
                    "target_id": str(target_id) if target_id else None,
                    "action": action,
                    "result": result,
                    "user_label": user_label,
                },
            )

        return self._to_dict(intervention)

    @staticmethod
    def _normalize_user(
        user_id: uuid.UUID | str | None,
    ) -> tuple[uuid.UUID | None, str | None]:
        """Split a caller identity into a UUID and/or a free-text label.

        ``v7_human_interventions.user_id`` is a UUID column, but a personal
        studio often identifies the operator by name ("author"). Non-UUID
        identities are kept as ``extra_metadata.user_label`` instead of being
        rejected.
        """
        if user_id is None:
            return None, None
        if isinstance(user_id, uuid.UUID):
            return user_id, None
        text = str(user_id).strip()
        if not text:
            return None, None
        try:
            return uuid.UUID(text), None
        except ValueError:
            return None, text

    # ── Typed helpers ────────────────────────────────────────────────────

    async def record_state_edit(
        self,
        state_id: uuid.UUID | None,
        *,
        state_type: str,
        state_key: str,
        old_value: dict[str, Any] | None,
        new_value: dict[str, Any] | None,
        reason: str | None = None,
        user_id: uuid.UUID | str | None = None,
        run_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Record a manual state modification."""
        return await self.record(
            "state_edit",
            "state",
            "update",
            target_id=state_id,
            description=f"Human edited state {state_type}/{state_key}",
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            user_id=user_id,
            run_id=run_id,
            extra_metadata={"state_type": state_type, "state_key": state_key},
        )

    async def record_state_review(
        self,
        state_id: uuid.UUID,
        approved: bool,
        *,
        state_type: str,
        state_key: str,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        reason: str | None = None,
        user_id: uuid.UUID | str | None = None,
    ) -> dict[str, Any]:
        """Record approval/rejection of a pending-review state."""
        return await self.record(
            "state_approve" if approved else "state_reject",
            "state",
            "approve" if approved else "reject",
            target_id=state_id,
            description=(
                f"Human {'approved' if approved else 'rejected'} "
                f"state {state_type}/{state_key}"
            ),
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            user_id=user_id,
            extra_metadata={"state_type": state_type, "state_key": state_key},
        )

    async def record_decision_review(
        self,
        decision_id: uuid.UUID,
        approved: bool,
        *,
        decision_type: str,
        old_status: str,
        new_status: str,
        reason: str | None = None,
        user_id: uuid.UUID | str | None = None,
        run_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Record approval/rejection of a pending decision."""
        return await self.record(
            "decision_approve" if approved else "decision_reject",
            "decision",
            "approve" if approved else "reject",
            target_id=decision_id,
            description=(
                f"Human {'approved' if approved else 'rejected'} "
                f"decision {decision_type}"
            ),
            old_value={"status": old_status},
            new_value={"status": new_status, "decided_by": "human"},
            reason=reason,
            user_id=user_id,
            run_id=run_id,
            extra_metadata={"decision_type": decision_type},
        )

    async def record_rollback(
        self,
        snapshot_id: uuid.UUID,
        *,
        version_id: uuid.UUID | None = None,
        restored_states: int = 0,
        deactivated_states: int = 0,
        safety_snapshot_id: uuid.UUID | None = None,
        reason: str | None = None,
        user_id: uuid.UUID | str | None = None,
        result: str = "success",
    ) -> dict[str, Any]:
        """Record a version rollback."""
        return await self.record(
            "rollback",
            "version",
            "rollback",
            target_id=snapshot_id,
            description=f"Human rolled back to snapshot {snapshot_id}",
            old_value={"safety_snapshot_id": str(safety_snapshot_id)
                       if safety_snapshot_id else None},
            new_value={
                "snapshot_id": str(snapshot_id),
                "version_id": str(version_id) if version_id else None,
                "restored_states": restored_states,
                "deactivated_states": deactivated_states,
            },
            reason=reason,
            user_id=user_id,
            result=result,
        )

    async def review_decision(
        self,
        decision_id: uuid.UUID,
        approved: bool,
        *,
        reason: str | None = None,
        user_id: uuid.UUID | str | None = None,
    ) -> dict[str, Any]:
        """Apply a human approve/reject to a decision log entry.

        Flips ``v7_decision_logs.status`` from ``pending`` to
        ``approved``/``rejected``, stamps ``decided_by='human'`` plus the
        decision timestamp, and records the matching human intervention.

        Raises ``LookupError`` when the decision does not exist for this novel
        and ``ValueError`` when it is not pending.
        """
        decision = await self.decision_repo.get(decision_id)
        if not decision or decision.novel_id != self.novel_id:
            raise LookupError(f"Decision not found: {decision_id}")

        if decision.status != "pending":
            raise ValueError(
                f"Decision {decision_id} is not pending "
                f"(current status: {decision.status})"
            )

        old_status = decision.status
        new_status = "approved" if approved else "rejected"
        user_uuid, _user_label = self._normalize_user(user_id)

        decision.status = new_status
        decision.decision = "approve" if approved else "reject"
        decision.decided_by = "human"
        decision.decided_by_user_id = user_uuid
        decision.decided_at = datetime.now(timezone.utc)
        decision.decision_reason = reason or (
            "Human approved" if approved else "Human rejected"
        )
        await self.db.flush()
        await self.db.refresh(decision)

        intervention = await self.record_decision_review(
            decision_id,
            approved,
            decision_type=decision.decision_type,
            old_status=old_status,
            new_status=new_status,
            reason=decision.decision_reason,
            user_id=user_id,
            run_id=decision.run_id,
        )

        return {
            "decision_id": str(decision.id),
            "decision_type": decision.decision_type,
            "decision": decision.decision,
            "status": decision.status,
            "previous_status": old_status,
            "decided_by": decision.decided_by,
            "decided_at": decision.decided_at.isoformat() if decision.decided_at else None,
            "decision_reason": decision.decision_reason,
            "intervention_id": intervention["id"],
        }

    # ── Instruction injection ────────────────────────────────────────────

    async def inject_instruction(
        self,
        instruction: str,
        *,
        scope: str = "next_chapter",
        target_chapter: int | None = None,
        priority: int = 50,
        reason: str | None = None,
        user_id: uuid.UUID | str | None = None,
        run_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Inject a human instruction for the next generation run.

        Writes both an intervention record and the ``global/human_instructions``
        story state so the generation pipeline can pick it up.
        """
        instruction = instruction.strip()
        if not instruction:
            raise ValueError("instruction must not be empty")

        state = await self.state_repo.get_by_key(
            self.novel_id, INSTRUCTION_STATE_TYPE, INSTRUCTION_STATE_KEY
        )
        old_value = dict(state.state_value) if state else None
        pending: list[dict[str, Any]] = []
        applied: list[dict[str, Any]] = []
        if state and isinstance(state.state_value, dict):
            pending = list(state.state_value.get("pending") or [])
            applied = list(state.state_value.get("applied") or [])

        entry = {
            "id": str(uuid.uuid4()),
            "instruction": instruction,
            "scope": scope,
            "target_chapter": target_chapter,
            "priority": priority,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
        }
        pending.append(entry)
        pending.sort(key=lambda i: i.get("priority", 50), reverse=True)

        new_value: dict[str, Any] = {
            "pending": pending,
            "applied": applied,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        if state:
            state.state_value = new_value
            state.confidence = 1.0
            state.source = "human_set"
            state.version += 1
            state.is_pending_review = False
            state.is_active = True
            await self.db.flush()
            await self.db.refresh(state)
            change_type = "update"
        else:
            state = await self.state_repo.create({
                "novel_id": self.novel_id,
                "state_type": INSTRUCTION_STATE_TYPE,
                "state_key": INSTRUCTION_STATE_KEY,
                "state_value": new_value,
                "confidence": 1.0,
                "source": "human_set",
                "is_pending_review": False,
            })
            change_type = "create"

        await self.change_repo.record_change(
            self.novel_id,
            state.id,
            change_type,
            INSTRUCTION_STATE_TYPE,
            INSTRUCTION_STATE_KEY,
            old_value=old_value,
            new_value=new_value,
            old_confidence=None,
            new_confidence=1.0,
            reason=reason or "Human instruction injected",
            source="human",
            source_run_id=run_id,
        )

        intervention = await self.record(
            "instruction",
            "state",
            "inject",
            target_id=state.id,
            description=f"Human instruction injected (scope={scope})",
            old_value=old_value,
            new_value={"instruction": entry},
            reason=reason,
            user_id=user_id,
            run_id=run_id,
            extra_metadata={
                "instruction_id": entry["id"],
                "scope": scope,
                "target_chapter": target_chapter,
                "priority": priority,
            },
        )

        return {
            "intervention": intervention,
            "instruction": entry,
            "state_id": str(state.id),
            "pending_count": len(pending),
        }

    async def get_pending_instructions(
        self,
        *,
        target_chapter: int | None = None,
    ) -> list[dict[str, Any]]:
        """Read pending human instructions for the generation pipeline."""
        state = await self.state_repo.get_by_key(
            self.novel_id, INSTRUCTION_STATE_TYPE, INSTRUCTION_STATE_KEY
        )
        if not state or not isinstance(state.state_value, dict):
            return []

        pending = list(state.state_value.get("pending") or [])
        if target_chapter is not None:
            pending = [
                i for i in pending
                if i.get("target_chapter") in (None, target_chapter)
            ]
        return pending

    async def mark_instructions_applied(
        self,
        instruction_ids: list[str],
        *,
        chapter_number: int | None = None,
    ) -> dict[str, Any]:
        """Move instructions from pending to applied after a generation run."""
        state = await self.state_repo.get_by_key(
            self.novel_id, INSTRUCTION_STATE_TYPE, INSTRUCTION_STATE_KEY
        )
        if not state or not isinstance(state.state_value, dict):
            return {"applied": 0, "pending": 0}

        wanted = set(instruction_ids)
        pending = list(state.state_value.get("pending") or [])
        applied = list(state.state_value.get("applied") or [])

        still_pending = []
        moved = 0
        for item in pending:
            if item.get("id") in wanted:
                item["status"] = "applied"
                item["applied_at"] = datetime.now(timezone.utc).isoformat()
                item["applied_chapter"] = chapter_number
                applied.append(item)
                moved += 1
            else:
                still_pending.append(item)

        state.state_value = {
            "pending": still_pending,
            "applied": applied,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        state.version += 1
        await self.db.flush()
        await self.db.refresh(state)

        return {"applied": moved, "pending": len(still_pending)}

    # ── Queries ──────────────────────────────────────────────────────────

    async def list_interventions(
        self,
        *,
        intervention_type: str | None = None,
        target_type: str | None = None,
        target_id: uuid.UUID | None = None,
        result: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List interventions for this novel."""
        items = await self.repo.list_by_novel(
            self.novel_id,
            intervention_type=intervention_type,
            target_type=target_type,
            target_id=target_id,
            result=result,
            skip=skip,
            limit=limit,
        )
        return [self._to_dict(i) for i in items]

    async def count_interventions(
        self,
        *,
        intervention_type: str | None = None,
        target_type: str | None = None,
        target_id: uuid.UUID | None = None,
        result: str | None = None,
    ) -> int:
        """Count interventions for this novel."""
        return await self.repo.count_by_novel(
            self.novel_id,
            intervention_type=intervention_type,
            target_type=target_type,
            target_id=target_id,
            result=result,
        )

    async def get_stats(self) -> dict[str, Any]:
        """Intervention counters grouped by type."""
        by_type = await self.repo.count_by_type(self.novel_id)
        return {
            "novel_id": str(self.novel_id),
            "total": sum(by_type.values()),
            "by_type": by_type,
        }

    # ── Serialization ────────────────────────────────────────────────────

    @staticmethod
    def _to_dict(item: HumanIntervention) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "novel_id": str(item.novel_id),
            "intervention_type": item.intervention_type,
            "target_type": item.target_type,
            "target_id": str(item.target_id) if item.target_id else None,
            "action": item.action,
            "description": item.description,
            "old_value": item.old_value,
            "new_value": item.new_value,
            "reason": item.reason,
            "user_id": str(item.user_id) if item.user_id else None,
            "run_id": str(item.run_id) if item.run_id else None,
            "result": item.result,
            "extra_metadata": item.extra_metadata,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
