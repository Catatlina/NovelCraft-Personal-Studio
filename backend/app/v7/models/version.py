"""Version control models."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, NovelScopedMixin


class StoryVersion(BaseModel, NovelScopedMixin):
    """Story version record."""
    __tablename__ = "v7_story_versions"

    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    version_type: Mapped[str] = mapped_column(String(50), nullable=False)  # auto/manual/branch/tag
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("v7_story_versions.id"),
        nullable=True,
    )
    branch_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tag_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_by: Mapped[str] = mapped_column(String(50), nullable=False, default="system")  # system/human/ai

    # D1 修复（2026-08-02）：此前用 `version_id_col = version_number` 把
    # version_number 交给 SQLAlchemy 乐观锁计数器，导致每次 INSERT 都被
    # 计数器覆盖成 1，版本号永远不递增。删除该配置后，repository 中
    # get_next_version_number() 计算的值会真实入库。


class BrainSnapshot(BaseModel, NovelScopedMixin):
    """Brain state snapshot."""
    __tablename__ = "v7_brain_snapshots"

    version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("v7_story_versions.id"),
        nullable=True,
    )
    snapshot_type: Mapped[str] = mapped_column(String(50), nullable=False)  # full/partial
    state_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
