"""Plot node repository."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from .base import BaseRepository
from ..models.plot import PlotNode


class PlotNodeRepository(BaseRepository[PlotNode]):
    """Persistence for the plot tree (arc / volume / chapter / scene / beat)."""

    def __init__(self, db):
        super().__init__(PlotNode, db)

    async def list_nodes(
        self,
        novel_id: uuid.UUID,
        *,
        node_type: str | None = None,
        chapter_number: int | None = None,
        status: str | None = None,
        active_only: bool = True,
        limit: int = 200,
    ) -> list[PlotNode]:
        query = select(PlotNode).where(PlotNode.novel_id == novel_id)
        if node_type:
            query = query.where(PlotNode.node_type == node_type)
        if chapter_number is not None:
            query = query.where(PlotNode.chapter_number == chapter_number)
        if status:
            query = query.where(PlotNode.status == status)
        if active_only:
            query = query.where(PlotNode.is_active.is_(True))
        query = query.order_by(
            PlotNode.chapter_number.asc().nullsfirst(),
            PlotNode.node_order.asc(),
        ).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_chapter_node(
        self, novel_id: uuid.UUID, chapter_number: int
    ) -> PlotNode | None:
        result = await self.db.execute(
            select(PlotNode)
            .where(PlotNode.novel_id == novel_id)
            .where(PlotNode.node_type == "chapter")
            .where(PlotNode.chapter_number == chapter_number)
            .where(PlotNode.is_active.is_(True))
            .order_by(PlotNode.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def upsert_chapter_node(
        self,
        novel_id: uuid.UUID,
        chapter_number: int,
        node_name: str,
        *,
        description: str | None = None,
        status: str = "planned",
        word_count_target: int | None = None,
        word_count_actual: int | None = None,
        importance: float = 0.5,
        confidence: float = 0.8,
        node_data: dict[str, Any] | None = None,
        goal_id: uuid.UUID | None = None,
        parent_node_id: uuid.UUID | None = None,
    ) -> tuple[PlotNode, str]:
        """Create or update the chapter node. Returns (node, 'created'|'updated')."""
        existing = await self.get_chapter_node(novel_id, chapter_number)
        if existing:
            existing.node_name = node_name
            if description is not None:
                existing.description = description
            existing.status = status
            if word_count_target is not None:
                existing.word_count_target = word_count_target
            if word_count_actual is not None:
                existing.word_count_actual = word_count_actual
            existing.importance = importance
            existing.confidence = confidence
            if node_data is not None:
                merged = dict(existing.node_data or {})
                merged.update(node_data)
                existing.node_data = merged
            if goal_id is not None:
                existing.goal_id = goal_id
            existing.version = (existing.version or 1) + 1
            await self.db.flush()
            return existing, "updated"

        node = PlotNode(
            novel_id=novel_id,
            node_type="chapter",
            node_name=node_name,
            description=description,
            parent_node_id=parent_node_id,
            node_order=chapter_number,
            depth=1,
            status=status,
            chapter_number=chapter_number,
            word_count_target=word_count_target,
            word_count_actual=word_count_actual,
            importance=importance,
            confidence=confidence,
            node_data=node_data or {},
            goal_id=goal_id,
            foreshadowing_ids=[],
            character_ids=[],
        )
        self.db.add(node)
        await self.db.flush()
        return node, "created"

    async def create_beat_nodes(
        self,
        novel_id: uuid.UUID,
        parent_node_id: uuid.UUID,
        chapter_number: int,
        beats: list[dict[str, Any]],
    ) -> list[PlotNode]:
        """Replace the beat nodes under a chapter node."""
        existing = await self.db.execute(
            select(PlotNode)
            .where(PlotNode.novel_id == novel_id)
            .where(PlotNode.parent_node_id == parent_node_id)
            .where(PlotNode.node_type == "beat")
        )
        for old in existing.scalars().all():
            old.is_active = False

        created: list[PlotNode] = []
        for idx, beat in enumerate(beats):
            node = PlotNode(
                novel_id=novel_id,
                node_type="beat",
                node_name=str(beat.get("name") or f"beat_{idx + 1}")[:200],
                description=str(beat.get("content") or "")[:4000] or None,
                parent_node_id=parent_node_id,
                node_order=idx,
                depth=2,
                status="planned",
                chapter_number=chapter_number,
                word_count_target=int(beat.get("target_words") or 0) or None,
                importance=float(beat.get("importance") or 0.5),
                confidence=float(beat.get("confidence") or 0.8),
                node_data={
                    "emotion": beat.get("emotion"),
                    "pov": beat.get("pov"),
                },
                foreshadowing_ids=[],
                character_ids=[],
            )
            self.db.add(node)
            created.append(node)
        await self.db.flush()
        return created

    @staticmethod
    def to_dict(node: PlotNode) -> dict[str, Any]:
        return {
            "id": str(node.id),
            "type": node.node_type,
            "name": node.node_name,
            "description": node.description,
            "parent_node_id": str(node.parent_node_id) if node.parent_node_id else None,
            "order": node.node_order,
            "depth": node.depth,
            "status": node.status,
            "chapter_number": node.chapter_number,
            "word_count_target": node.word_count_target,
            "word_count_actual": node.word_count_actual,
            "importance": node.importance,
            "confidence": node.confidence,
            "data": node.node_data,
            "goal_id": str(node.goal_id) if node.goal_id else None,
            "version": node.version,
        }
