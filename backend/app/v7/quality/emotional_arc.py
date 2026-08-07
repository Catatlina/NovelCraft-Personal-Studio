"""
情感弧线映射模块

功能：
1. 每章情感强度评分（1-10分）
2. 全卷情感曲线数据
3. 异常检测（疲劳/平淡、突兀、压抑）
4. 基于词频/情绪词典的规则评分，零AI调用

使用方式：
    from app.v7.quality.emotional_arc import analyze_emotional_arc, analyze_chapter_emotion

    # 单章分析
    result = analyze_chapter_emotion(text)
    print(result.score)  # 情感强度评分 1-10

    # 多章情感弧线
    chapters = [text1, text2, text3, ...]
    arc = analyze_emotional_arc(chapters)
    print(arc.scores)  # 每章评分列表
    print(arc.anomalies)  # 异常列表
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


# ============================================================
# 情绪词典
# ============================================================

# 积极情绪词（+分）
POSITIVE_WORDS = [
    # 基础积极
    "开心", "高兴", "喜悦", "兴奋", "激动", "快乐", "愉快", "舒畅",
    "幸福", "满足", "欣慰", "安心", "放心", "踏实", "温暖",
    # 成就类
    "成功", "胜利", "突破", "超越", "崛起", "逆袭", "翻盘",
    "获得", "得到", "拥有", "实现", "达成", "完成", "收获",
    "骄傲", "自豪", "自信", "威风", "风光", "荣耀", "荣誉",
    # 爽感类
    "打脸", "装逼", "爽", "厉害", "强大", "无敌", "至尊", "巅峰",
    "王者", "霸主", "传奇", "神话", "绝世", "盖世", "惊天", "动地",
    # 正面评价
    "好", "棒", "赞", "牛", "强", "优秀", "出色", "卓越",
    "精彩", "完美", "绝妙", "惊艳", "震撼", "叹服", "佩服",
    # 关系积极
    "喜欢", "爱", "感激", "感谢", "欣赏", "认可", "赞同", "支持",
    "信任", "依赖", "陪伴", "守护", "保护", "珍惜", "珍贵",
]

# 消极情绪词（-分）
NEGATIVE_WORDS = [
    # 基础消极
    "难过", "伤心", "悲伤", "痛苦", "绝望", "沮丧", "失落", "低落",
    "愤怒", "生气", "暴怒", "怒吼", "咆哮", "咬牙", "切齿",
    "恐惧", "害怕", "惊恐", "恐慌", "畏惧", "胆怯", "恐惧",
    "担忧", "焦虑", "紧张", "不安", "烦躁", "郁闷", "憋屈",
    # 失败挫折
    "失败", "挫折", "困难", "危机", "危险", "威胁", "险境",
    "失去", "损失", "牺牲", "放弃", "认输", "投降", "败北",
    "委屈", "冤枉", "受气", "被欺负", "被打压", "被陷害",
    # 背叛欺骗
    "背叛", "欺骗", "谎言", "阴谋", "诡计", "陷阱", "圈套",
    "阴险", "狡诈", "狠毒", "残忍", "残酷", "无情", "冷血",
    # 痛苦折磨
    "折磨", "煎熬", "痛苦", "剧痛", "伤痛", "伤痕", "伤疤",
    "疲惫", "虚弱", "无力", "绝望", "崩溃", "疯狂", "失控",
]

# 强度修饰词（放大效果）
INTENSIFIERS = {
    # 强强度（x2.0）
    "非常": 2.0, "极其": 2.0, "无比": 2.0, "极度": 2.0,
    "万分": 2.0, "十分": 2.0, "特别": 2.0, "超级": 2.0,
    "最": 2.0, "太": 2.0, "真": 1.8, "好": 1.5,
    # 中强度（x1.5）
    "很": 1.5, "挺": 1.3, "蛮": 1.3, "相当": 1.4,
    "格外": 1.4, "分外": 1.4, "更加": 1.3, "越发": 1.3,
    # 弱强度（x0.7）
    "有点": 0.7, "稍微": 0.7, "略微": 0.7, "轻轻": 0.6,
    "淡淡": 0.6, "微微": 0.6, "稍稍": 0.7,
}

# 情绪反转词（反转正负）
NEGATION_WORDS = [
    "不", "没", "无", "非", "未", "别", "莫", "勿",
    "不是", "没有", "不会", "不能", "不可", "不要",
]


# ============================================================
# 数据结构
# ============================================================

@dataclass
class ChapterEmotionResult:
    """单章情感分析结果。"""
    score: float  # 情感强度评分 1-10
    valence: float  # 情感价（-1到1，正=积极，负=消极）
    arousal: float  # 唤醒度（0到1，越高越强烈）
    emotion_type: str  # 主导情绪类型
    positive_count: int  # 积极词数量
    negative_count: int  # 消极词数量
    intensity_count: int  # 强度词数量
    exclamation_ratio: float  # 感叹号比例（每千字）
    question_ratio: float  # 问号比例（每千字）
    word_count: int  # 总字数
    top_emotions: List[Tuple[str, float]] = field(default_factory=list)  # 前3种情绪


@dataclass
class EmotionalArcResult:
    """情感弧线分析结果。"""
    scores: List[float]  # 每章情感强度评分
    valences: List[float]  # 每章情感价
    arousals: List[float]  # 每章唤醒度
    overall_score: float  # 整体情感强度
    arc_type: str  # 弧线类型（上升型/下降型/波浪型/平淡型）
    peak_chapter: int  # 最高峰章节
    valley_chapter: int  # 最低谷章节
    volatility: float  # 波动幅度（标准差）
    anomalies: List[Dict]  # 异常列表
    suggestions: List[str]  # 改进建议
    chapter_count: int  # 章节数量


# ============================================================
# 单章情感分析
# ============================================================

def analyze_chapter_emotion(text: str) -> ChapterEmotionResult:
    """
    分析单章情感强度。

    Args:
        text: 章节文本

    Returns:
        ChapterEmotionResult 情感分析结果
    """
    if not text or len(text.strip()) == 0:
        return ChapterEmotionResult(
            score=5.0,
            valence=0.0,
            arousal=0.0,
            emotion_type="neutral",
            positive_count=0,
            negative_count=0,
            intensity_count=0,
            exclamation_ratio=0.0,
            question_ratio=0.0,
            word_count=0,
            top_emotions=[],
        )

    text = text.strip()
    word_count = len(text)

    # 统计积极词和消极词
    positive_count = 0
    negative_count = 0
    intensity_count = 0

    # 检测积极词
    for word in POSITIVE_WORDS:
        count = text.count(word)
        if count > 0:
            # 检查前面是否有否定词
            # 简单处理：如果词前面3个字内有否定词，反转
            positions = [m.start() for m in re.finditer(re.escape(word), text)]
            actual_count = 0
            for pos in positions:
                # 检查前面是否有否定词
                prefix = text[max(0, pos - 3):pos]
                has_negation = any(neg in prefix for neg in NEGATION_WORDS)
                if not has_negation:
                    actual_count += 1
                else:
                    negative_count += 1  # 否定+积极 = 消极
            positive_count += actual_count

    # 检测消极词
    for word in NEGATIVE_WORDS:
        count = text.count(word)
        if count > 0:
            # 检查前面是否有否定词
            positions = [m.start() for m in re.finditer(re.escape(word), text)]
            actual_count = 0
            for pos in positions:
                prefix = text[max(0, pos - 3):pos]
                has_negation = any(neg in prefix for neg in NEGATION_WORDS)
                if not has_negation:
                    actual_count += 1
                else:
                    positive_count += 1  # 否定+消极 = 积极
            negative_count += actual_count

    # 检测强度词（简化处理，只统计数量）
    for word in INTENSIFIERS:
        intensity_count += text.count(word)

    # 统计标点符号
    exclamation_count = text.count("！") + text.count("!")
    question_count = text.count("？") + text.count("?")

    exclamation_ratio = exclamation_count / (word_count / 1000) if word_count > 0 else 0
    question_ratio = question_count / (word_count / 1000) if word_count > 0 else 0

    # 计算情感价（valence）：-1 到 1
    total_emotion_words = positive_count + negative_count
    if total_emotion_words > 0:
        valence = (positive_count - negative_count) / total_emotion_words
    else:
        valence = 0.0

    # 计算唤醒度（arousal）：0 到 1
    # 基于情绪词密度、强度词、感叹号
    emotion_density = total_emotion_words / (word_count / 1000) if word_count > 0 else 0
    intensity_factor = 1.0 + (intensity_count / max(total_emotion_words, 1)) * 0.5
    exclamation_factor = 1.0 + min(exclamation_ratio, 10) * 0.05

    arousal = min(1.0, emotion_density * 0.1 * intensity_factor * exclamation_factor)

    # 计算情感强度评分（1-10分）
    # 基础分5分，根据唤醒度和情感价调整
    base_score = 5.0
    arousal_contribution = arousal * 3.0  # 唤醒度最多贡献3分
    valence_contribution = valence * 2.0  # 情感价贡献±2分

    score = base_score + arousal_contribution + valence_contribution
    score = max(1.0, min(10.0, score))

    # 判断主导情绪类型
    if valence > 0.3 and arousal > 0.3:
        emotion_type = "excited"  # 兴奋/激动
    elif valence > 0.3 and arousal <= 0.3:
        emotion_type = "peaceful"  # 平静/温馨
    elif valence < -0.3 and arousal > 0.3:
        emotion_type = "angry"  # 愤怒/紧张
    elif valence < -0.3 and arousal <= 0.3:
        emotion_type = "sad"  # 悲伤/低落
    else:
        emotion_type = "neutral"  # 中性

    # 前3种情绪（简化版，基于关键词统计）
    top_emotions = []
    if positive_count > 0:
        top_emotions.append(("positive", positive_count / max(total_emotion_words, 1)))
    if negative_count > 0:
        top_emotions.append(("negative", negative_count / max(total_emotion_words, 1)))
    if exclamation_count > 0:
        top_emotions.append(("intense", min(1.0, exclamation_ratio / 10)))

    return ChapterEmotionResult(
        score=round(score, 1),
        valence=round(valence, 2),
        arousal=round(arousal, 2),
        emotion_type=emotion_type,
        positive_count=positive_count,
        negative_count=negative_count,
        intensity_count=intensity_count,
        exclamation_ratio=round(exclamation_ratio, 1),
        question_ratio=round(question_ratio, 1),
        word_count=word_count,
        top_emotions=top_emotions[:3],
    )


# ============================================================
# 情感弧线分析
# ============================================================

def analyze_emotional_arc(chapters: List[str]) -> EmotionalArcResult:
    """
    分析多章情感弧线。

    Args:
        chapters: 章节文本列表

    Returns:
        EmotionalArcResult 情感弧线分析结果
    """
    if not chapters:
        return EmotionalArcResult(
            scores=[],
            valences=[],
            arousals=[],
            overall_score=5.0,
            arc_type="flat",
            peak_chapter=0,
            valley_chapter=0,
            volatility=0.0,
            anomalies=[],
            suggestions=["没有章节数据"],
            chapter_count=0,
        )

    # 逐章分析
    chapter_results = [analyze_chapter_emotion(ch) for ch in chapters]
    scores = [r.score for r in chapter_results]
    valences = [r.valence for r in chapter_results]
    arousals = [r.arousal for r in chapter_results]

    chapter_count = len(chapters)

    # 整体评分
    overall_score = sum(scores) / chapter_count if chapter_count > 0 else 5.0

    # 最高峰和最低谷
    peak_chapter = scores.index(max(scores)) + 1 if scores else 0
    valley_chapter = scores.index(min(scores)) + 1 if scores else 0

    # 波动幅度（标准差）
    if chapter_count > 1:
        mean = sum(scores) / chapter_count
        variance = sum((s - mean) ** 2 for s in scores) / chapter_count
        volatility = variance ** 0.5
    else:
        volatility = 0.0

    # 判断弧线类型
    if chapter_count < 3:
        arc_type = "insufficient"
    else:
        # 简单判断：看整体趋势
        first_third = sum(scores[:chapter_count // 3]) / (chapter_count // 3)
        last_third = sum(scores[-chapter_count // 3:]) / (chapter_count // 3)

        if last_third - first_third > 1.0:
            arc_type = "rising"  # 上升型
        elif first_third - last_third > 1.0:
            arc_type = "falling"  # 下降型
        elif volatility > 1.5:
            arc_type = "wave"  # 波浪型
        else:
            arc_type = "flat"  # 平淡型

    # 异常检测
    anomalies = _detect_anomalies(scores, chapter_count)

    # 生成改进建议
    suggestions = _generate_suggestions(scores, anomalies, arc_type, volatility)

    return EmotionalArcResult(
        scores=[round(s, 1) for s in scores],
        valences=[round(v, 2) for v in valences],
        arousals=[round(a, 2) for a in arousals],
        overall_score=round(overall_score, 1),
        arc_type=arc_type,
        peak_chapter=peak_chapter,
        valley_chapter=valley_chapter,
        volatility=round(volatility, 2),
        anomalies=anomalies,
        suggestions=suggestions,
        chapter_count=chapter_count,
    )


def _detect_anomalies(scores: List[float], chapter_count: int) -> List[Dict]:
    """
    检测情感弧线异常。

    异常类型：
    1. fatigue: 连续3章同一强度 → 疲劳/平淡
    2. abrupt: 高潮前无蓄力 → 突兀
    3. depression: 低谷后无回升 → 压抑
    """
    anomalies = []

    if chapter_count < 3:
        return anomalies

    # 1. 检测连续平淡（疲劳）
    i = 0
    while i < chapter_count - 2:
        if abs(scores[i] - scores[i + 1]) < 0.5 and abs(scores[i + 1] - scores[i + 2]) < 0.5:
            # 连续3章强度相近
            start_chapter = i + 1
            end_chapter = i + 2
            # 继续向后找
            j = i + 3
            while j < chapter_count and abs(scores[j] - scores[i]) < 0.5:
                end_chapter = j + 1
                j += 1

            anomalies.append({
                "type": "fatigue",
                "name": "情感疲劳/平淡",
                "severity": "medium" if (end_chapter - start_chapter + 1) >= 5 else "low",
                "start_chapter": start_chapter,
                "end_chapter": end_chapter,
                "description": f"第{start_chapter}-{end_chapter}章情感强度持续相近，读者可能感到疲劳",
                "suggestion": "建议在平淡段中加入小冲突或悬念，打破平淡节奏",
            })
            i = j
        else:
            i += 1

    # 2. 检测突兀高潮（高潮前无蓄力）
    for i in range(1, chapter_count):
        if scores[i] >= 8.0:  # 高潮
            # 检查前一章
            if i > 0 and scores[i] - scores[i - 1] > 3.0:
                anomalies.append({
                    "type": "abrupt",
                    "name": "高潮突兀",
                    "severity": "medium",
                    "chapter": i + 1,
                    "description": f"第{i+1}章高潮来得太突然，前一章（{scores[i-1]:.1f}分）与高潮（{scores[i]:.1f}分）差距过大",
                    "suggestion": "建议在高潮前增加铺垫和蓄力，让情绪逐步攀升",
                })

    # 3. 检测压抑低谷（低谷后无回升）
    for i in range(chapter_count):
        if scores[i] <= 3.0:  # 低谷
            # 检查后面2章
            if i + 2 < chapter_count:
                next_scores = scores[i + 1:i + 3]
                if all(s <= scores[i] + 1.0 for s in next_scores):
                    anomalies.append({
                        "type": "depression",
                        "name": "情绪压抑",
                        "severity": "high",
                        "chapter": i + 1,
                        "description": f"第{i+1}章低谷后，连续2章情绪未明显回升，可能让读者感到压抑",
                        "suggestion": "建议在低谷后尽快安排小反弹或希望点，避免读者弃书",
                    })

    return anomalies


def _generate_suggestions(
    scores: List[float],
    anomalies: List[Dict],
    arc_type: str,
    volatility: float,
) -> List[str]:
    """生成改进建议。"""
    suggestions = []

    chapter_count = len(scores)

    # 弧线类型建议
    if arc_type == "flat":
        suggestions.append("整体情感弧线偏平淡，建议增加情绪波动，让节奏更有起伏")
    elif arc_type == "falling":
        suggestions.append("情感弧线呈下降趋势，注意后期是否过于压抑，建议安排反弹")
    elif arc_type == "rising":
        suggestions.append("情感弧线呈上升趋势，节奏不错，注意保持后期不要崩盘")

    # 波动建议
    if volatility < 0.5:
        suggestions.append("情绪波动太小，建议增加冲突和转折，让读者情绪跟着起伏")
    elif volatility > 2.5:
        suggestions.append("情绪波动太大，建议增加过渡，避免读者情绪过山车")

    # 异常相关建议
    fatigue_count = sum(1 for a in anomalies if a["type"] == "fatigue")
    abrupt_count = sum(1 for a in anomalies if a["type"] == "abrupt")
    depression_count = sum(1 for a in anomalies if a["type"] == "depression")

    if fatigue_count > 0:
        suggestions.append(f"发现 {fatigue_count} 处情感平淡段，建议加入小高潮打破沉闷")

    if abrupt_count > 0:
        suggestions.append(f"发现 {abrupt_count} 处突兀高潮，建议增加铺垫让高潮更自然")

    if depression_count > 0:
        suggestions.append(f"发现 {depression_count} 处压抑低谷，建议尽快安排情绪反弹")

    # 首尾建议
    if chapter_count >= 2:
        if scores[0] < 5.0:
            suggestions.append("开篇情绪偏低，建议开篇就抓住读者，增加开篇吸引力")

        if scores[-1] < 6.0:
            suggestions.append("章末情绪偏低，建议章末留钩子，让读者想看下一章")

    return suggestions


# ============================================================
# 便捷函数
# ============================================================

def get_emotion_summary(result: ChapterEmotionResult) -> str:
    """获取情感分析摘要。"""
    emotion_names = {
        "excited": "兴奋激动",
        "peaceful": "平静温馨",
        "angry": "愤怒紧张",
        "sad": "悲伤低落",
        "neutral": "中性平稳",
    }

    name = emotion_names.get(result.emotion_type, "未知")
    return f"情感强度 {result.score}/10，{name}，积极词 {result.positive_count} 个，消极词 {result.negative_count} 个"


def get_arc_summary(result: EmotionalArcResult) -> str:
    """获取情感弧线摘要。"""
    arc_names = {
        "rising": "上升型",
        "falling": "下降型",
        "wave": "波浪型",
        "flat": "平淡型",
        "insufficient": "数据不足",
    }

    name = arc_names.get(result.arc_type, "未知")
    return (
        f"共 {result.chapter_count} 章，整体 {result.overall_score}/10 分，"
        f"{name}弧线，最高峰第 {result.peak_chapter} 章，"
        f"最低谷第 {result.valley_chapter} 章，波动 {result.volatility}"
    )
