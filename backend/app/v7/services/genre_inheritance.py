"""
品类继承解析引擎

功能：
1. 解析品类的完整规则集（包含所有父品类的继承）
2. 子品类覆盖父品类的规则（相同 rule_key 的，子品类优先级更高）
3. 支持多层继承（base → tomato → datang）
4. 解析结果缓存
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.genre import GenrePack, GenreRule, GenreKnowledge, GenrePrompt


# 简单的内存缓存
_inheritance_cache: dict[uuid.UUID, dict[str, Any]] = {}
_cache_enabled = True


def clear_inheritance_cache() -> None:
    """清空继承解析缓存。"""
    _inheritance_cache.clear()


def disable_cache() -> None:
    """禁用缓存（用于测试）。"""
    global _cache_enabled
    _cache_enabled = False


def enable_cache() -> None:
    """启用缓存。"""
    global _cache_enabled
    _cache_enabled = True


async def get_genre_chain(db: AsyncSession, genre_id: uuid.UUID) -> list[GenrePack]:
    """
    获取品类继承链（从子到父）。
    
    例如：datang → tomato → base
    
    Args:
        db: 数据库会话
        genre_id: 品类 ID
        
    Returns:
        品类列表，从子到父排序
    """
    chain: list[GenrePack] = []
    current_id: uuid.UUID | None = genre_id
    visited: set[uuid.UUID] = set()  # 防止循环继承
    
    while current_id and current_id not in visited:
        visited.add(current_id)
        
        result = await db.execute(
            select(GenrePack).where(GenrePack.id == current_id)
        )
        genre = result.scalar_one_or_none()
        
        if not genre:
            break
            
        chain.append(genre)
        current_id = genre.parent_id
    
    return chain


async def resolve_genre_rules(
    db: AsyncSession,
    genre_id: uuid.UUID,
    rule_type: str | None = None,
) -> dict[str, dict[str, Any]]:
    """
    解析品类的完整规则集（包含继承）。
    
    子品类的规则会覆盖父品类的相同 rule_key 的规则。
    
    Args:
        db: 数据库会话
        genre_id: 品类 ID
        rule_type: 可选，只返回指定类型的规则
        
    Returns:
        规则字典，key 为 rule_key，value 为规则字典（DTO）
    """
    # 检查缓存
    cache_key = f"rules_{genre_id}_{rule_type or 'all'}"
    if _cache_enabled and cache_key in _inheritance_cache:
        return _inheritance_cache[cache_key]
    
    # 获取继承链
    chain = await get_genre_chain(db, genre_id)
    
    if not chain:
        return {}
    
    # 从父到子遍历，这样子品类的规则会覆盖父品类的
    resolved: dict[str, dict[str, Any]] = {}
    
    # 反转链，从父到子
    for genre in reversed(chain):
        query = select(GenreRule).where(
            GenreRule.genre_id == genre.id,
            GenreRule.is_active == True,  # noqa: E712
        )
        
        if rule_type:
            query = query.where(GenreRule.rule_type == rule_type)
        
        result = await db.execute(query)
        rules = list(result.scalars().all())
        
        for rule in rules:
            # 转换为字典（DTO），避免 detached 问题
            rule_dict = {
                "id": str(rule.id),
                "genre_id": str(rule.genre_id),
                "rule_type": rule.rule_type,
                "rule_key": rule.rule_key,
                "rule_value": rule.rule_value,
                "severity": rule.severity,
                "priority": rule.priority,
                "description": rule.description,
                "is_active": rule.is_active,
                "inherited_from": str(genre.id) if genre.id != genre_id else None,
                "created_at": rule.created_at.isoformat() if rule.created_at else None,
                "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
            }
            # 子品类覆盖父品类
            resolved[rule.rule_key] = rule_dict
    
    # 存入缓存
    if _cache_enabled:
        _inheritance_cache[cache_key] = resolved
    
    return resolved


async def resolve_genre_knowledge(
    db: AsyncSession,
    genre_id: uuid.UUID,
    knowledge_type: str | None = None,
) -> list[dict[str, Any]]:
    """
    解析品类的完整知识库（包含继承）。
    
    所有父品类的知识都会被继承，子品类可以新增知识。
    （知识没有"覆盖"的概念，只有新增）
    
    Args:
        db: 数据库会话
        genre_id: 品类 ID
        knowledge_type: 可选，只返回指定类型的知识
        
    Returns:
        知识条目字典列表（DTO）
    """
    # 检查缓存
    cache_key = f"knowledge_{genre_id}_{knowledge_type or 'all'}"
    if _cache_enabled and cache_key in _inheritance_cache:
        return _inheritance_cache[cache_key]
    
    # 获取继承链
    chain = await get_genre_chain(db, genre_id)
    
    if not chain:
        return []
    
    all_knowledge: list[dict[str, Any]] = []
    seen_titles: set[str] = set()  # 去重（相同标题的，子品类优先）
    
    # 从子到父遍历，这样子品类的知识排在前面
    for genre in chain:
        query = select(GenreKnowledge).where(
            GenreKnowledge.genre_id == genre.id,
            GenreKnowledge.is_active == True,  # noqa: E712
        )
        
        if knowledge_type:
            query = query.where(GenreKnowledge.knowledge_type == knowledge_type)
        
        query = query.order_by(GenreKnowledge.priority.desc())
        
        result = await db.execute(query)
        knowledge_list = list(result.scalars().all())
        
        for knowledge in knowledge_list:
            if knowledge.title not in seen_titles:
                # 转换为字典（DTO），避免 detached 问题
                knowledge_dict = {
                    "id": str(knowledge.id),
                    "genre_id": str(knowledge.genre_id),
                    "knowledge_type": knowledge.knowledge_type,
                    "title": knowledge.title,
                    "content": knowledge.content,
                    "tags": knowledge.tags,
                    "priority": knowledge.priority,
                    "is_active": knowledge.is_active,
                    "inherited_from": str(genre.id) if genre.id != genre_id else None,
                    "extra_metadata": knowledge.extra_metadata,
                    "created_at": knowledge.created_at.isoformat() if knowledge.created_at else None,
                    "updated_at": knowledge.updated_at.isoformat() if knowledge.updated_at else None,
                }
                seen_titles.add(knowledge.title)
                all_knowledge.append(knowledge_dict)
    
    # 存入缓存
    if _cache_enabled:
        _inheritance_cache[cache_key] = all_knowledge
    
    return all_knowledge


async def resolve_genre_prompts(
    db: AsyncSession,
    genre_id: uuid.UUID,
    prompt_type: str | None = None,
) -> dict[str, dict[str, Any]]:
    """
    解析品类的完整 Prompt 模板集（包含继承）。
    
    子品类的 Prompt 会覆盖父品类的相同 prompt_name 的 Prompt。
    
    Args:
        db: 数据库会话
        genre_id: 品类 ID
        prompt_type: 可选，只返回指定类型的 Prompt
        
    Returns:
        Prompt 字典，key 为 prompt_name，value 为 Prompt 字典（DTO）
    """
    # 检查缓存
    cache_key = f"prompts_{genre_id}_{prompt_type or 'all'}"
    if _cache_enabled and cache_key in _inheritance_cache:
        return _inheritance_cache[cache_key]
    
    # 获取继承链
    chain = await get_genre_chain(db, genre_id)
    
    if not chain:
        return {}
    
    # 从父到子遍历，这样子品类的 Prompt 会覆盖父品类的
    resolved: dict[str, dict[str, Any]] = {}
    
    # 反转链，从父到子
    for genre in reversed(chain):
        query = select(GenrePrompt).where(
            GenrePrompt.genre_id == genre.id,
            GenrePrompt.is_active == True,  # noqa: E712
        )
        
        if prompt_type:
            query = query.where(GenrePrompt.prompt_type == prompt_type)
        
        result = await db.execute(query)
        prompts = list(result.scalars().all())
        
        for prompt in prompts:
            # 转换为字典（DTO），避免 detached 问题
            prompt_dict = {
                "id": str(prompt.id),
                "genre_id": str(prompt.genre_id),
                "prompt_type": prompt.prompt_type,
                "prompt_name": prompt.prompt_name,
                "version": prompt.version,
                "content": prompt.content,
                "description": prompt.description,
                "is_active": prompt.is_active,
                "inherited_from": str(genre.id) if genre.id != genre_id else None,
                "extra_metadata": prompt.extra_metadata,
                "created_at": prompt.created_at.isoformat() if prompt.created_at else None,
                "updated_at": prompt.updated_at.isoformat() if prompt.updated_at else None,
            }
            # 子品类覆盖父品类
            resolved[prompt.prompt_name] = prompt_dict
    
    # 存入缓存
    if _cache_enabled:
        _inheritance_cache[cache_key] = resolved
    
    return resolved


async def get_genre_tree(db: AsyncSession) -> list[dict[str, Any]]:
    """
    获取完整的品类树结构。
    
    Returns:
        品类树列表，每个节点包含 children 字段
    """
    # 获取所有品类
    result = await db.execute(
        select(GenrePack).where(GenrePack.is_active == True)  # noqa: E712
    )
    all_genres = list(result.scalars().all())
    
    # 构建字典
    genre_map: dict[uuid.UUID, dict[str, Any]] = {}
    for genre in all_genres:
        genre_map[genre.id] = {
            "id": str(genre.id),
            "name": genre.name,
            "slug": genre.slug,
            "description": genre.description,
            "scope": genre.scope,
            "is_builtin": genre.is_builtin,
            "icon_url": genre.icon_url,
            "parent_id": str(genre.parent_id) if genre.parent_id else None,
            "children": [],
        }
    
    # 构建树
    roots: list[dict[str, Any]] = []
    for genre_id, genre_data in genre_map.items():
        parent_id = genre_data["parent_id"]
        if parent_id:
            try:
                parent_uuid = uuid.UUID(parent_id)
                if parent_uuid in genre_map:
                    genre_map[parent_uuid]["children"].append(genre_data)
                    continue
            except ValueError:
                pass
        roots.append(genre_data)
    
    return roots


async def get_genre_by_slug(db: AsyncSession, slug: str) -> GenrePack | None:
    """
    根据 slug 获取品类。
    
    Args:
        db: 数据库会话
        slug: 品类 slug
        
    Returns:
        品类对象，或 None
    """
    result = await db.execute(
        select(GenrePack).where(GenrePack.slug == slug)
    )
    return result.scalar_one_or_none()
