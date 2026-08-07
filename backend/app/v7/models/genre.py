"""
品类库系统模型

4张表：
- genre_packs：品类包
- genre_rules：品类规则
- genre_knowledge：品类知识
- genre_prompts：品类 Prompt 模板
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import Integer, String, Text, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class GenrePack(BaseModel):
    """
    品类包
    
    每个品类是一个独立的包，可以有父品类，支持继承。
    """
    __tablename__ = "v7_genre_packs"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    
    # 父品类 ID，支持多层继承
    parent_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("v7_genre_packs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 品类范围：webnovel / fanqie / qidian / jjwxc / custom
    scope: Mapped[str] = mapped_column(String(50), nullable=False, default="custom")
    
    # 是否内置品类（内置的不可删除）
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    # 是否启用
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    
    # 品类图标/封面
    icon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # 额外元数据
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    
    # 关系
    parent: Mapped["GenrePack | None"] = relationship(
        "GenrePack",
        remote_side="GenrePack.id",
        back_populates="children",
    )
    children: Mapped[list["GenrePack"]] = relationship(
        "GenrePack",
        back_populates="parent",
    )
    
    rules: Mapped[list["GenreRule"]] = relationship(
        "GenreRule",
        back_populates="genre_pack",
        cascade="all, delete-orphan",
    )
    
    knowledge: Mapped[list["GenreKnowledge"]] = relationship(
        "GenreKnowledge",
        back_populates="genre_pack",
        cascade="all, delete-orphan",
    )
    
    prompts: Mapped[list["GenrePrompt"]] = relationship(
        "GenrePrompt",
        back_populates="genre_pack",
        cascade="all, delete-orphan",
    )
    
    __table_args__ = (
        Index("idx_genre_packs_parent_id", "parent_id"),
        Index("idx_genre_packs_scope", "scope"),
        Index("idx_genre_packs_is_builtin", "is_builtin"),
    )


class GenreRule(BaseModel):
    """
    品类规则
    
    每个品类可以有很多条规则，支持继承和覆盖。
    """
    __tablename__ = "v7_genre_rules"

    genre_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("v7_genre_packs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # 规则类型：style / forbidden / required / quality_threshold / ai_smell_threshold / payoff / etc.
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # 规则键名，唯一标识一条规则（在同一品类内）
    rule_key: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # 规则值（JSON 格式，支持各种类型）
    rule_value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    
    # 严重程度：info / warning / error / blocking
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning")
    
    # 优先级（数字越大优先级越高，高优先级覆盖低优先级）
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    
    # 规则描述
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 是否启用
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    
    # 继承自哪个品类（用于继承解析时追踪来源）
    inherited_from: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    
    # 关系
    genre_pack: Mapped["GenrePack"] = relationship(
        "GenrePack",
        back_populates="rules",
    )
    
    __table_args__ = (
        Index("idx_genre_rules_genre_id", "genre_id"),
        Index("idx_genre_rules_rule_type", "rule_type"),
        Index("idx_genre_rules_genre_key", "genre_id", "rule_key", unique=True),
    )


class GenreKnowledge(BaseModel):
    """
    品类知识
    
    品类相关的知识库条目，比如：
    - 唐代官职表
    - 封神神仙体系
    - 常见场景描写素材
    """
    __tablename__ = "v7_genre_knowledge"

    genre_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("v7_genre_packs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # 知识类型：world_setting / character / scene / item / timeline / reference / etc.
    knowledge_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # 知识条目标题
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    
    # 知识内容
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 标签（用于检索）
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    
    # 优先级/重要性
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    
    # 是否启用
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    
    # 继承自哪个品类
    inherited_from: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    
    # 额外元数据
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    
    # 关系
    genre_pack: Mapped["GenrePack"] = relationship(
        "GenrePack",
        back_populates="knowledge",
    )
    
    __table_args__ = (
        Index("idx_genre_knowledge_genre_id", "genre_id"),
        Index("idx_genre_knowledge_type", "knowledge_type"),
    )


class GenrePrompt(BaseModel):
    """
    品类 Prompt 模板
    
    品类专属的 Prompt 模板，支持继承和覆盖。
    """
    __tablename__ = "v7_genre_prompts"

    genre_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("v7_genre_packs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Prompt 类型：writer / reviewer / planner / editor / etc.
    prompt_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # Prompt 名称（唯一标识）
    prompt_name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # 版本号
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    
    # Prompt 内容
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 描述
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 是否启用
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    
    # 继承自哪个品类
    inherited_from: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    
    # 额外元数据
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    
    # 关系
    genre_pack: Mapped["GenrePack"] = relationship(
        "GenrePack",
        back_populates="prompts",
    )
    
    __table_args__ = (
        Index("idx_genre_prompts_genre_id", "genre_id"),
        Index("idx_genre_prompts_type", "prompt_type"),
        Index("idx_genre_prompts_genre_name", "genre_id", "prompt_name", unique=True),
    )
