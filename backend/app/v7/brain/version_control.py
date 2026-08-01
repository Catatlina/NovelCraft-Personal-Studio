"""Version control system."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.state import StoryState
from ..repositories.version import VersionRepository, SnapshotRepository
from ..repositories.state import StoryStateRepository, StateChangeRepository
from ..repositories.event import EventLogRepository

# State types captured by a full snapshot.
SNAPSHOT_STATE_TYPES = ["global", "character", "world", "plot", "reader"]


class VersionControl:
    """Story version control system."""

    def __init__(self, db: AsyncSession, novel_id: uuid.UUID):
        self.db = db
        self.novel_id = novel_id
        self.version_repo = VersionRepository(db)
        self.snapshot_repo = SnapshotRepository(db)
        self.state_repo = StoryStateRepository(db)
        self.change_repo = StateChangeRepository(db)
        self.event_repo = EventLogRepository(db)

    async def list_versions(
        self,
        *,
        branch_name: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List versions."""
        versions = await self.version_repo.list_by_novel(
            self.novel_id,
            branch_name=branch_name,
            skip=skip,
            limit=limit,
        )
        return [
            {
                "id": str(v.id),
                "version_number": v.version_number,
                "version_type": v.version_type,
                "description": v.description,
                "branch_name": v.branch_name,
                "tag_name": v.tag_name,
                "created_by": v.created_by,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ]

    async def get_latest_version(
        self,
        *,
        branch_name: str = "main",
    ) -> dict[str, Any] | None:
        """Get latest version."""
        version = await self.version_repo.get_latest(
            self.novel_id, branch_name=branch_name
        )
        if version:
            return {
                "id": str(version.id),
                "version_number": version.version_number,
                "version_type": version.version_type,
                "description": version.description,
                "created_at": version.created_at.isoformat() if version.created_at else None,
            }
        return None

    async def create_snapshot(
        self,
        *,
        description: str | None = None,
        snapshot_type: str = "full",
        created_by: str = "system",
    ) -> dict[str, Any]:
        """Create a snapshot of current brain state."""
        all_states = await self._collect_states()

        snapshot = await self.snapshot_repo.create_snapshot(
            self.novel_id,
            all_states,
            snapshot_type=snapshot_type,
            description=description,
        )

        await self.event_repo.record_event(
            self.novel_id,
            "snapshot_created",
            f"Snapshot created: {snapshot_type}",
            "version",
            source=created_by,
            event_data={"snapshot_id": str(snapshot.id)},
        )

        return {
            "id": str(snapshot.id),
            "snapshot_type": snapshot.snapshot_type,
            "size_bytes": snapshot.size_bytes,
            "description": snapshot.description,
            "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        }

    async def create_version(
        self,
        *,
        version_type: str = "auto",
        description: str | None = None,
        branch_name: str = "main",
        tag_name: str | None = None,
        created_by: str = "system",
    ) -> dict[str, Any]:
        """Create a new version with snapshot."""
        # First create snapshot
        snapshot = await self.create_snapshot(
            description=description,
            snapshot_type="full",
            created_by=created_by,
        )

        # Then create version
        version = await self.version_repo.create_version(
            self.novel_id,
            version_type=version_type,
            description=description,
            snapshot_data={"snapshot_id": snapshot["id"]},
            branch_name=branch_name,
            tag_name=tag_name,
            created_by=created_by,
        )

        await self.event_repo.record_event(
            self.novel_id,
            "version_created",
            f"Version {version.version_number} created: {description or ''}",
            "version",
            source=created_by,
            event_data={
                "version_id": str(version.id),
                "version_number": version.version_number,
            },
        )

        return {
            "id": str(version.id),
            "version_number": version.version_number,
            "version_type": version.version_type,
            "description": version.description,
            "branch_name": version.branch_name,
            "tag_name": version.tag_name,
            "created_by": version.created_by,
            "created_at": version.created_at.isoformat() if version.created_at else None,
        }

    async def list_snapshots(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List snapshots."""
        snapshots = await self.snapshot_repo.list_by_novel(
            self.novel_id, skip=skip, limit=limit
        )
        return [
            {
                "id": str(s.id),
                "snapshot_type": s.snapshot_type,
                "description": s.description,
                "size_bytes": s.size_bytes,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in snapshots
        ]

    async def get_snapshot(self, snapshot_id: uuid.UUID) -> dict[str, Any] | None:
        """Get a snapshot with its full state payload."""
        snapshot = await self.snapshot_repo.get(snapshot_id)
        if not snapshot or snapshot.novel_id != self.novel_id:
            return None
        return {
            "id": str(snapshot.id),
            "snapshot_type": snapshot.snapshot_type,
            "description": snapshot.description,
            "size_bytes": snapshot.size_bytes,
            "state_count": len(self._flatten_snapshot(snapshot.state_data)),
            "state_data": snapshot.state_data,
            "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        }

    async def compare_snapshots(
        self,
        snapshot_a_id: uuid.UUID,
        snapshot_b_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Compare two snapshots and return the per-state differences.

        ``added`` / ``removed`` / ``modified`` are computed from A -> B.
        """
        snapshot_a = await self.snapshot_repo.get_or_404(snapshot_a_id)
        snapshot_b = await self.snapshot_repo.get_or_404(snapshot_b_id)

        for snap in (snapshot_a, snapshot_b):
            if snap.novel_id != self.novel_id:
                raise ValueError(f"Snapshot {snap.id} belongs to another novel")

        flat_a = self._flatten_snapshot(snapshot_a.state_data)
        flat_b = self._flatten_snapshot(snapshot_b.state_data)

        keys_a = set(flat_a)
        keys_b = set(flat_b)

        added = []
        for key in sorted(keys_b - keys_a):
            state_type, state_key = key
            added.append({
                "state_type": state_type,
                "state_key": state_key,
                "value": flat_b[key]["value"],
                "confidence": flat_b[key]["confidence"],
            })

        removed = []
        for key in sorted(keys_a - keys_b):
            state_type, state_key = key
            removed.append({
                "state_type": state_type,
                "state_key": state_key,
                "value": flat_a[key]["value"],
                "confidence": flat_a[key]["confidence"],
            })

        modified = []
        unchanged = 0
        for key in sorted(keys_a & keys_b):
            state_type, state_key = key
            entry_a = flat_a[key]
            entry_b = flat_b[key]
            value_changed = entry_a["value"] != entry_b["value"]
            confidence_changed = entry_a["confidence"] != entry_b["confidence"]
            if value_changed or confidence_changed:
                modified.append({
                    "state_type": state_type,
                    "state_key": state_key,
                    "old_value": entry_a["value"],
                    "new_value": entry_b["value"],
                    "old_confidence": entry_a["confidence"],
                    "new_confidence": entry_b["confidence"],
                    "value_changed": value_changed,
                    "confidence_changed": confidence_changed,
                })
            else:
                unchanged += 1

        return {
            "snapshot_a": {
                "id": str(snapshot_a.id),
                "description": snapshot_a.description,
                "created_at": snapshot_a.created_at.isoformat() if snapshot_a.created_at else None,
                "state_count": len(flat_a),
            },
            "snapshot_b": {
                "id": str(snapshot_b.id),
                "description": snapshot_b.description,
                "created_at": snapshot_b.created_at.isoformat() if snapshot_b.created_at else None,
                "state_count": len(flat_b),
            },
            "added": added,
            "removed": removed,
            "modified": modified,
            "unchanged_count": unchanged,
            "summary": {
                "added": len(added),
                "removed": len(removed),
                "modified": len(modified),
                "unchanged": unchanged,
                "identical": not added and not removed and not modified,
            },
        }

    async def rollback_to_snapshot(
        self,
        snapshot_id: uuid.UUID,
        *,
        user_id: uuid.UUID | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Roll the story state back to a snapshot.

        Restores every ``v7_story_states`` row captured by the snapshot, writes a
        ``v7_state_changes`` row per restored/deactivated state, and creates a
        new ``rollback`` version. Nothing is deleted: states created after the
        snapshot are deactivated (``is_active=False``) rather than dropped, and
        a safety snapshot of the pre-rollback state is taken first so the
        rollback itself is reversible.
        """
        snapshot = await self.snapshot_repo.get_or_404(snapshot_id)
        if snapshot.novel_id != self.novel_id:
            raise ValueError(f"Snapshot {snapshot_id} belongs to another novel")

        target_states = self._flatten_snapshot(snapshot.state_data)

        # 1. Safety snapshot so the rollback can itself be undone.
        current_states = await self._collect_states()
        safety_snapshot = await self.snapshot_repo.create_snapshot(
            self.novel_id,
            current_states,
            snapshot_type="pre_rollback",
            description=f"Pre-rollback safety snapshot (target={snapshot_id})",
        )

        # 2. Load every existing state row (including inactive ones).
        result = await self.db.execute(
            select(StoryState).where(StoryState.novel_id == self.novel_id)
        )
        existing_rows = list(result.scalars().all())
        existing_by_key: dict[tuple[str, str], StoryState] = {}
        for row in existing_rows:
            key = (row.state_type, row.state_key)
            current = existing_by_key.get(key)
            # Prefer the active row when duplicates exist.
            if current is None or (not current.is_active and row.is_active):
                existing_by_key[key] = row

        restored: list[dict[str, Any]] = []
        recreated: list[dict[str, Any]] = []
        deactivated: list[dict[str, Any]] = []
        unchanged = 0

        # 3. Restore states captured in the snapshot.
        for (state_type, state_key), entry in target_states.items():
            target_value = entry["value"]
            target_confidence = entry["confidence"]
            row = existing_by_key.get((state_type, state_key))

            if row is None:
                new_row = await self.state_repo.create({
                    "novel_id": self.novel_id,
                    "state_type": state_type,
                    "state_key": state_key,
                    "state_value": target_value,
                    "confidence": target_confidence,
                    "source": "imported",
                    "is_active": True,
                    "is_pending_review": False,
                })
                await self.change_repo.record_change(
                    self.novel_id,
                    new_row.id,
                    "rollback_create",
                    state_type,
                    state_key,
                    old_value=None,
                    new_value=target_value,
                    old_confidence=None,
                    new_confidence=target_confidence,
                    reason=reason or f"Rollback to snapshot {snapshot_id}",
                    source="human",
                    snapshot_id=snapshot_id,
                )
                recreated.append({"state_type": state_type, "state_key": state_key})
                continue

            value_differs = row.state_value != target_value
            confidence_differs = row.confidence != target_confidence
            if not value_differs and not confidence_differs and row.is_active:
                unchanged += 1
                continue

            old_value = row.state_value
            old_confidence = row.confidence
            version_before = row.version

            row.state_value = target_value
            row.confidence = target_confidence
            row.is_active = True
            row.is_pending_review = False
            row.version = version_before + 1
            await self.db.flush()

            await self.change_repo.record_change(
                self.novel_id,
                row.id,
                "rollback",
                state_type,
                state_key,
                old_value=old_value,
                new_value=target_value,
                old_confidence=old_confidence,
                new_confidence=target_confidence,
                reason=reason or f"Rollback to snapshot {snapshot_id}",
                source="human",
                snapshot_id=snapshot_id,
            )
            restored.append({
                "state_type": state_type,
                "state_key": state_key,
                "version_before": version_before,
                "version_after": row.version,
            })

        # 4. Deactivate states created after the snapshot (history preserved).
        for (state_type, state_key), row in existing_by_key.items():
            if (state_type, state_key) in target_states:
                continue
            if not row.is_active:
                continue

            old_value = row.state_value
            version_before = row.version
            row.is_active = False
            row.is_pending_review = False
            row.version = version_before + 1
            await self.db.flush()

            await self.change_repo.record_change(
                self.novel_id,
                row.id,
                "rollback_deactivate",
                state_type,
                state_key,
                old_value=old_value,
                new_value=None,
                old_confidence=row.confidence,
                new_confidence=None,
                reason=(
                    reason
                    or f"Rollback to snapshot {snapshot_id}: state not present in snapshot"
                ),
                source="human",
                snapshot_id=snapshot_id,
            )
            deactivated.append({"state_type": state_type, "state_key": state_key})

        # 5. Record the rollback as a new version (old versions are kept).
        parent_version = await self.version_repo.get_latest(self.novel_id)
        version = await self.version_repo.create_version(
            self.novel_id,
            version_type="rollback",
            description=f"Rollback to snapshot {snapshot_id}",
            snapshot_data={
                "rollback_to_snapshot": str(snapshot_id),
                "safety_snapshot_id": str(safety_snapshot.id),
                "restored_states": len(restored),
                "recreated_states": len(recreated),
                "deactivated_states": len(deactivated),
                "unchanged_states": unchanged,
                "reason": reason,
            },
            parent_version_id=parent_version.id if parent_version else None,
            created_by="human",
        )

        # Link the safety snapshot to the rollback version for traceability.
        safety_snapshot.version_id = version.id
        await self.db.flush()

        await self.event_repo.record_event(
            self.novel_id,
            "rollback",
            f"Rollback to snapshot {snapshot_id}",
            "version",
            source="human",
            source_user_id=user_id,
            severity="warning",
            description=reason,
            event_data={
                "snapshot_id": str(snapshot_id),
                "safety_snapshot_id": str(safety_snapshot.id),
                "version_id": str(version.id),
                "version_number": version.version_number,
                "restored_states": len(restored),
                "recreated_states": len(recreated),
                "deactivated_states": len(deactivated),
                "unchanged_states": unchanged,
                "reason": reason,
            },
        )

        return {
            "version_id": str(version.id),
            "version_number": version.version_number,
            "snapshot_id": str(snapshot_id),
            "safety_snapshot_id": str(safety_snapshot.id),
            "status": "rolled_back",
            "restored_states": len(restored),
            "recreated_states": len(recreated),
            "deactivated_states": len(deactivated),
            "unchanged_states": unchanged,
            "restored": restored,
            "recreated": recreated,
            "deactivated": deactivated,
        }

    # ── Internals ────────────────────────────────────────────────────────

    async def _collect_states(self) -> dict[str, list[dict[str, Any]]]:
        """Collect all active states grouped by state type."""
        all_states: dict[str, list[dict[str, Any]]] = {}
        for state_type in SNAPSHOT_STATE_TYPES:
            type_states = await self.state_repo.list_by_type(
                self.novel_id, state_type, limit=500
            )
            all_states[state_type] = [
                {
                    "key": s.state_key,
                    "value": s.state_value,
                    "confidence": s.confidence,
                }
                for s in type_states
            ]
        return all_states

    @staticmethod
    def _flatten_snapshot(
        state_data: dict[str, Any] | None,
    ) -> dict[tuple[str, str], dict[str, Any]]:
        """Flatten a snapshot payload into {(state_type, state_key): entry}."""
        if not state_data:
            return {}

        # Tolerate the legacy {"states": {...}} wrapper.
        payload = state_data.get("states") if isinstance(
            state_data.get("states"), dict
        ) else state_data

        flat: dict[tuple[str, str], dict[str, Any]] = {}
        for state_type, entries in payload.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict) or "key" not in entry:
                    continue
                flat[(state_type, entry["key"])] = {
                    "value": entry.get("value"),
                    "confidence": entry.get("confidence", 0.9),
                }
        return flat
