"""V7 series (跨系列世界共享) models.

Series 允许多个 Novel 项目共享同一世界观知识库，
人物、地点、时间线在一个库里，各自独立使用。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, Base


class Series(BaseModel):
    """系列定义表。

    一个系列可以包含多个小说项目，共享世界观知识库。
    """

    __tablename__ = "v7_series"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # 系列设置
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # 创建者
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    # 关系
    members: Mapped[list["SeriesMember"]] = relationship(
        back_populates="series",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    knowledge: Mapped[list["SeriesKnowledge"]] = relationship(
        back_populates="series",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_series_owner_id", "owner_id"),
        Index("idx_series_is_active", "is_active"),
    )


class SeriesMember(BaseModel):
    """系列成员表。

    记录哪些小说属于哪个系列，以及它们在系列中的角色。
    """

    __tablename__ = "v7_series_members"

    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("v7_series.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    novel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # 在系列中的角色：main/spinoff/prequel/sequel/side
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="main")

    # 顺序（用于排序）
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 是否可以写入共享知识库
    can_write: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # 加入时间
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # 关系
    series: Mapped["Series"] = relationship(back_populates="members")

    __table_args__ = (
        UniqueConstraint("series_id", "novel_id", name="uq_series_member"),
        Index("idx_series_member_novel_id", "novel_id"),
    )


class SeriesKnowledge(BaseModel):
    """系列共享知识库表。

    系列内所有小说共享的世界观知识。
    优先级：novel > series > global（小说级 > 系列级 > 全局级）
    """

    __tablename__ = "v7_series_knowledge"

    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("v7_series.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 知识类型：character/location/item/timeline/world_setting/event/reference
    knowledge_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 标签，用于检索
    tags: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )

    # 重要性/优先级
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    # 来源小说（可选，标记是哪部小说贡献的）
    source_novel_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # 额外元数据
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    # 关系
    series: Mapped["Series"] = relationship(back_populates="knowledge")

    __table_args__ = (
        Index("idx_series_knowledge_series_id", "series_id"),
        Index("idx_series_knowledge_type", "knowledge_type"),
        Index("idx_series_knowledge_source", "source_novel_id"),
        Index("idx_series_knowledge_importance", "importance"),
    )
