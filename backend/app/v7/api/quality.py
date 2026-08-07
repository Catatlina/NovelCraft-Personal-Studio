"""
质量分析 API

提供小说质量分析相关的接口：
- 角色出场统计
- AI味检测
- 深度审查
- 情感弧线

注意：当前版本返回空数据结构，前端显示真实空状态。
后续版本将接入真实的分析引擎。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from ...api.v1.config import require_admin_reads

router = APIRouter(
    prefix="",
    tags=["v7-quality"],
    dependencies=[Depends(require_admin_reads)],
)


# ============ 数据模型 ============

class DimensionScore(BaseModel):
    """维度评分"""
    key: str
    name: str
    score: float
    max_score: float = 100.0
    comment: str = ""
    level: str = "normal"  # excellent / good / normal / warning / danger


class QualityReviewResponse(BaseModel):
    """质量审查响应"""
    chapter_id: str
    overall_score: float
    dimensions: List[DimensionScore]
    summary: str = ""
    suggestions: List[str] = []
    has_data: bool = False


class AiSmellDimension(BaseModel):
    """AI味检测维度"""
    key: str
    name: str
    score: float
    risk_level: str = "low"  # low / medium / high
    description: str = ""


class AiSmellResponse(BaseModel):
    """AI味检测响应"""
    chapter_id: str
    overall_risk: str = "low"
    overall_score: float = 0.0
    dimensions: List[AiSmellDimension]
    has_data: bool = False


class CharacterStats(BaseModel):
    """角色统计"""
    name: str
    appearance_count: int = 0
    word_count: int = 0
    word_ratio: float = 0.0
    last_appearance_chapter: int = 0
    chapters_since_last: int = 0
    forget_risk: str = "low"  # low / medium / high
    importance: str = "medium"  # high / medium / low


class CharacterStatsResponse(BaseModel):
    """角色统计响应"""
    novel_id: str
    total_characters: int = 0
    total_chapters: int = 0
    balance_score: float = 0.0
    characters: List[CharacterStats]
    has_data: bool = False


class EmotionalArcPoint(BaseModel):
    """情感弧线上的点"""
    chapter: int
    chapter_title: str = ""
    emotion_score: float = 0.0
    emotion_label: str = ""


class EmotionAnomaly(BaseModel):
    """情感异常点"""
    chapter: int
    chapter_title: str = ""
    anomaly_type: str  # fatigue / abrupt / depression
    description: str
    severity: str = "medium"  # low / medium / high


class EmotionalArcResponse(BaseModel):
    """情感弧线响应"""
    novel_id: str
    arc: List[EmotionalArcPoint]
    anomalies: List[EmotionAnomaly]
    has_data: bool = False


# ============ API 端点 ============

@router.get("/chapters/{chapter_id}/quality-review", response_model=QualityReviewResponse)
async def get_quality_review(
    chapter_id: str,
):
    """
    获取章节质量审查结果
    
    返回五维评分：一致性、角色声音、情节逻辑、节奏、文笔质量
    """
    # TODO: 接入真实的质量审查引擎
    # 当前返回空数据结构，前端显示真实空状态
    
    return QualityReviewResponse(
        chapter_id=chapter_id,
        overall_score=0.0,
        dimensions=[],
        summary="",
        suggestions=[],
        has_data=False,
    )


@router.get("/chapters/{chapter_id}/ai-smell", response_model=AiSmellResponse)
async def get_ai_smell(
    chapter_id: str,
):
    """
    获取章节 AI 味检测结果
    
    返回 7 维模式级检测结果
    """
    # TODO: 接入真实的 AI 味检测引擎（structural_ai_smell.py）
    # 当前返回空数据结构，前端显示真实空状态
    
    return AiSmellResponse(
        chapter_id=chapter_id,
        overall_risk="low",
        overall_score=0.0,
        dimensions=[],
        has_data=False,
    )


@router.get("/novels/{novel_id}/character-stats", response_model=CharacterStatsResponse)
async def get_character_stats(
    novel_id: str,
):
    """
    获取小说角色出场统计
    
    返回所有角色的出场次数、字数占比、遗忘风险等
    """
    # TODO: 接入真实的角色平衡分析引擎（character_balance.py）
    # 当前返回空数据结构，前端显示真实空状态
    
    return CharacterStatsResponse(
        novel_id=novel_id,
        total_characters=0,
        total_chapters=0,
        balance_score=0.0,
        characters=[],
        has_data=False,
    )


@router.get("/novels/{novel_id}/emotional-arc", response_model=EmotionalArcResponse)
async def get_emotional_arc(
    novel_id: str,
    start_chapter: Optional[int] = Query(None, description="起始章节号"),
    end_chapter: Optional[int] = Query(None, description="结束章节号"),
):
    """
    获取小说情感弧线
    
    返回每章情感分和异常点列表
    """
    # TODO: 接入真实的情感弧线分析引擎（emotional_arc.py）
    # 当前返回空数据结构，前端显示真实空状态
    
    return EmotionalArcResponse(
        novel_id=novel_id,
        arc=[],
        anomalies=[],
        has_data=False,
    )
