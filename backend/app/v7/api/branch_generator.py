"""
分支生成器 API — 剧情分支探索

提供剧情分支生成、保存、应用功能。
作者可以选中某段文字，AI 生成 1-3 条不同走向的分支，
作者可以选择应用某条分支，或者保存为草稿。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import get_async_db as get_db
from ...api.v1.config import require_admin, require_admin_reads

router = APIRouter(
    prefix="/branches",
    tags=["v7-branches"],
    dependencies=[Depends(require_admin_reads)],
)


# ── Data Models (in-memory for now, can be moved to DB later) ──────────

# 注意：分支数据暂时用内存存储，后续可以考虑持久化到数据库
# 这里先定义数据结构和 API 接口

class BranchOption:
    """分支选项。"""
    def __init__(
        self,
        id: str,
        title: str,
        content: str,
        direction: str,
        confidence: float = 0.8,
    ):
        self.id = id
        self.title = title
        self.content = content
        self.direction = direction  # 分支走向描述
        self.confidence = confidence
        self.created_at = datetime.utcnow()


class BranchGenerationResult:
    """分支生成结果。"""
    def __init__(
        self,
        id: str,
        novel_id: str,
        chapter_id: str,
        source_text: str,
        source_start: int,
        source_end: int,
        options: List[BranchOption],
        status: str = "completed",
    ):
        self.id = id
        self.novel_id = novel_id
        self.chapter_id = chapter_id
        self.source_text = source_text
        self.source_start = source_start
        self.source_end = source_end
        self.options = options
        self.status = status
        self.created_at = datetime.utcnow()


# 内存存储（临时方案，后续可持久化）
_branch_store: dict[str, BranchGenerationResult] = {}


# ── Helpers ─────────────────────────────────────────────────────────────


def _parse_uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {field}")


def _branch_option_to_dict(option: BranchOption) -> dict[str, Any]:
    return {
        "id": option.id,
        "title": option.title,
        "content": option.content,
        "direction": option.direction,
        "confidence": option.confidence,
        "created_at": option.created_at.isoformat() if option.created_at else None,
    }


def _branch_result_to_dict(result: BranchGenerationResult) -> dict[str, Any]:
    return {
        "id": result.id,
        "novel_id": result.novel_id,
        "chapter_id": result.chapter_id,
        "source_text": result.source_text,
        "source_start": result.source_start,
        "source_end": result.source_end,
        "options": [_branch_option_to_dict(o) for o in result.options],
        "status": result.status,
        "created_at": result.created_at.isoformat() if result.created_at else None,
    }


def _generate_mock_branches(
    source_text: str,
    num_options: int = 3,
) -> List[BranchOption]:
    """生成模拟分支（用于演示，实际应该调用 AI）。

    实际实现中，这里应该调用 AI gateway 来生成不同走向的剧情分支。
    """
    directions = [
        ("冲突升级", "让矛盾更加激烈，推动剧情快速发展"),
        ("反转剧情", "出现意想不到的转折，打破读者预期"),
        ("埋下伏笔", "引入新的线索，为后续剧情做铺垫"),
        ("人物成长", "通过事件让主角获得成长或领悟"),
        ("引入新角色", "出现新的关键人物，改变局势"),
    ]

    options = []
    for i in range(min(num_options, len(directions))):
        direction_name, direction_desc = directions[i]
        option = BranchOption(
            id=str(uuid.uuid4()),
            title=f"分支{i + 1}：{direction_name}",
            content=f"【{direction_name}走向】\n\n这是{direction_name}方向的剧情分支示例内容。\n\n在实际使用中，这里会由 AI 根据上下文生成 200-500 字的具体剧情内容，提供不同的故事走向供作者选择。\n\n{direction_desc}",
            direction=direction_desc,
            confidence=0.7 + i * 0.05,
        )
        options.append(option)

    return options


# ── Branch Generation API ──────────────────────────────────────────────


@router.post("/generate")
async def generate_branches(
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """生成剧情分支。

    根据选中的文本和上下文，生成 1-3 条不同走向的分支。

    请求体：
    - novel_id: 小说 ID
    - chapter_id: 章节 ID
    - source_text: 选中的源文本
    - source_start: 源文本起始位置
    - source_end: 源文本结束位置
    - num_options: 生成选项数量（默认 3）
    - context: 额外上下文（可选）
    """
    novel_id = data.get("novel_id", "")
    chapter_id = data.get("chapter_id", "")
    source_text = data.get("source_text", "")
    source_start = data.get("source_start", 0)
    source_end = data.get("source_end", 0)
    num_options = data.get("num_options", 3)

    if not novel_id:
        raise HTTPException(status_code=400, detail="novel_id is required")
    if not chapter_id:
        raise HTTPException(status_code=400, detail="chapter_id is required")
    if not source_text:
        raise HTTPException(status_code=400, detail="source_text is required")
    if len(source_text) < 10:
        raise HTTPException(status_code=400, detail="source_text too short")

    # 生成分支（目前是模拟数据，实际应调用 AI）
    options = _generate_mock_branches(source_text, num_options)

    # 保存结果
    result_id = str(uuid.uuid4())
    result = BranchGenerationResult(
        id=result_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        source_text=source_text,
        source_start=source_start,
        source_end=source_end,
        options=options,
        status="completed",
    )
    _branch_store[result_id] = result

    return _branch_result_to_dict(result)


@router.get("/{branch_id}")
async def get_branch(
    branch_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取分支生成结果。"""
    result = _branch_store.get(branch_id)
    if not result:
        raise HTTPException(status_code=404, detail="Branch not found")
    return _branch_result_to_dict(result)


@router.post("/{branch_id}/apply")
async def apply_branch(
    branch_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """应用分支到正文。

    请求体：
    - option_id: 要应用的分支选项 ID
    - mode: 应用模式（replace/insert_after/insert_before）
    """
    result = _branch_store.get(branch_id)
    if not result:
        raise HTTPException(status_code=404, detail="Branch not found")

    option_id = data.get("option_id", "")
    mode = data.get("mode", "replace")

    # 找到对应的选项
    selected_option = None
    for opt in result.options:
        if opt.id == option_id:
            selected_option = opt
            break

    if not selected_option:
        raise HTTPException(status_code=404, detail="Option not found")

    # 注意：实际应用操作应该调用编辑器相关的 API 或服务
    # 这里只返回应用信息，实际应用由前端处理

    return {
        "success": True,
        "branch_id": branch_id,
        "option_id": option_id,
        "mode": mode,
        "content": selected_option.content,
        "message": "分支内容已准备好，可以应用到编辑器",
    }


@router.post("/{branch_id}/save")
async def save_branch(
    branch_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """保存分支为草稿。

    请求体：
    - option_id: 要保存的分支选项 ID
    - title: 草稿标题（可选）
    - notes: 备注（可选）
    """
    result = _branch_store.get(branch_id)
    if not result:
        raise HTTPException(status_code=404, detail="Branch not found")

    option_id = data.get("option_id", "")
    title = data.get("title", "")
    notes = data.get("notes", "")

    # 找到对应的选项
    selected_option = None
    for opt in result.options:
        if opt.id == option_id:
            selected_option = opt
            break

    if not selected_option:
        raise HTTPException(status_code=404, detail="Option not found")

    # 注意：实际保存操作应该持久化到数据库
    # 这里只返回保存信息，实际保存逻辑待实现

    return {
        "success": True,
        "branch_id": branch_id,
        "option_id": option_id,
        "saved_title": title or selected_option.title,
        "saved_content": selected_option.content,
        "notes": notes,
        "message": "分支已保存为草稿",
    }


@router.get("/by-chapter/{chapter_id}")
async def list_chapter_branches(
    chapter_id: str,
    db: AsyncSession = Depends(get_db),
):
    """列出某章节的所有分支。"""
    # 从内存存储中筛选
    branches = [
        _branch_result_to_dict(b)
        for b in _branch_store.values()
        if b.chapter_id == chapter_id
    ]
    branches.sort(key=lambda x: x["created_at"], reverse=True)

    return {
        "items": branches,
        "total": len(branches),
    }


# ── Branch Exploration Stats ───────────────────────────────────────────


@router.get("/stats/{novel_id}")
async def get_branch_stats(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取某小说的分支探索统计。"""
    # 从内存存储中统计
    novel_branches = [
        b for b in _branch_store.values()
        if b.novel_id == novel_id
    ]

    total_generations = len(novel_branches)
    total_options = sum(len(b.options) for b in novel_branches)

    return {
        "novel_id": novel_id,
        "total_generations": total_generations,
        "total_options": total_options,
        "avg_options_per_generation": total_options / total_generations if total_generations > 0 else 0,
        "applied_count": 0,  # 待实现
        "saved_count": 0,  # 待实现
    }
