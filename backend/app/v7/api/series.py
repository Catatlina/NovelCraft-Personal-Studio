"""
系列 API — 跨系列世界共享

提供系列、系列成员、系列知识库的 CRUD 操作。
多个小说项目可以共享同一世界观知识库。
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import get_async_db as get_db
from ..models.series import Series, SeriesMember, SeriesKnowledge
from ...api.v1.config import require_admin, require_admin_reads

router = APIRouter(
    prefix="/series",
    tags=["v7-series"],
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


def _series_to_dict(series: Series, include_counts: bool = False) -> dict[str, Any]:
    """把系列对象转成字典。"""
    result = {
        "id": str(series.id),
        "name": series.name,
        "slug": series.slug,
        "description": series.description,
        "icon_url": series.icon_url,
        "settings": series.settings,
        "is_active": series.is_active,
        "is_public": series.is_public,
        "owner_id": str(series.owner_id) if series.owner_id else None,
        "created_at": series.created_at.isoformat() if series.created_at else None,
        "updated_at": series.updated_at.isoformat() if series.updated_at else None,
    }
    if include_counts:
        result["member_count"] = len(series.members) if series.members else 0
        result["knowledge_count"] = len(series.knowledge) if series.knowledge else 0
    return result


def _member_to_dict(member: SeriesMember) -> dict[str, Any]:
    """把系列成员对象转成字典。"""
    return {
        "id": str(member.id),
        "series_id": str(member.series_id),
        "novel_id": str(member.novel_id),
        "role": member.role,
        "sort_order": member.sort_order,
        "can_write": member.can_write,
        "joined_at": member.joined_at.isoformat() if member.joined_at else None,
        "created_at": member.created_at.isoformat() if member.created_at else None,
        "updated_at": member.updated_at.isoformat() if member.updated_at else None,
    }


def _knowledge_to_dict(knowledge: SeriesKnowledge) -> dict[str, Any]:
    """把系列知识对象转成字典。"""
    return {
        "id": str(knowledge.id),
        "series_id": str(knowledge.series_id),
        "knowledge_type": knowledge.knowledge_type,
        "title": knowledge.title,
        "content": knowledge.content,
        "tags": knowledge.tags,
        "importance": knowledge.importance,
        "source_novel_id": str(knowledge.source_novel_id) if knowledge.source_novel_id else None,
        "is_active": knowledge.is_active,
        "is_approved": knowledge.is_approved,
        "extra_metadata": knowledge.extra_metadata,
        "created_at": knowledge.created_at.isoformat() if knowledge.created_at else None,
        "updated_at": knowledge.updated_at.isoformat() if knowledge.updated_at else None,
    }


# ── Series CRUD ─────────────────────────────────────────────────────────


@router.get("")
async def list_series(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """列出系列。"""
    query = select(Series).options(
        selectinload(Series.members),
        selectinload(Series.knowledge),
    )

    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                Series.name.ilike(search_pattern),
                Series.slug.ilike(search_pattern),
                Series.description.ilike(search_pattern),
            )
        )

    if is_active is not None:
        query = query.where(Series.is_active == is_active)

    query = query.order_by(Series.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    series_list = result.scalars().all()

    return {
        "items": [_series_to_dict(s, include_counts=True) for s in series_list],
        "total": len(series_list),
        "skip": skip,
        "limit": limit,
    }


@router.get("/{series_id}")
async def get_series(
    series_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取系列详情。"""
    sid = _parse_uuid(series_id, "series_id")

    query = select(Series).options(
        selectinload(Series.members),
        selectinload(Series.knowledge),
    ).where(Series.id == sid)
    result = await db.execute(query)
    series = result.scalar_one_or_none()

    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    return _series_to_dict(series, include_counts=True)


@router.post("", dependencies=[Depends(require_admin)])
async def create_series(
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """创建系列。"""
    name = data.get("name", "").strip()
    slug = data.get("slug", "").strip()

    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if not slug:
        raise HTTPException(status_code=400, detail="Slug is required")

    # 检查 slug 是否存在
    existing = await db.execute(select(Series).where(Series.slug == slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Slug already exists")

    series = Series(
        name=name,
        slug=slug,
        description=data.get("description"),
        icon_url=data.get("icon_url"),
        settings=data.get("settings", {}),
        is_active=data.get("is_active", True),
        is_public=data.get("is_public", False),
        owner_id=_parse_optional_uuid(data.get("owner_id"), "owner_id"),
    )

    db.add(series)
    await db.flush()
    await db.refresh(series)

    return _series_to_dict(series)


@router.put("/{series_id}", dependencies=[Depends(require_admin)])
async def update_series(
    series_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """更新系列。"""
    sid = _parse_uuid(series_id, "series_id")

    result = await db.execute(select(Series).where(Series.id == sid))
    series = result.scalar_one_or_none()

    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    # 更新字段
    if "name" in data:
        series.name = data["name"].strip()
    if "slug" in data:
        new_slug = data["slug"].strip()
        if new_slug != series.slug:
            existing = await db.execute(
                select(Series).where(Series.slug == new_slug, Series.id != sid)
            )
            if existing.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Slug already exists")
            series.slug = new_slug
    if "description" in data:
        series.description = data["description"]
    if "icon_url" in data:
        series.icon_url = data["icon_url"]
    if "settings" in data:
        series.settings = data["settings"]
    if "is_active" in data:
        series.is_active = data["is_active"]
    if "is_public" in data:
        series.is_public = data["is_public"]

    await db.flush()
    await db.refresh(series)

    return _series_to_dict(series)


@router.delete("/{series_id}", dependencies=[Depends(require_admin)])
async def delete_series(
    series_id: str,
    db: AsyncSession = Depends(get_db),
):
    """删除系列。"""
    sid = _parse_uuid(series_id, "series_id")

    result = await db.execute(select(Series).where(Series.id == sid))
    series = result.scalar_one_or_none()

    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    await db.delete(series)
    await db.flush()

    return {"success": True, "message": "Series deleted"}


# ── Series Members ──────────────────────────────────────────────────────


@router.get("/{series_id}/members")
async def list_series_members(
    series_id: str,
    db: AsyncSession = Depends(get_db),
):
    """列出系列成员。"""
    sid = _parse_uuid(series_id, "series_id")

    # 先确认系列存在
    series_result = await db.execute(select(Series).where(Series.id == sid))
    if not series_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Series not found")

    query = select(SeriesMember).where(
        SeriesMember.series_id == sid
    ).order_by(SeriesMember.sort_order, SeriesMember.joined_at)

    result = await db.execute(query)
    members = result.scalars().all()

    return {
        "items": [_member_to_dict(m) for m in members],
        "total": len(members),
    }


@router.post("/{series_id}/members", dependencies=[Depends(require_admin)])
async def add_series_member(
    series_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """添加系列成员。"""
    sid = _parse_uuid(series_id, "series_id")
    novel_id = _parse_uuid(data.get("novel_id", ""), "novel_id")

    # 先确认系列存在
    series_result = await db.execute(select(Series).where(Series.id == sid))
    if not series_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Series not found")

    # 检查是否已经是成员
    existing = await db.execute(
        select(SeriesMember).where(
            SeriesMember.series_id == sid,
            SeriesMember.novel_id == novel_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Novel already in series")

    member = SeriesMember(
        series_id=sid,
        novel_id=novel_id,
        role=data.get("role", "main"),
        sort_order=data.get("sort_order", 0),
        can_write=data.get("can_write", True),
    )

    db.add(member)
    await db.flush()
    await db.refresh(member)

    return _member_to_dict(member)


@router.put("/{series_id}/members/{member_id}", dependencies=[Depends(require_admin)])
async def update_series_member(
    series_id: str,
    member_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """更新系列成员。"""
    sid = _parse_uuid(series_id, "series_id")
    mid = _parse_uuid(member_id, "member_id")

    result = await db.execute(
        select(SeriesMember).where(
            SeriesMember.id == mid,
            SeriesMember.series_id == sid,
        )
    )
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if "role" in data:
        member.role = data["role"]
    if "sort_order" in data:
        member.sort_order = data["sort_order"]
    if "can_write" in data:
        member.can_write = data["can_write"]

    await db.flush()
    await db.refresh(member)

    return _member_to_dict(member)


@router.delete("/{series_id}/members/{member_id}", dependencies=[Depends(require_admin)])
async def remove_series_member(
    series_id: str,
    member_id: str,
    db: AsyncSession = Depends(get_db),
):
    """移除系列成员。"""
    sid = _parse_uuid(series_id, "series_id")
    mid = _parse_uuid(member_id, "member_id")

    result = await db.execute(
        select(SeriesMember).where(
            SeriesMember.id == mid,
            SeriesMember.series_id == sid,
        )
    )
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    await db.delete(member)
    await db.flush()

    return {"success": True, "message": "Member removed"}


# ── Series Knowledge ────────────────────────────────────────────────────


@router.get("/{series_id}/knowledge")
async def list_series_knowledge(
    series_id: str,
    knowledge_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """列出系列知识库。"""
    sid = _parse_uuid(series_id, "series_id")

    # 先确认系列存在
    series_result = await db.execute(select(Series).where(Series.id == sid))
    if not series_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Series not found")

    query = select(SeriesKnowledge).where(
        SeriesKnowledge.series_id == sid,
        SeriesKnowledge.is_active == True,
    )

    if knowledge_type:
        query = query.where(SeriesKnowledge.knowledge_type == knowledge_type)

    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                SeriesKnowledge.title.ilike(search_pattern),
                SeriesKnowledge.content.ilike(search_pattern),
            )
        )

    query = query.order_by(
        SeriesKnowledge.importance.desc(),
        SeriesKnowledge.updated_at.desc(),
    ).offset(skip).limit(limit)

    result = await db.execute(query)
    knowledge_list = result.scalars().all()

    return {
        "items": [_knowledge_to_dict(k) for k in knowledge_list],
        "total": len(knowledge_list),
        "skip": skip,
        "limit": limit,
    }


@router.post("/{series_id}/knowledge", dependencies=[Depends(require_admin)])
async def create_series_knowledge(
    series_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """创建系列知识条目。"""
    sid = _parse_uuid(series_id, "series_id")

    # 先确认系列存在
    series_result = await db.execute(select(Series).where(Series.id == sid))
    if not series_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Series not found")

    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    knowledge_type = data.get("knowledge_type", "reference")

    if not title:
        raise HTTPException(status_code=400, detail="Title is required")
    if not content:
        raise HTTPException(status_code=400, detail="Content is required")

    knowledge = SeriesKnowledge(
        series_id=sid,
        knowledge_type=knowledge_type,
        title=title,
        content=content,
        tags=data.get("tags", []),
        importance=data.get("importance", 50),
        source_novel_id=_parse_optional_uuid(data.get("source_novel_id"), "source_novel_id"),
        is_active=data.get("is_active", True),
        is_approved=data.get("is_approved", True),
        extra_metadata=data.get("extra_metadata", {}),
    )

    db.add(knowledge)
    await db.flush()
    await db.refresh(knowledge)

    return _knowledge_to_dict(knowledge)


@router.put("/{series_id}/knowledge/{knowledge_id}", dependencies=[Depends(require_admin)])
async def update_series_knowledge(
    series_id: str,
    knowledge_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """更新系列知识条目。"""
    sid = _parse_uuid(series_id, "series_id")
    kid = _parse_uuid(knowledge_id, "knowledge_id")

    result = await db.execute(
        select(SeriesKnowledge).where(
            SeriesKnowledge.id == kid,
            SeriesKnowledge.series_id == sid,
        )
    )
    knowledge = result.scalar_one_or_none()

    if not knowledge:
        raise HTTPException(status_code=404, detail="Knowledge not found")

    # 更新字段
    if "title" in data:
        knowledge.title = data["title"].strip()
    if "content" in data:
        knowledge.content = data["content"].strip()
    if "knowledge_type" in data:
        knowledge.knowledge_type = data["knowledge_type"]
    if "tags" in data:
        knowledge.tags = data["tags"]
    if "importance" in data:
        knowledge.importance = data["importance"]
    if "is_active" in data:
        knowledge.is_active = data["is_active"]
    if "is_approved" in data:
        knowledge.is_approved = data["is_approved"]
    if "extra_metadata" in data:
        knowledge.extra_metadata = data["extra_metadata"]

    await db.flush()
    await db.refresh(knowledge)

    return _knowledge_to_dict(knowledge)


@router.delete("/{series_id}/knowledge/{knowledge_id}", dependencies=[Depends(require_admin)])
async def delete_series_knowledge(
    series_id: str,
    knowledge_id: str,
    db: AsyncSession = Depends(get_db),
):
    """删除系列知识条目。"""
    sid = _parse_uuid(series_id, "series_id")
    kid = _parse_uuid(knowledge_id, "knowledge_id")

    result = await db.execute(
        select(SeriesKnowledge).where(
            SeriesKnowledge.id == kid,
            SeriesKnowledge.series_id == sid,
        )
    )
    knowledge = result.scalar_one_or_none()

    if not knowledge:
        raise HTTPException(status_code=404, detail="Knowledge not found")

    # 软删除：设置 is_active = False
    knowledge.is_active = False
    await db.flush()

    return {"success": True, "message": "Knowledge deleted"}


# ── Novel's Series ──────────────────────────────────────────────────────


@router.get("/by-novel/{novel_id}")
async def get_novel_series(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取某部小说所属的所有系列。"""
    nid = _parse_uuid(novel_id, "novel_id")

    query = select(SeriesMember).where(
        SeriesMember.novel_id == nid
    ).options(selectinload(SeriesMember.series))

    result = await db.execute(query)
    members = result.scalars().all()

    return {
        "items": [
            {
                **_series_to_dict(m.series),
                "role": m.role,
                "can_write": m.can_write,
                "joined_at": m.joined_at.isoformat() if m.joined_at else None,
            }
            for m in members
            if m.series
        ],
        "total": len(members),
    }
