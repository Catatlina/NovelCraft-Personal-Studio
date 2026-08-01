"""Version control system."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.version import VersionRepository, SnapshotRepository
from ..repositories.state import StoryStateRepository
from ..repositories.event import EventLogRepository


class VersionControl:
    """Story version control system."""

    def __init__(self, db: AsyncSession, novel_id: uuid.UUID):
        self.db = db
        self.novel_id = novel_id
        self.version_repo = VersionRepository(db)
        self.snapshot_repo = SnapshotRepository(db)
        self.state_repo = StoryStateRepository(db)
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
        # Collect all states
        states = await self.state_repo.list_by_type(
            self.novel_id, "global", limit=500
        )
        # Also collect other state types
        all_states = {}
        for state_type in ["global", "character", "world", "plot", "reader"]:
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

        snapshot_data = {
            "states": all_states,
            "snapshot_type": snapshot_type,
            "created_at": description,
        }

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

    async def rollback_to_snapshot(
        self,
        snapshot_id: uuid.UUID,
        *,
        user_id: uuid.UUID | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """
        Rollback to a snapshot.
        
        Alpha implementation: creates a new version marked as rollback.
        Actual state restoration will be implemented in Sprint 2.
        """
        snapshot = await self.snapshot_repo.get_or_404(snapshot_id)

        # Create a new version as rollback marker
        version = await self.version_repo.create_version(
            self.novel_id,
            version_type="rollback",
            description=f"Rollback to snapshot {snapshot_id}",
            snapshot_data={"rollback_to_snapshot": str(snapshot_id)},
            created_by="human",
        )

        await self.event_repo.record_event(
            self.novel_id,
            "rollback",
            f"Rollback to snapshot {snapshot_id}",
            "version",
            source="human",
            source_user_id=user_id,
            severity="warning",
            event_data={
                "snapshot_id": str(snapshot_id),
                "version_id": str(version.id),
                "reason": reason,
            },
        )

        return {
            "version_id": str(version.id),
            "version_number": version.version_number,
            "snapshot_id": str(snapshot_id),
            "status": "rollback_created",
            "note": "Alpha: rollback marker created. Full state restoration in Sprint 2.",
        }
