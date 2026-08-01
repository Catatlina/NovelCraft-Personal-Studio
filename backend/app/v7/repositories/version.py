"""Version control repositories."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from ..models.version import StoryVersion, BrainSnapshot


class VersionRepository(BaseRepository[StoryVersion]):
    """Story version repository."""

    def __init__(self, db: AsyncSession):
        super().__init__(StoryVersion, db)

    async def list_by_novel(
        self,
        novel_id: uuid.UUID,
        *,
        branch_name: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[StoryVersion]:
        """List versions for a novel."""
        query = select(StoryVersion).where(StoryVersion.novel_id == novel_id)

        if branch_name:
            query = query.where(StoryVersion.branch_name == branch_name)

        query = query.order_by(StoryVersion.version_number.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_latest(
        self,
        novel_id: uuid.UUID,
        *,
        branch_name: str = "main",
    ) -> StoryVersion | None:
        """Get latest version for a novel."""
        result = await self.db.execute(
            select(StoryVersion).where(
                StoryVersion.novel_id == novel_id,
                StoryVersion.branch_name == branch_name,
            )
            .order_by(StoryVersion.version_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_next_version_number(
        self,
        novel_id: uuid.UUID,
        *,
        branch_name: str = "main",
    ) -> int:
        """Get next version number."""
        result = await self.db.execute(
            select(func.max(StoryVersion.version_number)).where(
                StoryVersion.novel_id == novel_id,
                StoryVersion.branch_name == branch_name,
            )
        )
        max_version = result.scalar_one_or_none()
        return (max_version or 0) + 1

    async def create_version(
        self,
        novel_id: uuid.UUID,
        *,
        version_type: str = "auto",
        description: str | None = None,
        snapshot_data: dict[str, Any] | None = None,
        parent_version_id: uuid.UUID | None = None,
        branch_name: str = "main",
        tag_name: str | None = None,
        created_by: str = "system",
    ) -> StoryVersion:
        """Create a new version."""
        version_number = await self.get_next_version_number(novel_id, branch_name=branch_name)
        
        return await self.create({
            "novel_id": novel_id,
            "version_number": version_number,
            "version_type": version_type,
            "description": description,
            "snapshot_data": snapshot_data or {},
            "parent_version_id": parent_version_id,
            "branch_name": branch_name,
            "tag_name": tag_name,
            "created_by": created_by,
        })


class SnapshotRepository(BaseRepository[BrainSnapshot]):
    """Brain snapshot repository."""

    def __init__(self, db: AsyncSession):
        super().__init__(BrainSnapshot, db)

    async def list_by_novel(
        self,
        novel_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> list[BrainSnapshot]:
        """List snapshots for a novel."""
        result = await self.db.execute(
            select(BrainSnapshot).where(BrainSnapshot.novel_id == novel_id)
            .order_by(BrainSnapshot.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create_snapshot(
        self,
        novel_id: uuid.UUID,
        state_data: dict[str, Any],
        *,
        snapshot_type: str = "full",
        description: str | None = None,
        version_id: uuid.UUID | None = None,
    ) -> BrainSnapshot:
        """Create a new snapshot."""
        import json
        size_bytes = len(json.dumps(state_data).encode("utf-8"))
        
        return await self.create({
            "novel_id": novel_id,
            "version_id": version_id,
            "snapshot_type": snapshot_type,
            "state_data": state_data,
            "description": description,
            "size_bytes": size_bytes,
        })
