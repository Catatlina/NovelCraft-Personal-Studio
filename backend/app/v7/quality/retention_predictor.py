"""
读者留存预测器

功能：
1. 基于40维特征向量预测读者留存率
2. 拖累因素排名（前3名）
3. 改进建议生成
4. 基于规则的启发式预测，零AI调用
5. 支持多品类基准值对比

使用方式：
    from app.v7.quality.retention_predictor import predict_retention, RetentionPrediction

    # 预测留存率
    result = predict_retention(features, platform="fanqie")
    print(result.predicted_retention)  # 预测留存率 0-100%
    print(result.top_drag_factors)  # 前3名拖累因素
    print(result.suggestions)  # 改进建议
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


# ============================================================
# 特征维度定义
# ============================================================

# 40维特征定义
FEATURE_DEFINITIONS = {
    # === 章节基础（5维） ===
    "word_count": {
        "name": "章节字数",
        "category": "chapter_basic",
        "direction": "optimal",  # optimal=有最优区间，higher=越高越好，lower=越低越好
        "weight": 1.0,
        "description": "章节总字数",
    },
    "paragraph_count": {
        "name": "段落数量",
        "category": "chapter_basic",
        "direction": "optimal",
        "weight": 0.5,
        "description": "段落总数",
    },
    "dialogue_ratio": {
        "name": "对话占比",
        "category": "chapter_basic",
        "direction": "optimal",
        "weight": 1.5,
        "description": "对话字数占总字数比例",
    },
    "short_sentence_ratio": {
        "name": "短句比例",
        "category": "chapter_basic",
        "direction": "higher",
        "weight": 1.0,
        "description": "短句（15字以内）占比",
    },
    "avg_paragraph_length": {
        "name": "平均段落长度",
        "category": "chapter_basic",
        "direction": "lower",
        "weight": 0.8,
        "description": "平均每段字数",
    },

    # === AI味指标（7维） ===
    "le_word_density": {
        "name": "了字密度",
        "category": "ai_smell",
        "direction": "lower",
        "weight": 2.0,
        "description": "每千字'了'字出现次数",
    },
    "transition_word_density": {
        "name": "转折词密度",
        "category": "ai_smell",
        "direction": "lower",
        "weight": 1.5,
        "description": "每千字转折词出现次数",
    },
    "abstract_adverb_density": {
        "name": "抽象副词密度",
        "category": "ai_smell",
        "direction": "lower",
        "weight": 1.8,
        "description": "每千字抽象副词出现次数",
    },
    "summary_sentence_density": {
        "name": "总结句密度",
        "category": "ai_smell",
        "direction": "lower",
        "weight": 1.2,
        "description": "每千字总结句出现次数",
    },
    "paragraph_opening_repeat": {
        "name": "段落首句雷同",
        "category": "ai_smell",
        "direction": "lower",
        "weight": 1.5,
        "description": "连续段落首句雷同比例",
    },
    "dialogue_omit_ratio": {
        "name": "对话省略比例",
        "category": "ai_smell",
        "direction": "higher",
        "weight": 1.0,
        "description": "对话中省略主语/宾语的比例",
    },
    "paragraph_rhythm_cv": {
        "name": "段落节奏变异",
        "category": "ai_smell",
        "direction": "higher",
        "weight": 1.0,
        "description": "段落长度变异系数",
    },

    # === 爽点指标（5维） ===
    "payoff_density": {
        "name": "爽点密度",
        "category": "payoff",
        "direction": "higher",
        "weight": 3.0,  # 最高权重
        "description": "每千字爽点数量",
    },
    "payoff_intensity_avg": {
        "name": "爽点平均强度",
        "category": "payoff",
        "direction": "higher",
        "weight": 2.5,
        "description": "爽点平均强度评分",
    },
    "payoff_type_diversity": {
        "name": "爽点类型多样性",
        "category": "payoff",
        "direction": "higher",
        "weight": 1.0,
        "description": "爽点类型数量",
    },
    "first_payoff_position": {
        "name": "首个爽点位置",
        "category": "payoff",
        "direction": "lower",
        "weight": 2.0,
        "description": "第一个爽点出现的位置（越靠前越好）",
    },
    "payoff_climax_count": {
        "name": "高潮爽点数量",
        "category": "payoff",
        "direction": "higher",
        "weight": 1.5,
        "description": "peak级别的爽点数量",
    },

    # === 节奏指标（6维） ===
    "info_density": {
        "name": "信息密度",
        "category": "pacing",
        "direction": "optimal",
        "weight": 1.2,
        "description": "平均信息密度",
    },
    "opening_hook_score": {
        "name": "开篇钩子强度",
        "category": "pacing",
        "direction": "higher",
        "weight": 3.0,  # 最高权重
        "description": "前100字钩子强度评分",
    },
    "ending_hook_score": {
        "name": "章末钩子强度",
        "category": "pacing",
        "direction": "higher",
        "weight": 2.5,
        "description": "章末钩子锋利度评分",
    },
    "conflict_density": {
        "name": "冲突密度",
        "category": "pacing",
        "direction": "higher",
        "weight": 2.0,
        "description": "每千字冲突/危险信号数量",
    },
    "info_dump_position": {
        "name": "背景倒灌位置",
        "category": "pacing",
        "direction": "higher",
        "weight": 1.0,
        "description": "背景信息集中出现的位置（越靠后越好）",
    },
    "pacing_variation": {
        "name": "节奏变化",
        "category": "pacing",
        "direction": "higher",
        "weight": 1.0,
        "description": "节奏变化幅度",
    },

    # === 人物指标（5维） ===
    "protagonist_recognition": {
        "name": "主角辨识度",
        "category": "character",
        "direction": "higher",
        "weight": 2.0,
        "description": "主角在前500字的辨识度",
    },
    "character_count": {
        "name": "角色数量",
        "category": "character",
        "direction": "optimal",
        "weight": 0.8,
        "description": "出场角色数量",
    },
    "dialogue_quality": {
        "name": "对话质量",
        "category": "character",
        "direction": "higher",
        "weight": 1.5,
        "description": "对话个性化程度评分",
    },
    "character_balance": {
        "name": "角色出场平衡",
        "category": "character",
        "direction": "optimal",
        "weight": 0.5,
        "description": "角色出场次数平衡度",
    },
    "protagonist_action_ratio": {
        "name": "主角主动行为比例",
        "category": "character",
        "direction": "higher",
        "weight": 1.2,
        "description": "主角主动行动占比",
    },

    # === 情感指标（5维） ===
    "emotion_intensity": {
        "name": "情感强度",
        "category": "emotion",
        "direction": "higher",
        "weight": 1.5,
        "description": "情感强度评分",
    },
    "emotion_valence": {
        "name": "情感价",
        "category": "emotion",
        "direction": "optimal",
        "weight": 1.0,
        "description": "积极/消极情感比例",
    },
    "emotion_variation": {
        "name": "情感波动",
        "category": "emotion",
        "direction": "higher",
        "weight": 1.2,
        "description": "情感波动幅度",
    },
    "empathy_moment_count": {
        "name": "共情时刻数量",
        "category": "emotion",
        "direction": "higher",
        "weight": 1.8,
        "description": "读者共情时刻数量",
    },
    "ending_emotion": {
        "name": "章末情绪",
        "category": "emotion",
        "direction": "higher",
        "weight": 1.5,
        "description": "章末情绪状态（越积极/越有悬念越好）",
    },

    # === 其他指标（7维） ===
    "title_attractiveness": {
        "name": "标题吸引力",
        "category": "other",
        "direction": "higher",
        "weight": 1.0,
        "description": "标题吸引力评分",
    },
    "punctuation_diversity": {
        "name": "标点多样性",
        "category": "other",
        "direction": "higher",
        "weight": 0.5,
        "description": "标点符号种类丰富度",
    },
    "vocabulary_richness": {
        "name": "词汇丰富度",
        "category": "other",
        "direction": "higher",
        "weight": 0.8,
        "description": "词汇丰富度（type-token ratio）",
    },
    "exclamation_ratio": {
        "name": "感叹号比例",
        "category": "other",
        "direction": "optimal",
        "weight": 0.8,
        "description": "每千字感叹号数量",
    },
    "question_ratio": {
        "name": "问号比例",
        "category": "other",
        "direction": "higher",
        "weight": 0.6,
        "description": "每千字问号数量（悬念感）",
    },
    "chapter_length_variation": {
        "name": "章节长度变异",
        "category": "other",
        "direction": "lower",
        "weight": 0.3,
        "description": "章节长度变异系数",
    },
    "readability_score": {
        "name": "可读性评分",
        "category": "other",
        "direction": "higher",
        "weight": 1.0,
        "description": "综合可读性评分",
    },
}

# 验证：40维
assert len(FEATURE_DEFINITIONS) == 40, f"特征维度数量错误：{len(FEATURE_DEFINITIONS)}，应为40"


# ============================================================
# 品类基准值
# ============================================================

# 番茄爽文基准值
TOMATO_BASELINE = {
    # 章节基础
    "word_count": 3000,
    "paragraph_count": 50,
    "dialogue_ratio": 0.35,
    "short_sentence_ratio": 0.6,
    "avg_paragraph_length": 60,

    # AI味
    "le_word_density": 25.0,
    "transition_word_density": 5.0,
    "abstract_adverb_density": 2.0,
    "summary_sentence_density": 3.0,
    "paragraph_opening_repeat": 0.15,
    "dialogue_omit_ratio": 0.30,
    "paragraph_rhythm_cv": 0.30,

    # 爽点
    "payoff_density": 1.5,
    "payoff_intensity_avg": 7.0,
    "payoff_type_diversity": 3,
    "first_payoff_position": 500,
    "payoff_climax_count": 1,

    # 节奏
    "info_density": 0.6,
    "opening_hook_score": 7.0,
    "ending_hook_score": 7.5,
    "conflict_density": 2.0,
    "info_dump_position": 1000,
    "pacing_variation": 0.4,

    # 人物
    "protagonist_recognition": 7.0,
    "character_count": 5,
    "dialogue_quality": 6.0,
    "character_balance": 0.6,
    "protagonist_action_ratio": 0.6,

    # 情感
    "emotion_intensity": 6.5,
    "emotion_valence": 0.3,
    "emotion_variation": 0.5,
    "empathy_moment_count": 2,
    "ending_emotion": 7.0,

    # 其他
    "title_attractiveness": 7.0,
    "punctuation_diversity": 6,
    "vocabulary_richness": 0.4,
    "exclamation_ratio": 8.0,
    "question_ratio": 3.0,
    "chapter_length_variation": 0.1,
    "readability_score": 7.5,
}

# 起点玄幻基准值
QIDIAN_BASELINE = {
    # 章节基础
    "word_count": 4000,
    "paragraph_count": 40,
    "dialogue_ratio": 0.25,
    "short_sentence_ratio": 0.4,
    "avg_paragraph_length": 100,

    # AI味
    "le_word_density": 40.0,
    "transition_word_density": 8.0,
    "abstract_adverb_density": 3.0,
    "summary_sentence_density": 5.0,
    "paragraph_opening_repeat": 0.20,
    "dialogue_omit_ratio": 0.20,
    "paragraph_rhythm_cv": 0.25,

    # 爽点
    "payoff_density": 1.0,
    "payoff_intensity_avg": 6.5,
    "payoff_type_diversity": 4,
    "first_payoff_position": 1000,
    "payoff_climax_count": 1,

    # 节奏
    "info_density": 0.7,
    "opening_hook_score": 6.0,
    "ending_hook_score": 7.0,
    "conflict_density": 1.5,
    "info_dump_position": 500,
    "pacing_variation": 0.3,

    # 人物
    "protagonist_recognition": 6.5,
    "character_count": 8,
    "dialogue_quality": 6.5,
    "character_balance": 0.5,
    "protagonist_action_ratio": 0.5,

    # 情感
    "emotion_intensity": 6.0,
    "emotion_valence": 0.2,
    "emotion_variation": 0.4,
    "empathy_moment_count": 1,
    "ending_emotion": 6.5,

    # 其他
    "title_attractiveness": 6.5,
    "punctuation_diversity": 7,
    "vocabulary_richness": 0.5,
    "exclamation_ratio": 5.0,
    "question_ratio": 2.0,
    "chapter_length_variation": 0.15,
    "readability_score": 7.0,
}

# 晋江言情基准值
JJWXC_BASELINE = {
    # 章节基础
    "word_count": 3500,
    "paragraph_count": 45,
    "dialogue_ratio": 0.40,
    "short_sentence_ratio": 0.5,
    "avg_paragraph_length": 80,

    # AI味
    "le_word_density": 30.0,
    "transition_word_density": 6.0,
    "abstract_adverb_density": 2.5,
    "summary_sentence_density": 4.0,
    "paragraph_opening_repeat": 0.15,
    "dialogue_omit_ratio": 0.25,
    "paragraph_rhythm_cv": 0.28,

    # 爽点
    "payoff_density": 0.8,
    "payoff_intensity_avg": 6.0,
    "payoff_type_diversity": 2,
    "first_payoff_position": 1500,
    "payoff_climax_count": 1,

    # 节奏
    "info_density": 0.5,
    "opening_hook_score": 6.5,
    "ending_hook_score": 7.0,
    "conflict_density": 1.0,
    "info_dump_position": 800,
    "pacing_variation": 0.35,

    # 人物
    "protagonist_recognition": 7.5,
    "character_count": 6,
    "dialogue_quality": 8.0,
    "character_balance": 0.7,
    "protagonist_action_ratio": 0.55,

    # 情感
    "emotion_intensity": 7.5,
    "emotion_valence": 0.4,
    "emotion_variation": 0.6,
    "empathy_moment_count": 3,
    "ending_emotion": 7.5,

    # 其他
    "title_attractiveness": 7.5,
    "punctuation_diversity": 6,
    "vocabulary_richness": 0.45,
    "exclamation_ratio": 6.0,
    "question_ratio": 4.0,
    "chapter_length_variation": 0.12,
    "readability_score": 8.0,
}

# 通用基准值（平均值）
DEFAULT_BASELINE = {
    key: (TOMATO_BASELINE[key] + QIDIAN_BASELINE[key] + JJWXC_BASELINE[key]) / 3
    for key in FEATURE_DEFINITIONS.keys()
}

# 基准值映射
BASELINE_MAP = {
    "fanqie": TOMATO_BASELINE,
    "tomato": TOMATO_BASELINE,
    "qidian": QIDIAN_BASELINE,
    "jjwxc": JJWXC_BASELINE,
    "default": DEFAULT_BASELINE,
}

# 基础留存率（品类基准）
BASE_RETENTION = {
    "fanqie": 65.0,
    "tomato": 65.0,
    "qidian": 60.0,
    "jjwxc": 62.0,
    "default": 60.0,
}


# ============================================================
# 数据结构
# ============================================================

@dataclass
class DragFactor:
    """拖累因素。"""
    feature_key: str
    feature_name: str
    category: str
    actual_value: float
    baseline_value: float
    deviation: float  # 偏离程度（百分比）
    impact: float  # 对留存的影响（扣分，负数）
    weight: float
    suggestion: str


@dataclass
class RetentionPrediction:
    """留存预测结果。"""
    predicted_retention: float  # 预测留存率 0-100
    base_retention: float  # 基础留存率
    total_adjustment: float  # 总调整量
    feature_count: int  # 特征数量
    platform: str  # 平台/品类
    top_drag_factors: List[DragFactor] = field(default_factory=list)  # 前N名拖累因素
    top_boost_factors: List[DragFactor] = field(default_factory=list)  # 前N名加分因素
    category_scores: Dict[str, float] = field(default_factory=dict)  # 各分类得分
    suggestions: List[str] = field(default_factory=list)  # 改进建议
    confidence: float = 0.7  # 预测置信度


# ============================================================
# 核心预测算法
# ============================================================

def predict_retention(
    features: Dict[str, float],
    platform: str = "default",
    top_n: int = 3,
) -> RetentionPrediction:
    """
    预测读者留存率。

    Args:
        features: 40维特征字典
        platform: 平台/品类（fanqie/qidian/jjwxc/default）
        top_n: 返回前N名拖累/加分因素

    Returns:
        RetentionPrediction 预测结果
    """
    # 获取基准值
    baseline = BASELINE_MAP.get(platform, DEFAULT_BASELINE)
    base_retention = BASE_RETENTION.get(platform, 60.0)

    # 计算每个特征的影响
    drag_factors = []
    boost_factors = []
    category_impacts = {}  # 各分类的总影响

    for feature_key, feature_def in FEATURE_DEFINITIONS.items():
        if feature_key not in features:
            continue

        actual = features[feature_key]
        base = baseline.get(feature_key, actual)
        weight = feature_def["weight"]
        direction = feature_def["direction"]
        category = feature_def["category"]

        # 计算偏离程度和影响
        impact, deviation_pct = _calculate_impact(
            actual, base, direction, weight
        )

        # 创建因素对象
        factor = DragFactor(
            feature_key=feature_key,
            feature_name=feature_def["name"],
            category=category,
            actual_value=round(actual, 2),
            baseline_value=round(base, 2),
            deviation=round(deviation_pct, 1),
            impact=round(impact, 2),
            weight=weight,
            suggestion=_generate_suggestion(feature_key, actual, base, direction),
        )

        if impact < 0:
            drag_factors.append(factor)
        elif impact > 0:
            boost_factors.append(factor)

        # 累加分类影响
        if category not in category_impacts:
            category_impacts[category] = 0.0
        category_impacts[category] += impact

    # 计算总调整量
    total_adjustment = sum(f.impact for f in drag_factors + boost_factors)

    # 计算最终预测留存率
    predicted_retention = base_retention + total_adjustment
    predicted_retention = max(0.0, min(100.0, predicted_retention))

    # 排序
    drag_factors.sort(key=lambda x: x.impact)  # 按影响从小到大（最严重的在前）
    boost_factors.sort(key=lambda x: x.impact, reverse=True)  # 按影响从大到小

    # 分类得分（转换为0-100分）
    category_scores = {}
    for category, impact in category_impacts.items():
        # 简单转换：基准50分，每1分影响对应5分
        score = 50 + impact * 5
        score = max(0, min(100, score))
        category_scores[category] = round(score, 1)

    # 生成改进建议
    suggestions = _generate_improvement_suggestions(
        drag_factors[:top_n],
        platform,
        predicted_retention,
    )

    # 计算置信度
    available_features = len([k for k in FEATURE_DEFINITIONS if k in features])
    confidence = min(0.95, 0.5 + (available_features / 40) * 0.45)

    return RetentionPrediction(
        predicted_retention=round(predicted_retention, 1),
        base_retention=base_retention,
        total_adjustment=round(total_adjustment, 1),
        feature_count=available_features,
        platform=platform,
        top_drag_factors=drag_factors[:top_n],
        top_boost_factors=boost_factors[:top_n],
        category_scores=category_scores,
        suggestions=suggestions,
        confidence=round(confidence, 2),
    )


def _calculate_impact(
    actual: float,
    baseline: float,
    direction: str,
    weight: float,
) -> Tuple[float, float]:
    """
    计算单个特征对留存的影响。

    Returns:
        (impact, deviation_pct)
        impact: 对留存的影响（正数=加分，负数=扣分）
        deviation_pct: 偏离百分比
    """
    if baseline == 0:
        return 0.0, 0.0

    # 计算偏离百分比
    deviation_pct = ((actual - baseline) / baseline) * 100

    if direction == "higher":
        # 越高越好
        # 每偏离10%，影响 = weight * 0.5（非线性）
        ratio = actual / baseline if baseline > 0 else 1.0
        if ratio >= 1.0:
            # 加分：边际递减
            impact = weight * min(3.0, (ratio - 1.0) * 2)
        else:
            # 扣分：加速下降
            impact = -weight * min(5.0, (1.0 - ratio) * 3)

    elif direction == "lower":
        # 越低越好
        ratio = actual / baseline if baseline > 0 else 1.0
        if ratio <= 1.0:
            # 加分
            impact = weight * min(2.0, (1.0 - ratio) * 2)
        else:
            # 扣分
            impact = -weight * min(5.0, (ratio - 1.0) * 3)

    else:  # optimal
        # 有最优区间
        # 假设最优区间为基准值的 ±20%
        ratio = actual / baseline if baseline > 0 else 1.0
        if 0.8 <= ratio <= 1.2:
            # 在最优区间内，满分
            impact = weight * 1.0
        elif ratio < 0.8:
            # 低于最优区间
            impact = -weight * min(3.0, (0.8 - ratio) * 5)
        else:  # ratio > 1.2
            # 高于最优区间
            impact = -weight * min(3.0, (ratio - 1.2) * 5)

    return impact, deviation_pct


def _generate_suggestion(
    feature_key: str,
    actual: float,
    baseline: float,
    direction: str,
) -> str:
    """生成单个特征的改进建议。"""
    feature_def = FEATURE_DEFINITIONS.get(feature_key, {})
    name = feature_def.get("name", feature_key)

    if direction == "higher":
        if actual < baseline:
            gap = baseline - actual
            return f"{name}偏低（{actual:.1f} < {baseline:.1f}），建议提升约{gap:.1f}"
        else:
            return f"{name}表现良好（{actual:.1f} > {baseline:.1f}）"

    elif direction == "lower":
        if actual > baseline:
            gap = actual - baseline
            return f"{name}偏高（{actual:.1f} > {baseline:.1f}），建议降低约{gap:.1f}"
        else:
            return f"{name}表现良好（{actual:.1f} < {baseline:.1f}）"

    else:  # optimal
        ratio = actual / baseline if baseline > 0 else 1.0
        if 0.8 <= ratio <= 1.2:
            return f"{name}在最优区间内（{actual:.1f}）"
        elif ratio < 0.8:
            return f"{name}偏低（{actual:.1f}），建议提升到约{baseline:.1f}"
        else:
            return f"{name}偏高（{actual:.1f}），建议降低到约{baseline:.1f}"


def _generate_improvement_suggestions(
    top_drags: List[DragFactor],
    platform: str,
    predicted_retention: float,
) -> List[str]:
    """生成改进建议列表。"""
    suggestions = []

    # 总体评价
    if predicted_retention >= 80:
        suggestions.append(f"预测留存率 {predicted_retention:.1f}%，表现优秀，继续保持！")
    elif predicted_retention >= 65:
        suggestions.append(f"预测留存率 {predicted_retention:.1f}%，表现良好，仍有提升空间")
    elif predicted_retention >= 50:
        suggestions.append(f"预测留存率 {predicted_retention:.1f}%，表现一般，建议重点优化")
    else:
        suggestions.append(f"预测留存率 {predicted_retention:.1f}%，表现较差，急需改进")

    # 前3名拖累因素的具体建议
    for i, drag in enumerate(top_drags[:3], 1):
        suggestions.append(f"拖累因素{i}：{drag.feature_name}（影响 {drag.impact:+.1f}%）- {drag.suggestion}")

    # 分类建议
    categories = set(d.category for d in top_drags)
    if "payoff" in categories:
        suggestions.append("爽点是影响留存的最关键因素，建议优先提升爽点密度和强度")
    if "pacing" in categories:
        suggestions.append("节奏问题直接影响追读意愿，建议优化开篇钩子和章末钩子")
    if "ai_smell" in categories:
        suggestions.append("AI味过重会让读者出戏，建议降低AI味指标，增加自然感")
    if "character" in categories:
        suggestions.append("人物立不住会让读者没有代入感，建议加强主角辨识度和对话质量")
    if "emotion" in categories:
        suggestions.append("情感共鸣是留存的核心，建议增加共情时刻，提升情感波动")

    return suggestions


# ============================================================
# 便捷函数
# ============================================================

def get_feature_list() -> List[Dict]:
    """获取所有特征定义列表。"""
    return [
        {"key": k, "name": v["name"], "category": v["category"], "weight": v["weight"]}
        for k, v in FEATURE_DEFINITIONS.items()
    ]


def get_baseline(platform: str = "default") -> Dict[str, float]:
    """获取指定平台的基准值。"""
    return BASELINE_MAP.get(platform, DEFAULT_BASELINE).copy()


def get_retention_level(retention: float) -> str:
    """获取留存率等级。"""
    if retention >= 85:
        return "S级（优秀）"
    elif retention >= 75:
        return "A级（良好）"
    elif retention >= 65:
        return "B级（一般）"
    elif retention >= 50:
        return "C级（较差）"
    else:
        return "D级（危险）"


def compare_with_baseline(
    features: Dict[str, float],
    platform: str = "default",
) -> Dict[str, Dict]:
    """
    对比特征值与基准值。

    Returns:
        {feature_key: {actual, baseline, deviation, status}}
    """
    baseline = get_baseline(platform)
    result = {}

    for key, actual in features.items():
        base = baseline.get(key, actual)
        if base == 0:
            deviation = 0
        else:
            deviation = ((actual - base) / base) * 100

        feature_def = FEATURE_DEFINITIONS.get(key, {})
        direction = feature_def.get("direction", "higher")

        # 判断状态
        if direction == "higher":
            if deviation >= 10:
                status = "excellent"
            elif deviation >= -10:
                status = "good"
            elif deviation >= -30:
                status = "average"
            else:
                status = "poor"
        elif direction == "lower":
            if deviation <= -10:
                status = "excellent"
            elif deviation <= 10:
                status = "good"
            elif deviation <= 30:
                status = "average"
            else:
                status = "poor"
        else:  # optimal
            if abs(deviation) <= 10:
                status = "excellent"
            elif abs(deviation) <= 20:
                status = "good"
            elif abs(deviation) <= 40:
                status = "average"
            else:
                status = "poor"

        result[key] = {
            "actual": round(actual, 2),
            "baseline": round(base, 2),
            "deviation": round(deviation, 1),
            "status": status,
        }

    return result
