"""
质量分析 API

提供小说质量分析相关的接口：
- 角色出场统计
- AI味检测
- 深度审查
- 情感弧线
- 金句检测
- 首章钩力分析
- 世界观约束检查
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from ...api.v1.config import require_admin_reads
from ...db import connect, decode
from ...services.novel_export import extract_body_text

from ..quality.structural_ai_smell import (
    analyze_structural_ai_smell,
    StructuralAISmellResult,
    StructuralDimensionResult,
)
from ..quality.character_balance import (
    analyze_character_balance,
    CharacterBalanceResult,
    CharacterStats as CharacterBalanceStats,
    _count_chinese_chars,
    estimate_character_word_count as _estimate_character_word_count,
)
from ..quality.emotional_arc import (
    analyze_emotional_arc,
    EmotionalArcResult,
)

router = APIRouter(
    prefix="",
    tags=["v7-quality"],
    dependencies=[Depends(require_admin_reads)],
)


# ============ 工具函数 ============

def _get_chapter_text(chapter_id: str) -> tuple[str, str, int]:
    """
    获取章节文本
    
    Returns:
        (text, novel_id, chapter_seq)
    """
    conn = connect()
    try:
        row = conn.execute(
            """
            SELECT body, parent_id, COALESCE(seq, (meta->>'seq')::int, 1) as seq
            FROM contents
            WHERE id = %s AND type = 'chapter' AND is_deleted = FALSE
            """,
            (chapter_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="章节不存在")
        text = extract_body_text(decode(row["body"], {}))
        return text, str(row["parent_id"]), int(row["seq"])
    finally:
        conn.close()


def _get_novel_chapters(novel_id: str) -> List[tuple[str, str, int]]:
    """
    获取小说所有章节
    
    Returns:
        [(chapter_id, text, chapter_seq), ...]
    """
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT id, body, COALESCE(seq, (meta->>'seq')::int, 1) as seq
            FROM contents
            WHERE parent_id = %s AND type = 'chapter' AND is_deleted = FALSE
            ORDER BY COALESCE(seq, (meta->>'seq')::int, 1) ASC
            """,
            (novel_id,),
        ).fetchall()
        result = []
        for row in rows:
            text = extract_body_text(decode(row["body"], {}))
            result.append((str(row["id"]), text, int(row["seq"])))
        return result
    finally:
        conn.close()


def _get_novel_characters(novel_id: str) -> List[str]:
    """
    获取小说角色列表
    """
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT title
            FROM knowledge_items
            WHERE project_id = (
                SELECT project_id FROM contents WHERE id = %s
            ) AND kind = 'character' AND is_deleted = FALSE
            ORDER BY created_at ASC
            """,
            (novel_id,),
        ).fetchall()
        return [row["title"] for row in rows]
    finally:
        conn.close()


def _get_novel_genre(novel_id: str) -> str:
    """
    获取小说品类
    """
    conn = connect()
    try:
        row = conn.execute(
            """
            SELECT meta FROM contents WHERE id = %s AND type = 'novel' AND is_deleted = FALSE
            """,
            (novel_id,),
        ).fetchone()
        if not row:
            return "default"
        meta = decode(row["meta"], {})
        return meta.get("genre", "default")
    finally:
        conn.close()


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
    actual: float = 0.0
    threshold: float = 0.0
    unit: str = ""
    risk_level: str = "low"  # low / medium / high
    description: str = ""
    examples: List[str] = []


class AiSmellResponse(BaseModel):
    """AI味检测响应"""
    chapter_id: str
    overall_risk: str = "low"
    overall_score: float = 0.0
    grade: str = ""
    passed: bool = True
    dimensions: List[AiSmellDimension]
    has_data: bool = False


class CharacterStats(BaseModel):
    """角色统计"""
    name: str
    appearance_count: int = 0
    total_mentions: int = 0
    word_count: int = 0
    word_ratio: float = 0.0
    first_appearance_chapter: int = 0
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
    has_warnings: bool = False
    high_risk_characters: List[CharacterStats] = []
    medium_risk_characters: List[CharacterStats] = []
    low_risk_characters: List[CharacterStats] = []
    suggestions: List[str] = []
    characters: List[CharacterStats]
    has_data: bool = False


class EmotionalArcPoint(BaseModel):
    """情感弧线上的点"""
    chapter: int
    chapter_id: str = ""
    chapter_title: str = ""
    emotion_score: float = 0.0
    valence: float = 0.0
    arousal: float = 0.0
    emotion_label: str = ""


class EmotionAnomalyItem(BaseModel):
    """情感异常点"""
    chapter: int
    chapter_title: str = ""
    anomaly_type: str  # fatigue / abrupt / depression
    description: str
    severity: str = "medium"  # low / medium / high


class EmotionalArcResponse(BaseModel):
    """情感弧线响应"""
    novel_id: str
    scores: List[float] = []
    valences: List[float] = []
    arousals: List[float] = []
    overall_score: float = 0.0
    arc_type: str = ""
    peak_chapter: int = 0
    valley_chapter: int = 0
    volatility: float = 0.0
    arc: List[EmotionalArcPoint]
    anomalies: List[EmotionAnomalyItem]
    suggestions: List[str] = []
    chapter_count: int = 0
    has_data: bool = False


class GoldenQuote(BaseModel):
    """金句"""
    text: str
    score: float
    quote_type: str = ""
    position: int = 0


class GoldenQuotesResponse(BaseModel):
    """金句检测响应"""
    chapter_id: str
    quotes: List[GoldenQuote]
    total_count: int = 0
    has_data: bool = False


class HookDimension(BaseModel):
    """钩力维度"""
    key: str
    name: str
    score: float
    description: str = ""


class HookAnalysisResponse(BaseModel):
    """首章钩力分析响应"""
    chapter_id: str
    overall_score: float = 0.0
    estimated_retention: float = 0.0
    dimensions: List[HookDimension] = []
    suggestions: List[str] = []
    has_data: bool = False


class WorldConstraintViolation(BaseModel):
    """世界观约束违规"""
    level: str  # high / medium / low
    category: str
    description: str
    position: int = 0


class WorldConstraintResponse(BaseModel):
    """世界观约束检查响应"""
    chapter_id: str
    violations: List[WorldConstraintViolation]
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
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
    # 获取章节文本
    text, novel_id, seq = _get_chapter_text(chapter_id)
    
    if not text.strip():
        return QualityReviewResponse(
            chapter_id=chapter_id,
            overall_score=0.0,
            dimensions=[],
            summary="章节内容为空",
            suggestions=[],
            has_data=False,
        )
    
    # 调用 AI 味检测
    ai_smell_result = analyze_structural_ai_smell(text)
    
    # 辅助函数：获取 AI 味维度得分
    def _get_ai_dim_score(dim_name: str) -> float:
        for dim in ai_smell_result.dimensions:
            if dim.name == dim_name:
                return dim.score
        return 70.0  # 默认分
    
    # 从 AI 味检测结果映射五维评分
    # 1. 文笔质量：直接用 AI 味总分
    writing_score = ai_smell_result.overall_score
    
    # 2. 节奏：段落节奏变异 + 转折词密度
    rhythm_score = (_get_ai_dim_score("段落节奏变异") + _get_ai_dim_score("转折词密度")) / 2
    
    # 3. 人物：对话省略比例（对话自然 = 人物刻画好）
    character_score = _get_ai_dim_score("对话省略比例")
    
    # 4. 剧情：总结句密度（总结句少 = 剧情在推进）
    plot_score = _get_ai_dim_score("总结句密度")
    
    # 5. 爽感：段落首句雷同 + "了"字密度（首句有变化 + 动作多 = 爽感强）
    thrill_score = (_get_ai_dim_score("段落首句雷同") + _get_ai_dim_score("\"了\"字密度")) / 2
    
    # 构建五维评分
    dimensions = [
        DimensionScore(
            key="thrill",
            name="爽感",
            score=round(thrill_score, 1),
            comment="基于段落变化与动作密度推导",
            level=_score_to_level(thrill_score),
        ),
        DimensionScore(
            key="rhythm",
            name="节奏",
            score=round(rhythm_score, 1),
            comment="基于段落节奏与转折密度推导",
            level=_score_to_level(rhythm_score),
        ),
        DimensionScore(
            key="plot",
            name="剧情",
            score=round(plot_score, 1),
            comment="基于叙事推进效率推导",
            level=_score_to_level(plot_score),
        ),
        DimensionScore(
            key="character",
            name="人物",
            score=round(character_score, 1),
            comment="基于对话自然度推导",
            level=_score_to_level(character_score),
        ),
        DimensionScore(
            key="writing_quality",
            name="文笔",
            score=round(writing_score, 1),
            comment=f"AI味检测总分 {ai_smell_result.overall_score:.1f}/100，等级 {ai_smell_result.grade}",
            level=_score_to_level(writing_score),
        ),
    ]
    
    # 计算总分（五维平均分）
    overall_score = sum(d.score for d in dimensions) / len(dimensions)
    
    # 收集建议
    suggestions = []
    for dim in ai_smell_result.dimensions:
        if not dim.passed:
            suggestions.append(f"{dim.name}：{dim.detail}")
    
    summary = f"章节质量评分 {overall_score:.1f}/100，{_score_to_level(overall_score)} 等级"
    
    return QualityReviewResponse(
        chapter_id=chapter_id,
        overall_score=round(overall_score, 1),
        dimensions=dimensions,
        summary=summary,
        suggestions=suggestions,
        has_data=True,
    )


@router.get("/chapters/{chapter_id}/ai-smell", response_model=AiSmellResponse)
async def get_ai_smell(
    chapter_id: str,
    threshold_preset: str = Query("default", description="阈值预设：tomato/qidian/jjwxc/default"),
):
    """
    获取章节 AI 味检测结果
    
    返回 7 维模式级检测结果
    """
    # 获取章节文本
    text, novel_id, seq = _get_chapter_text(chapter_id)
    
    if not text.strip():
        return AiSmellResponse(
            chapter_id=chapter_id,
            overall_risk="low",
            overall_score=0.0,
            grade="",
            passed=True,
            dimensions=[],
            has_data=False,
        )
    
    # 调用 AI 味检测
    result = analyze_structural_ai_smell(text, threshold_preset=threshold_preset)
    
    # 转换维度结果
    dimensions = []
    for dim in result.dimensions:
        risk_level = "low" if dim.passed else ("medium" if dim.score >= 60 else "high")
        dimensions.append(AiSmellDimension(
            key=_dimension_name_to_key(dim.name),
            name=dim.name,
            score=dim.score,
            actual=dim.actual,
            threshold=dim.threshold,
            unit=dim.unit,
            risk_level=risk_level,
            description=dim.detail,
            examples=dim.examples,
        ))
    
    # 计算整体风险等级
    overall_risk = "low" if result.passed else ("medium" if result.overall_score >= 60 else "high")
    
    return AiSmellResponse(
        chapter_id=chapter_id,
        overall_risk=overall_risk,
        overall_score=result.overall_score,
        grade=result.grade,
        passed=result.passed,
        dimensions=dimensions,
        has_data=True,
    )


@router.get("/chapters/{chapter_id}/character-stats", response_model=CharacterStatsResponse)
async def get_chapter_character_stats(
    chapter_id: str,
):
    """
    获取单章角色出场统计
    
    只返回在本章出场的角色，按出现次数降序排列
    """
    # 获取章节文本
    text, novel_id, seq = _get_chapter_text(chapter_id)
    
    if not text.strip():
        return CharacterStatsResponse(
            novel_id=novel_id,
            total_characters=0,
            total_chapters=1,
            balance_score=0.0,
            has_warnings=False,
            high_risk_characters=[],
            medium_risk_characters=[],
            low_risk_characters=[],
            suggestions=[],
            characters=[],
            has_data=False,
        )
    
    # 获取角色列表
    character_list = _get_novel_characters(novel_id)
    
    # 统计单章角色出场
    chapter_word_count = _count_chinese_chars(text)
    characters = []
    
    for name in character_list:
        mention_count = text.count(name)
        if mention_count == 0:
            continue  # 只返回出场的角色
        
        # 估算涉及字数
        word_count = _estimate_character_word_count(text, name)
        word_ratio = word_count / chapter_word_count if chapter_word_count > 0 else 0.0
        
        characters.append(CharacterStats(
            name=name,
            appearance_count=1,  # 单章出场次数就是1
            total_mentions=mention_count,
            word_count=word_count,
            word_ratio=word_ratio,
            first_appearance_chapter=seq,
            last_appearance_chapter=seq,
            chapters_since_last=0,
            forget_risk="low",
            importance="medium",
        ))
    
    # 按提及次数降序排列
    characters.sort(key=lambda x: x.total_mentions, reverse=True)
    
    return CharacterStatsResponse(
        novel_id=novel_id,
        total_characters=len(characters),
        total_chapters=1,
        balance_score=100.0,
        has_warnings=False,
        high_risk_characters=[],
        medium_risk_characters=[],
        low_risk_characters=characters,
        suggestions=[f"本章共 {len(characters)} 个角色出场"],
        characters=characters,
        has_data=True,
    )


@router.get("/novels/{novel_id}/character-stats", response_model=CharacterStatsResponse)
async def get_character_stats(
    novel_id: str,
    high_risk_threshold: int = Query(10, description="高风险阈值（多少章没出场算高风险）"),
    medium_risk_threshold: int = Query(5, description="中风险阈值"),
):
    """
    获取小说角色出场统计
    
    返回所有出场过的角色的出场次数、字数占比、遗忘风险等
    """
    # 获取所有章节
    chapters = _get_novel_chapters(novel_id)
    chapter_texts = [text for _, text, _ in chapters]
    
    if not chapter_texts:
        return CharacterStatsResponse(
            novel_id=novel_id,
            total_characters=0,
            total_chapters=0,
            balance_score=0.0,
            has_warnings=False,
            high_risk_characters=[],
            medium_risk_characters=[],
            low_risk_characters=[],
            suggestions=[],
            characters=[],
            has_data=False,
        )
    
    # 获取角色列表
    character_list = _get_novel_characters(novel_id)
    
    # 调用角色平衡分析
    result = analyze_character_balance(
        chapter_texts,
        character_list=character_list if character_list else None,
        high_risk_threshold=high_risk_threshold,
        medium_risk_threshold=medium_risk_threshold,
        auto_extract=not character_list,
    )
    
    # 转换角色统计
    def _convert_stats(stats: CharacterBalanceStats) -> CharacterStats:
        return CharacterStats(
            name=stats.name,
            appearance_count=stats.appearance_count,
            total_mentions=stats.total_mentions,
            word_count=stats.word_count,
            word_ratio=stats.word_ratio,
            first_appearance_chapter=stats.first_appearance_chapter,
            last_appearance_chapter=stats.last_appearance_chapter,
            chapters_since_last=stats.chapters_since_last,
            forget_risk=stats.forget_risk,
            importance=stats.importance,
        )
    
    # 只保留出场过的角色（appearance_count > 0）
    all_stats = [s for s in result.character_stats.values() if s.appearance_count > 0]
    
    high_risk = [_convert_stats(s) for s in result.high_risk_characters if s.appearance_count > 0]
    medium_risk = [_convert_stats(s) for s in result.medium_risk_characters if s.appearance_count > 0]
    low_risk = [_convert_stats(s) for s in result.low_risk_characters if s.appearance_count > 0]
    
    # 所有角色（按出场次数排序）
    all_characters = sorted(
        [_convert_stats(s) for s in all_stats],
        key=lambda x: x.appearance_count,
        reverse=True,
    )
    
    return CharacterStatsResponse(
        novel_id=novel_id,
        total_characters=len(all_characters),
        total_chapters=result.total_chapters,
        balance_score=result.balance_score,
        has_warnings=result.has_warnings,
        high_risk_characters=high_risk,
        medium_risk_characters=medium_risk,
        low_risk_characters=low_risk,
        suggestions=result.suggestions,
        characters=all_characters,
        has_data=True,
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
    # 获取所有章节
    chapters = _get_novel_chapters(novel_id)
    
    if not chapters:
        return EmotionalArcResponse(
            novel_id=novel_id,
            scores=[],
            valences=[],
            arousals=[],
            overall_score=0.0,
            arc_type="",
            peak_chapter=0,
            valley_chapter=0,
            volatility=0.0,
            arc=[],
            anomalies=[],
            suggestions=[],
            chapter_count=0,
            has_data=False,
        )
    
    # 过滤章节范围
    if start_chapter is not None or end_chapter is not None:
        filtered = []
        for ch_id, text, seq in chapters:
            if start_chapter is not None and seq < start_chapter:
                continue
            if end_chapter is not None and seq > end_chapter:
                continue
            filtered.append((ch_id, text, seq))
        chapters = filtered
    
    chapter_texts = [text for _, text, _ in chapters]
    
    # 调用情感弧线分析
    result = analyze_emotional_arc(chapter_texts)
    
    # 构建弧线点
    arc = []
    for i, (ch_id, text, seq) in enumerate(chapters):
        score = result.scores[i] if i < len(result.scores) else 0.0
        valence = result.valences[i] if i < len(result.valences) else 0.0
        arousal = result.arousals[i] if i < len(result.arousals) else 0.0
        arc.append(EmotionalArcPoint(
            chapter=seq,
            chapter_id=ch_id,
            chapter_title=f"第{seq}章",
            emotion_score=score,
            valence=valence,
            arousal=arousal,
            emotion_label=_emotion_score_to_label(score),
        ))
    
    # 转换异常点
    anomalies = []
    for anomaly in result.anomalies:
        anomalies.append(EmotionAnomalyItem(
            chapter=anomaly.chapter,
            chapter_title=f"第{anomaly.chapter}章",
            anomaly_type=anomaly.anomaly_type,
            description=anomaly.description,
            severity=anomaly.severity,
        ))
    
    return EmotionalArcResponse(
        novel_id=novel_id,
        scores=result.scores,
        valences=result.valences,
        arousals=result.arousals,
        overall_score=result.overall_score,
        arc_type=result.arc_type,
        peak_chapter=result.peak_chapter,
        valley_chapter=result.valley_chapter,
        volatility=result.volatility,
        arc=arc,
        anomalies=anomalies,
        suggestions=result.suggestions,
        chapter_count=result.chapter_count,
        has_data=True,
    )


@router.get("/chapters/{chapter_id}/golden-quotes", response_model=GoldenQuotesResponse)
async def get_golden_quotes(
    chapter_id: str,
):
    """
    获取章节金句检测结果
    
    返回金句列表（文本、评分、类型）
    """
    # 获取章节文本
    text, novel_id, seq = _get_chapter_text(chapter_id)
    
    if not text.strip():
        return GoldenQuotesResponse(
            chapter_id=chapter_id,
            quotes=[],
            total_count=0,
            has_data=False,
        )
    
    # 尝试导入金句检测模块
    try:
        from ..quality.golden_quote_detector import detect_golden_quotes
        quotes = detect_golden_quotes(text)
        
        result = []
        for q in quotes:
            result.append(GoldenQuote(
                text=q.text,
                score=q.score,
                quote_type=getattr(q, 'quote_type', ''),
                position=getattr(q, 'position', 0),
            ))
        
        return GoldenQuotesResponse(
            chapter_id=chapter_id,
            quotes=result,
            total_count=len(result),
            has_data=True,
        )
    except (ImportError, AttributeError):
        # 模块不存在或函数不存在，返回空
        return GoldenQuotesResponse(
            chapter_id=chapter_id,
            quotes=[],
            total_count=0,
            has_data=False,
        )


@router.get("/chapters/{chapter_id}/hook-analysis", response_model=HookAnalysisResponse)
async def get_hook_analysis(
    chapter_id: str,
):
    """
    获取首章钩力分析结果
    
    返回 6 维钩力报告 + 预估留存率
    """
    # 获取章节文本
    text, novel_id, seq = _get_chapter_text(chapter_id)
    
    if not text.strip():
        return HookAnalysisResponse(
            chapter_id=chapter_id,
            overall_score=0.0,
            estimated_retention=0.0,
            dimensions=[],
            suggestions=[],
            has_data=False,
        )
    
    # 尝试导入钩力分析模块
    try:
        from ..quality.hook_analysis import analyze_hook_power
        result = analyze_hook_power(text)
        
        dimensions = []
        if hasattr(result, 'dimensions'):
            for dim in result.dimensions:
                dimensions.append(HookDimension(
                    key=getattr(dim, 'key', ''),
                    name=getattr(dim, 'name', ''),
                    score=getattr(dim, 'score', 0.0),
                    description=getattr(dim, 'description', ''),
                ))
        
        return HookAnalysisResponse(
            chapter_id=chapter_id,
            overall_score=getattr(result, 'overall_score', 0.0),
            estimated_retention=getattr(result, 'estimated_retention', 0.0),
            dimensions=dimensions,
            suggestions=getattr(result, 'suggestions', []),
            has_data=True,
        )
    except (ImportError, AttributeError):
        # 模块不存在或函数不存在，返回空
        return HookAnalysisResponse(
            chapter_id=chapter_id,
            overall_score=0.0,
            estimated_retention=0.0,
            dimensions=[],
            suggestions=[],
            has_data=False,
        )


@router.get("/chapters/{chapter_id}/world-constraint", response_model=WorldConstraintResponse)
async def get_world_constraint(
    chapter_id: str,
):
    """
    获取世界观约束检查结果
    
    返回违规列表（高级/中级/低级）
    """
    # 获取章节文本
    text, novel_id, seq = _get_chapter_text(chapter_id)
    
    if not text.strip():
        return WorldConstraintResponse(
            chapter_id=chapter_id,
            violations=[],
            high_count=0,
            medium_count=0,
            low_count=0,
            has_data=False,
        )
    
    # 获取小说品类
    genre = _get_novel_genre(novel_id)
    
    # 尝试导入世界观约束模块
    try:
        from ..quality.world_constraint import get_constraint_pack
        pack = get_constraint_pack(genre)
        if not pack:
            return WorldConstraintResponse(
                chapter_id=chapter_id,
                violations=[],
                high_count=0,
                medium_count=0,
                low_count=0,
                has_data=False,
            )
        
        result = pack.check_text(text)
        
        violations = []
        high_count = 0
        medium_count = 0
        low_count = 0
        
        for v in result.get("violations", []):
            severity = v.get("severity", "low")
            level = severity
            violations.append(WorldConstraintViolation(
                level=level,
                category=v.get("category", ""),
                description=v.get("description", ""),
                position=0,
            ))
            if level == 'high':
                high_count += 1
            elif level == 'medium':
                medium_count += 1
            else:
                low_count += 1
        
        return WorldConstraintResponse(
            chapter_id=chapter_id,
            violations=violations,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            has_data=True,
        )
    except (ImportError, AttributeError):
        # 模块不存在或函数不存在，返回空
        return WorldConstraintResponse(
            chapter_id=chapter_id,
            violations=[],
            high_count=0,
            medium_count=0,
            low_count=0,
            has_data=False,
        )


# ============ 辅助函数 ============

def _score_to_level(score: float) -> str:
    """将分数转换为等级"""
    if score >= 90:
        return "excellent"
    elif score >= 75:
        return "good"
    elif score >= 60:
        return "normal"
    elif score >= 40:
        return "warning"
    else:
        return "danger"


def _dimension_name_to_key(name: str) -> str:
    """将维度名称转换为 key"""
    name_map = {
        "转折词密度": "transition_word_density",
        "段落首句雷同": "paragraph_opening_repeat",
        "抽象副词": "abstract_adverb_density",
        "\"了\"字密度": "le_word_density",
        "总结句": "summary_sentence_density",
        "对话完整度": "dialogue_omit_ratio",
        "段落节奏": "paragraph_rhythm_cv",
    }
    return name_map.get(name, name.lower().replace(" ", "_"))


def _emotion_score_to_label(score: float) -> str:
    """将情感分数转换为标签"""
    if score >= 8:
        return "强烈积极"
    elif score >= 6:
        return "积极"
    elif score >= 4:
        return "中性"
    elif score >= 2:
        return "消极"
    else:
        return "强烈消极"
