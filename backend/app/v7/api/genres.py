"""
品类库 API

提供品类包、规则、知识、Prompt 的 CRUD 操作，以及继承解析和品类树查询。
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_async_db as get_db
from ..models.genre import GenrePack, GenreRule, GenreKnowledge, GenrePrompt
from ..services.genre_inheritance import (
    resolve_genre_rules,
    resolve_genre_knowledge,
    resolve_genre_prompts,
    get_genre_tree,
    get_genre_chain,
    clear_inheritance_cache,
)
from ...api.v1.config import require_admin, require_admin_reads

router = APIRouter(
    prefix="",
    tags=["v7-genres"],
    dependencies=[Depends(require_admin_reads)],
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _parse_uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {field}")


def _parse_optional_uuid(value: str | None, field: str) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    return _parse_uuid(value, field)


def _genre_to_dict(genre: GenrePack) -> dict[str, Any]:
    """把品类对象转成字典。"""
    return {
        "id": str(genre.id),
        "name": genre.name,
        "slug": genre.slug,
        "parent_id": str(genre.parent_id) if genre.parent_id else None,
        "description": genre.description,
        "scope": genre.scope,
        "is_builtin": genre.is_builtin,
        "is_active": genre.is_active,
        "icon_url": genre.icon_url,
        "extra_metadata": genre.extra_metadata,
        "created_at": genre.created_at.isoformat() if genre.created_at else None,
        "updated_at": genre.updated_at.isoformat() if genre.updated_at else None,
    }


def _rule_to_dict(rule: GenreRule) -> dict[str, Any]:
    """把规则对象转成字典。"""
    return {
        "id": str(rule.id),
        "genre_id": str(rule.genre_id),
        "rule_type": rule.rule_type,
        "rule_key": rule.rule_key,
        "rule_value": rule.rule_value,
        "severity": rule.severity,
        "priority": rule.priority,
        "description": rule.description,
        "is_active": rule.is_active,
        "inherited_from": str(rule.inherited_from) if rule.inherited_from else None,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


def _knowledge_to_dict(knowledge: GenreKnowledge) -> dict[str, Any]:
    """把知识对象转成字典。"""
    return {
        "id": str(knowledge.id),
        "genre_id": str(knowledge.genre_id),
        "knowledge_type": knowledge.knowledge_type,
        "title": knowledge.title,
        "content": knowledge.content,
        "tags": knowledge.tags,
        "priority": knowledge.priority,
        "is_active": knowledge.is_active,
        "inherited_from": str(knowledge.inherited_from) if knowledge.inherited_from else None,
        "extra_metadata": knowledge.extra_metadata,
        "created_at": knowledge.created_at.isoformat() if knowledge.created_at else None,
        "updated_at": knowledge.updated_at.isoformat() if knowledge.updated_at else None,
    }


def _prompt_to_dict(prompt: GenrePrompt) -> dict[str, Any]:
    """把 Prompt 对象转成字典。"""
    return {
        "id": str(prompt.id),
        "genre_id": str(prompt.genre_id),
        "prompt_type": prompt.prompt_type,
        "prompt_name": prompt.prompt_name,
        "version": prompt.version,
        "content": prompt.content,
        "description": prompt.description,
        "is_active": prompt.is_active,
        "inherited_from": str(prompt.inherited_from) if prompt.inherited_from else None,
        "extra_metadata": prompt.extra_metadata,
        "created_at": prompt.created_at.isoformat() if prompt.created_at else None,
        "updated_at": prompt.updated_at.isoformat() if prompt.updated_at else None,
    }


# ── 品类树 ────────────────────────────────────────────────────────────────


@router.get("/tree", response_model=dict)
async def get_genre_tree_api(
    db: AsyncSession = Depends(get_db),
):
    """获取完整的品类树结构。"""
    tree = await get_genre_tree(db)
    return {"tree": tree}


# ── 品类包 CRUD ───────────────────────────────────────────────────────────


@router.get("/packs", response_model=dict)
async def list_genre_packs(
    scope: str | None = Query(None, description="按范围过滤"),
    is_active: bool | None = Query(None, description="是否只返回启用的"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """列出品类包。"""
    query = select(GenrePack)
    
    if scope:
        query = query.where(GenrePack.scope == scope)
    
    if is_active is not None:
        query = query.where(GenrePack.is_active == is_active)
    
    query = query.order_by(GenrePack.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    packs = list(result.scalars().all())
    
    # 统计总数
    count_query = select(GenrePack)
    if scope:
        count_query = count_query.where(GenrePack.scope == scope)
    if is_active is not None:
        count_query = count_query.where(GenrePack.is_active == is_active)
    
    from sqlalchemy import func
    count_result = await db.execute(
        select(func.count()).select_from(GenrePack)
    )
    total = count_result.scalar_one()
    
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "packs": [_genre_to_dict(p) for p in packs],
    }


@router.get("/packs/{pack_id}", response_model=dict)
async def get_genre_pack(
    pack_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取品类包详情。"""
    genre_id = _parse_uuid(pack_id, "pack_id")
    
    result = await db.execute(
        select(GenrePack).where(GenrePack.id == genre_id)
    )
    pack = result.scalar_one_or_none()
    
    if not pack:
        raise HTTPException(status_code=404, detail="Genre pack not found")
    
    return {"pack": _genre_to_dict(pack)}


@router.post("/packs", response_model=dict)
async def create_genre_pack(
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """创建品类包。"""
    # 检查 slug 是否重复
    slug = data.get("slug")
    if not slug:
        raise HTTPException(status_code=400, detail="slug is required")
    
    existing = await db.execute(
        select(GenrePack).where(GenrePack.slug == slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"slug '{slug}' already exists")
    
    pack = GenrePack(
        name=data.get("name", ""),
        slug=slug,
        parent_id=_parse_optional_uuid(data.get("parent_id"), "parent_id"),
        description=data.get("description"),
        scope=data.get("scope", "custom"),
        is_builtin=data.get("is_builtin", False),
        is_active=data.get("is_active", True),
        icon_url=data.get("icon_url"),
        extra_metadata=data.get("extra_metadata", {}),
    )
    
    db.add(pack)
    await db.flush()
    await db.refresh(pack)
    await db.commit()
    
    # 清空缓存
    clear_inheritance_cache()
    
    return {"pack": _genre_to_dict(pack)}


@router.put("/packs/{pack_id}", response_model=dict)
async def update_genre_pack(
    pack_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """更新品类包。"""
    genre_id = _parse_uuid(pack_id, "pack_id")
    
    result = await db.execute(
        select(GenrePack).where(GenrePack.id == genre_id)
    )
    pack = result.scalar_one_or_none()
    
    if not pack:
        raise HTTPException(status_code=404, detail="Genre pack not found")
    
    # 内置品类不允许修改
    if pack.is_builtin and not data.get("allow_builtin_modify", False):
        raise HTTPException(status_code=400, detail="Builtin genre packs cannot be modified")
    
    # 更新字段
    if "name" in data:
        pack.name = data["name"]
    if "slug" in data and data["slug"] != pack.slug:
        # 检查新 slug 是否重复
        existing = await db.execute(
            select(GenrePack).where(GenrePack.slug == data["slug"])
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"slug '{data['slug']}' already exists")
        pack.slug = data["slug"]
    if "parent_id" in data:
        pack.parent_id = _parse_optional_uuid(data["parent_id"], "parent_id")
    if "description" in data:
        pack.description = data["description"]
    if "scope" in data:
        pack.scope = data["scope"]
    if "is_active" in data:
        pack.is_active = data["is_active"]
    if "icon_url" in data:
        pack.icon_url = data["icon_url"]
    if "extra_metadata" in data:
        pack.extra_metadata = data["extra_metadata"]
    
    await db.flush()
    await db.refresh(pack)
    await db.commit()
    
    # 清空缓存
    clear_inheritance_cache()
    
    return {"pack": _genre_to_dict(pack)}


@router.delete("/packs/{pack_id}", response_model=dict)
async def delete_genre_pack(
    pack_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """删除品类包。"""
    genre_id = _parse_uuid(pack_id, "pack_id")
    
    result = await db.execute(
        select(GenrePack).where(GenrePack.id == genre_id)
    )
    pack = result.scalar_one_or_none()
    
    if not pack:
        raise HTTPException(status_code=404, detail="Genre pack not found")
    
    # 内置品类不允许删除
    if pack.is_builtin:
        raise HTTPException(status_code=400, detail="Builtin genre packs cannot be deleted")
    
    await db.delete(pack)
    await db.commit()
    
    # 清空缓存
    clear_inheritance_cache()
    
    return {"success": True, "message": "Genre pack deleted"}


# ── 规则 CRUD ─────────────────────────────────────────────────────────────


@router.get("/packs/{pack_id}/rules", response_model=dict)
async def list_genre_rules(
    pack_id: str,
    rule_type: str | None = Query(None, description="按规则类型过滤"),
    include_inherited: bool = Query(False, description="是否包含继承的规则"),
    db: AsyncSession = Depends(get_db),
):
    """列出品类规则。"""
    genre_id = _parse_uuid(pack_id, "pack_id")
    
    if include_inherited:
        # 使用继承解析引擎（返回字典列表）
        resolved = await resolve_genre_rules(db, genre_id, rule_type=rule_type)
        rules = list(resolved.values())
    else:
        # 只返回当前品类自己的规则（ORM 对象，需要转换）
        query = select(GenreRule).where(GenreRule.genre_id == genre_id)
        
        if rule_type:
            query = query.where(GenreRule.rule_type == rule_type)
        
        query = query.order_by(GenreRule.rule_type, GenreRule.rule_key)
        
        result = await db.execute(query)
        rule_objects = list(result.scalars().all())
        rules = [_rule_to_dict(r) for r in rule_objects]
    
    return {
        "total": len(rules),
        "rules": rules,
    }


@router.post("/packs/{pack_id}/rules", response_model=dict)
async def create_genre_rule(
    pack_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """创建品类规则。"""
    genre_id = _parse_uuid(pack_id, "pack_id")
    
    # 检查 rule_key 是否重复
    rule_key = data.get("rule_key")
    if not rule_key:
        raise HTTPException(status_code=400, detail="rule_key is required")
    
    existing = await db.execute(
        select(GenreRule).where(
            GenreRule.genre_id == genre_id,
            GenreRule.rule_key == rule_key,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"rule_key '{rule_key}' already exists in this genre")
    
    rule = GenreRule(
        genre_id=genre_id,
        rule_type=data.get("rule_type", "style"),
        rule_key=rule_key,
        rule_value=data.get("rule_value", {}),
        severity=data.get("severity", "warning"),
        priority=data.get("priority", 50),
        description=data.get("description"),
        is_active=data.get("is_active", True),
    )
    
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    await db.commit()
    
    # 清空缓存
    clear_inheritance_cache()
    
    return {"rule": _rule_to_dict(rule)}


@router.put("/packs/{pack_id}/rules/{rule_id}", response_model=dict)
async def update_genre_rule(
    pack_id: str,
    rule_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """更新品类规则。"""
    genre_id = _parse_uuid(pack_id, "pack_id")
    rule_uuid = _parse_uuid(rule_id, "rule_id")
    
    result = await db.execute(
        select(GenreRule).where(
            GenreRule.id == rule_uuid,
            GenreRule.genre_id == genre_id,
        )
    )
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Genre rule not found")
    
    # 更新字段
    if "rule_type" in data:
        rule.rule_type = data["rule_type"]
    if "rule_value" in data:
        rule.rule_value = data["rule_value"]
    if "severity" in data:
        rule.severity = data["severity"]
    if "priority" in data:
        rule.priority = data["priority"]
    if "description" in data:
        rule.description = data["description"]
    if "is_active" in data:
        rule.is_active = data["is_active"]
    
    await db.flush()
    await db.refresh(rule)
    await db.commit()
    
    # 清空缓存
    clear_inheritance_cache()
    
    return {"rule": _rule_to_dict(rule)}


@router.delete("/packs/{pack_id}/rules/{rule_id}", response_model=dict)
async def delete_genre_rule(
    pack_id: str,
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """删除品类规则。"""
    genre_id = _parse_uuid(pack_id, "pack_id")
    rule_uuid = _parse_uuid(rule_id, "rule_id")
    
    result = await db.execute(
        select(GenreRule).where(
            GenreRule.id == rule_uuid,
            GenreRule.genre_id == genre_id,
        )
    )
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Genre rule not found")
    
    await db.delete(rule)
    await db.commit()
    
    # 清空缓存
    clear_inheritance_cache()
    
    return {"success": True, "message": "Genre rule deleted"}


# ── 知识 CRUD ─────────────────────────────────────────────────────────────


@router.get("/packs/{pack_id}/knowledge", response_model=dict)
async def list_genre_knowledge(
    pack_id: str,
    knowledge_type: str | None = Query(None, description="按知识类型过滤"),
    include_inherited: bool = Query(False, description="是否包含继承的知识"),
    db: AsyncSession = Depends(get_db),
):
    """列出品类知识。"""
    genre_id = _parse_uuid(pack_id, "pack_id")
    
    if include_inherited:
        # 使用继承解析引擎（返回字典列表）
        knowledge_list = await resolve_genre_knowledge(db, genre_id, knowledge_type=knowledge_type)
    else:
        # 只返回当前品类自己的知识（ORM 对象，需要转换）
        query = select(GenreKnowledge).where(GenreKnowledge.genre_id == genre_id)
        
        if knowledge_type:
            query = query.where(GenreKnowledge.knowledge_type == knowledge_type)
        
        query = query.order_by(GenreKnowledge.priority.desc(), GenreKnowledge.created_at.desc())
        
        result = await db.execute(query)
        knowledge_objects = list(result.scalars().all())
        knowledge_list = [_knowledge_to_dict(k) for k in knowledge_objects]
    
    return {
        "total": len(knowledge_list),
        "knowledge": knowledge_list,
    }


@router.post("/packs/{pack_id}/knowledge", response_model=dict)
async def create_genre_knowledge(
    pack_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """创建品类知识。"""
    genre_id = _parse_uuid(pack_id, "pack_id")
    
    knowledge = GenreKnowledge(
        genre_id=genre_id,
        knowledge_type=data.get("knowledge_type", "reference"),
        title=data.get("title", ""),
        content=data.get("content", ""),
        tags=data.get("tags", []),
        priority=data.get("priority", 50),
        is_active=data.get("is_active", True),
        extra_metadata=data.get("extra_metadata", {}),
    )
    
    db.add(knowledge)
    await db.flush()
    await db.refresh(knowledge)
    await db.commit()
    
    # 清空缓存
    clear_inheritance_cache()
    
    return {"knowledge": _knowledge_to_dict(knowledge)}


@router.put("/packs/{pack_id}/knowledge/{knowledge_id}", response_model=dict)
async def update_genre_knowledge(
    pack_id: str,
    knowledge_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """更新品类知识。"""
    genre_id = _parse_uuid(pack_id, "pack_id")
    knowledge_uuid = _parse_uuid(knowledge_id, "knowledge_id")
    
    result = await db.execute(
        select(GenreKnowledge).where(
            GenreKnowledge.id == knowledge_uuid,
            GenreKnowledge.genre_id == genre_id,
        )
    )
    knowledge = result.scalar_one_or_none()
    
    if not knowledge:
        raise HTTPException(status_code=404, detail="Genre knowledge not found")
    
    # 更新字段
    if "knowledge_type" in data:
        knowledge.knowledge_type = data["knowledge_type"]
    if "title" in data:
        knowledge.title = data["title"]
    if "content" in data:
        knowledge.content = data["content"]
    if "tags" in data:
        knowledge.tags = data["tags"]
    if "priority" in data:
        knowledge.priority = data["priority"]
    if "is_active" in data:
        knowledge.is_active = data["is_active"]
    if "extra_metadata" in data:
        knowledge.extra_metadata = data["extra_metadata"]
    
    await db.flush()
    await db.refresh(knowledge)
    await db.commit()
    
    # 清空缓存
    clear_inheritance_cache()
    
    return {"knowledge": _knowledge_to_dict(knowledge)}


@router.delete("/packs/{pack_id}/knowledge/{knowledge_id}", response_model=dict)
async def delete_genre_knowledge(
    pack_id: str,
    knowledge_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """删除品类知识。"""
    genre_id = _parse_uuid(pack_id, "pack_id")
    knowledge_uuid = _parse_uuid(knowledge_id, "knowledge_id")
    
    result = await db.execute(
        select(GenreKnowledge).where(
            GenreKnowledge.id == knowledge_uuid,
            GenreKnowledge.genre_id == genre_id,
        )
    )
    knowledge = result.scalar_one_or_none()
    
    if not knowledge:
        raise HTTPException(status_code=404, detail="Genre knowledge not found")
    
    await db.delete(knowledge)
    await db.commit()
    
    # 清空缓存
    clear_inheritance_cache()
    
    return {"success": True, "message": "Genre knowledge deleted"}


# ── Prompt CRUD ───────────────────────────────────────────────────────────


@router.get("/packs/{pack_id}/prompts", response_model=dict)
async def list_genre_prompts(
    pack_id: str,
    prompt_type: str | None = Query(None, description="按 Prompt 类型过滤"),
    include_inherited: bool = Query(False, description="是否包含继承的 Prompt"),
    db: AsyncSession = Depends(get_db),
):
    """列出品类 Prompt 模板。"""
    genre_id = _parse_uuid(pack_id, "pack_id")
    
    if include_inherited:
        # 使用继承解析引擎（返回字典列表）
        resolved = await resolve_genre_prompts(db, genre_id, prompt_type=prompt_type)
        prompts = list(resolved.values())
    else:
        # 只返回当前品类自己的 Prompt（ORM 对象，需要转换）
        query = select(GenrePrompt).where(GenrePrompt.genre_id == genre_id)
        
        if prompt_type:
            query = query.where(GenrePrompt.prompt_type == prompt_type)
        
        query = query.order_by(GenrePrompt.prompt_type, GenrePrompt.prompt_name)
        
        result = await db.execute(query)
        prompt_objects = list(result.scalars().all())
        prompts = [_prompt_to_dict(p) for p in prompt_objects]
    
    return {
        "total": len(prompts),
        "prompts": prompts,
    }


@router.post("/packs/{pack_id}/prompts", response_model=dict)
async def create_genre_prompt(
    pack_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """创建品类 Prompt 模板。"""
    genre_id = _parse_uuid(pack_id, "pack_id")
    
    # 检查 prompt_name 是否重复
    prompt_name = data.get("prompt_name")
    if not prompt_name:
        raise HTTPException(status_code=400, detail="prompt_name is required")
    
    existing = await db.execute(
        select(GenrePrompt).where(
            GenrePrompt.genre_id == genre_id,
            GenrePrompt.prompt_name == prompt_name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"prompt_name '{prompt_name}' already exists in this genre")
    
    prompt = GenrePrompt(
        genre_id=genre_id,
        prompt_type=data.get("prompt_type", "writer"),
        prompt_name=prompt_name,
        version=data.get("version", "1.0"),
        content=data.get("content", ""),
        description=data.get("description"),
        is_active=data.get("is_active", True),
        extra_metadata=data.get("extra_metadata", {}),
    )
    
    db.add(prompt)
    await db.flush()
    await db.refresh(prompt)
    await db.commit()
    
    # 清空缓存
    clear_inheritance_cache()
    
    return {"prompt": _prompt_to_dict(prompt)}


@router.put("/packs/{pack_id}/prompts/{prompt_id}", response_model=dict)
async def update_genre_prompt(
    pack_id: str,
    prompt_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """更新品类 Prompt 模板。"""
    genre_id = _parse_uuid(pack_id, "pack_id")
    prompt_uuid = _parse_uuid(prompt_id, "prompt_id")
    
    result = await db.execute(
        select(GenrePrompt).where(
            GenrePrompt.id == prompt_uuid,
            GenrePrompt.genre_id == genre_id,
        )
    )
    prompt = result.scalar_one_or_none()
    
    if not prompt:
        raise HTTPException(status_code=404, detail="Genre prompt not found")
    
    # 更新字段
    if "prompt_type" in data:
        prompt.prompt_type = data["prompt_type"]
    if "version" in data:
        prompt.version = data["version"]
    if "content" in data:
        prompt.content = data["content"]
    if "description" in data:
        prompt.description = data["description"]
    if "is_active" in data:
        prompt.is_active = data["is_active"]
    if "extra_metadata" in data:
        prompt.extra_metadata = data["extra_metadata"]
    
    await db.flush()
    await db.refresh(prompt)
    await db.commit()
    
    # 清空缓存
    clear_inheritance_cache()
    
    return {"prompt": _prompt_to_dict(prompt)}


@router.delete("/packs/{pack_id}/prompts/{prompt_id}", response_model=dict)
async def delete_genre_prompt(
    pack_id: str,
    prompt_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """删除品类 Prompt 模板。"""
    genre_id = _parse_uuid(pack_id, "pack_id")
    prompt_uuid = _parse_uuid(prompt_id, "prompt_id")
    
    result = await db.execute(
        select(GenrePrompt).where(
            GenrePrompt.id == prompt_uuid,
            GenrePrompt.genre_id == genre_id,
        )
    )
    prompt = result.scalar_one_or_none()
    
    if not prompt:
        raise HTTPException(status_code=404, detail="Genre prompt not found")
    
    await db.delete(prompt)
    await db.commit()
    
    # 清空缓存
    clear_inheritance_cache()
    
    return {"success": True, "message": "Genre prompt deleted"}


# ── 继承链查询 ────────────────────────────────────────────────────────────


@router.get("/packs/{pack_id}/chain", response_model=dict)
async def get_genre_inheritance_chain(
    pack_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取品类的继承链（从子到父）。"""
    genre_id = _parse_uuid(pack_id, "pack_id")
    
    chain = await get_genre_chain(db, genre_id)
    
    return {
        "chain": [_genre_to_dict(g) for g in chain],
        "depth": len(chain),
    }


# ── 缓存管理 ──────────────────────────────────────────────────────────────


@router.post("/cache/clear", response_model=dict)
async def clear_genre_cache(
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """清空品类继承解析缓存。"""
    clear_inheritance_cache()
    return {"success": True, "message": "Genre inheritance cache cleared"}
