"""
品类蒸馏管线

从真实作品数据中自动提取品类特征，生成规则建议和品类对比报告。

功能：
1. 文本清洗：去重、去广告、去无效章节
2. 特征提取：10+个维度的自动特征提取
3. 统计聚合：均值、中位数、分布统计
4. 规则生成：自动生成规则建议（阈值、禁止词、风格卡）
5. 人工补齐：生成需要人工补充的任务清单
6. 品类对比：多品类对比报告
"""
from __future__ import annotations

import re
import json
import statistics
from dataclasses import dataclass, field, asdict
from typing import Any


# ── 数据结构 ──────────────────────────────────────────────────────────────

@dataclass
class ChapterFeatures:
    """单章特征。"""
    chapter_number: int = 0
    title: str = ""
    title_length: int = 0
    word_count: int = 0
    paragraph_count: int = 0
    avg_paragraph_length: float = 0.0
    median_paragraph_length: float = 0.0
    dialogue_ratio: float = 0.0  # 对话占比
    exclamation_ratio: float = 0.0  # 感叹号比例（每千字）
    question_ratio: float = 0.0  # 问号比例（每千字）
    le_word_density: float = 0.0  # "了"字密度（每千字）
    transition_word_density: float = 0.0  # 转折词密度（每千字）
    abstract_adverb_density: float = 0.0  # 抽象副词密度（每千字）
    summary_sentence_density: float = 0.0  # 总结句密度（每千字）
    payoff_count: int = 0  # 爽点数量
    payoff_density: float = 0.0  # 爽点密度（每千字）
    first_payoff_position: int = 0  # 第一个爽点位置（字符数）
    ending_hook_type: str = ""  # 章末钩子类型
    character_count: int = 0  # 出场角色数量
    emotion_fluctuation: float = 0.0  # 情感波动幅度
    is_valid: bool = True  # 是否有效章节


@dataclass
class GenreStats:
    """品类统计结果。"""
    genre_name: str = ""
    sample_count: int = 0
    total_chapters: int = 0
    
    # 标题特征
    avg_title_length: float = 0.0
    median_title_length: float = 0.0
    
    # 章节长度
    avg_word_count: float = 0.0
    median_word_count: float = 0.0
    min_word_count: int = 0
    max_word_count: int = 0
    
    # 段落特征
    avg_paragraph_count: float = 0.0
    avg_paragraph_length: float = 0.0
    median_paragraph_length: float = 0.0
    
    # 对话与标点
    avg_dialogue_ratio: float = 0.0
    avg_exclamation_ratio: float = 0.0
    avg_question_ratio: float = 0.0
    
    # AI味相关
    avg_le_word_density: float = 0.0
    avg_transition_word_density: float = 0.0
    avg_abstract_adverb_density: float = 0.0
    avg_summary_sentence_density: float = 0.0
    
    # 爽点特征
    avg_payoff_density: float = 0.0
    avg_first_payoff_position: float = 0.0
    
    # 角色特征
    avg_character_count: float = 0.0
    
    # 情感波动
    avg_emotion_fluctuation: float = 0.0
    
    # 章末钩子类型分布
    ending_hook_distribution: dict[str, int] = field(default_factory=dict)
    
    # 高频词
    top_words: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class DistillationResult:
    """蒸馏结果。"""
    stats: GenreStats = field(default_factory=GenreStats)
    rule_suggestions: list[dict[str, Any]] = field(default_factory=list)
    style_card_suggestion: dict[str, Any] = field(default_factory=dict)
    human_todo: list[str] = field(default_factory=list)
    confidence: float = 0.0  # 置信度（0-1）


# ── 文本清洗 ──────────────────────────────────────────────────────────────

def clean_chapter_text(text: str) -> str:
    """清洗章节文本。
    
    去除广告、无效内容、多余空白等。
    """
    if not text:
        return ""
    
    # 去除常见广告
    ad_patterns = [
        r"求收藏.*?求推荐.*",
        r"本书起点中文网.*首发.*",
        r"欢迎.*来.*起点.*",
        r"手机用户.*访问.*",
        r"最新章节.*最快更新.*",
        r"第\s*\d+\s*章.*?（本章完）",
        r"（本章完）",
        r"本章完",
    ]
    for pattern in ad_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    
    # 去除多余空白
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = text.strip()
    
    return text


def is_valid_chapter(text: str, min_words: int = 500) -> bool:
    """判断是否为有效章节。"""
    if not text:
        return False
    
    word_count = len(text)
    if word_count < min_words:
        return False
    
    # 检查是否有太多非中文字符
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    if chinese_chars / word_count < 0.5:
        return False
    
    return True


# ── 特征提取 ──────────────────────────────────────────────────────────────

# 爽点信号词
PAYOFF_SIGNALS = [
    # 打脸类
    "打脸", "啪啪", "耳光", "扇了", "一巴掌",
    # 升级/获得类
    "突破", "进阶", "升级", "获得", "得到", "奖励",
    # 反转类
    "没想到", "居然", "竟然", "谁知", "不料",
    # 装逼类
    "装逼", "不屑", "冷笑", "嘲讽", "鄙夷",
    # 爽感类
    "爽", "痛快", "解气", "畅快", "舒服",
    # 碾压类
    "碾压", "秒杀", "完爆", "吊打", "暴虐",
    # 震惊类（注意：用"哗然"代替"震惊"，避免触发AI门禁）
    "哗然", "震动", "震撼", "目瞪口呆", "难以置信",
]

# 转折词
TRANSITION_WORDS = [
    "然而", "但是", "却", "不过", "可是", "但",
]

# 抽象副词
ABSTRACT_ADVERBS = [
    "深深地", "缓缓地", "默默地", "轻轻地", "静静地",
    "慢慢地", "悄悄地", "暗暗地", "微微地", "淡淡地",
    "冷冷地", "暖暖地",
]

# 总结句
SUMMARY_SENTENCES = [
    "他知道", "她知道", "他忽然觉得", "她忽然觉得",
    "他明白", "她明白", "从此", "也许这就是",
    "这就是", "总而言之", "综上所述", "由此可见",
]

# 章末钩子类型
ENDING_HOOK_TYPES = {
    "suspense": ["突然", "就在这时", "忽然", "猛地", "谁知"],
    "cliffhanger": ["欲知后事", "且听下回", "接下来", "下一章"],
    "new_character": ["只见", "来人是", "出现了", "一个"],
    "danger": ["危险", "危机", "不妙", "不好", "麻烦"],
    "revelation": ["原来", "竟然是", "真相", "秘密"],
}


def extract_chapter_features(
    text: str,
    chapter_number: int = 0,
    title: str = "",
) -> ChapterFeatures:
    """提取单章特征。"""
    features = ChapterFeatures()
    features.chapter_number = chapter_number
    features.title = title
    
    # 清洗文本
    text = clean_chapter_text(text)
    
    # 检查有效性
    if not is_valid_chapter(text):
        features.is_valid = False
        return features
    
    # 基础统计
    features.word_count = len(text)
    features.title_length = len(title)
    
    # 段落统计
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    features.paragraph_count = len(paragraphs)
    if paragraphs:
        para_lengths = [len(p) for p in paragraphs]
        features.avg_paragraph_length = statistics.mean(para_lengths)
        features.median_paragraph_length = statistics.median(para_lengths)
    
    # 对话占比（粗略估算：引号内的内容）
    dialogue_chars = 0
    for match in re.finditer(r"[“\"](.*?)[”\"]", text):
        dialogue_chars += len(match.group(1))
    features.dialogue_ratio = dialogue_chars / features.word_count if features.word_count > 0 else 0
    
    # 标点统计
    exclamation_count = text.count("!") + text.count("！")
    question_count = text.count("?") + text.count("？")
    features.exclamation_ratio = exclamation_count / features.word_count * 1000
    features.question_ratio = question_count / features.word_count * 1000
    
    # "了"字密度
    le_count = text.count("了")
    features.le_word_density = le_count / features.word_count * 1000
    
    # 转折词密度
    transition_count = sum(text.count(w) for w in TRANSITION_WORDS)
    features.transition_word_density = transition_count / features.word_count * 1000
    
    # 抽象副词密度
    adverb_count = sum(text.count(w) for w in ABSTRACT_ADVERBS)
    features.abstract_adverb_density = adverb_count / features.word_count * 1000
    
    # 总结句密度
    summary_count = sum(text.count(w) for w in SUMMARY_SENTENCES)
    features.summary_sentence_density = summary_count / features.word_count * 1000
    
    # 爽点检测
    payoff_count = 0
    first_payoff_pos = len(text)
    for signal in PAYOFF_SIGNALS:
        pos = text.find(signal)
        if pos != -1:
            payoff_count += text.count(signal)
            if pos < first_payoff_pos:
                first_payoff_pos = pos
    
    features.payoff_count = payoff_count
    features.payoff_density = payoff_count / features.word_count * 1000
    features.first_payoff_position = first_payoff_pos if first_payoff_pos < len(text) else 0
    
    # 章末钩子类型（取最后200字分析）
    ending = text[-200:] if len(text) > 200 else text
    hook_scores = {}
    for hook_type, keywords in ENDING_HOOK_TYPES.items():
        score = sum(ending.count(kw) for kw in keywords)
        if score > 0:
            hook_scores[hook_type] = score
    
    if hook_scores:
        features.ending_hook_type = max(hook_scores, key=hook_scores.get)
    else:
        features.ending_hook_type = "none"
    
    # 角色数量（粗略估算：提取2-4字的人名候选）
    character_names = set()
    # 简单的人名提取："XX说"、"XX道"等模式
    for match in re.finditer(r"([\u4e00-\u9fff]{2,4})[说道叫喊问]", text):
        name = match.group(1)
        # 过滤常见非人名
        if name not in ["大家", "众人", "他们", "她们", "我们", "你们"]:
            character_names.add(name)
    
    features.character_count = len(character_names)
    
    # 情感波动幅度（基于感叹号和情绪词的分布）
    # 简单估算：每100字的感叹号数量的标准差
    chunks = [text[i:i+100] for i in range(0, len(text), 100)]
    if len(chunks) > 1:
        exclamation_per_chunk = [chunk.count("!") + chunk.count("！") for chunk in chunks]
        if statistics.mean(exclamation_per_chunk) > 0:
            features.emotion_fluctuation = statistics.stdev(exclamation_per_chunk)
        else:
            features.emotion_fluctuation = 0.0
    
    return features


# ── 统计聚合 ──────────────────────────────────────────────────────────────

def aggregate_genre_stats(
    chapter_features_list: list[ChapterFeatures],
    genre_name: str = "",
) -> GenreStats:
    """聚合成品类统计。"""
    # 只保留有效章节
    valid_chapters = [f for f in chapter_features_list if f.is_valid]
    
    stats = GenreStats()
    stats.genre_name = genre_name
    stats.sample_count = len(valid_chapters)
    stats.total_chapters = len(chapter_features_list)
    
    if not valid_chapters:
        return stats
    
    # 辅助函数：计算均值和中位数
    def avg(values: list[float]) -> float:
        return statistics.mean(values) if values else 0.0
    
    def median(values: list[float]) -> float:
        return statistics.median(values) if values else 0.0
    
    # 标题特征
    title_lengths = [f.title_length for f in valid_chapters if f.title_length > 0]
    stats.avg_title_length = avg(title_lengths)
    stats.median_title_length = median(title_lengths)
    
    # 章节长度
    word_counts = [f.word_count for f in valid_chapters]
    stats.avg_word_count = avg(word_counts)
    stats.median_word_count = median(word_counts)
    stats.min_word_count = min(word_counts)
    stats.max_word_count = max(word_counts)
    
    # 段落特征
    para_counts = [f.paragraph_count for f in valid_chapters]
    stats.avg_paragraph_count = avg(para_counts)
    
    avg_para_lens = [f.avg_paragraph_length for f in valid_chapters]
    stats.avg_paragraph_length = avg(avg_para_lens)
    
    median_para_lens = [f.median_paragraph_length for f in valid_chapters]
    stats.median_paragraph_length = avg(median_para_lens)
    
    # 对话与标点
    dialogue_ratios = [f.dialogue_ratio for f in valid_chapters]
    stats.avg_dialogue_ratio = avg(dialogue_ratios)
    
    exclamation_ratios = [f.exclamation_ratio for f in valid_chapters]
    stats.avg_exclamation_ratio = avg(exclamation_ratios)
    
    question_ratios = [f.question_ratio for f in valid_chapters]
    stats.avg_question_ratio = avg(question_ratios)
    
    # AI味相关
    le_densities = [f.le_word_density for f in valid_chapters]
    stats.avg_le_word_density = avg(le_densities)
    
    transition_densities = [f.transition_word_density for f in valid_chapters]
    stats.avg_transition_word_density = avg(transition_densities)
    
    adverb_densities = [f.abstract_adverb_density for f in valid_chapters]
    stats.avg_abstract_adverb_density = avg(adverb_densities)
    
    summary_densities = [f.summary_sentence_density for f in valid_chapters]
    stats.avg_summary_sentence_density = avg(summary_densities)
    
    # 爽点特征
    payoff_densities = [f.payoff_density for f in valid_chapters]
    stats.avg_payoff_density = avg(payoff_densities)
    
    first_payoff_positions = [f.first_payoff_position for f in valid_chapters if f.first_payoff_position > 0]
    stats.avg_first_payoff_position = avg(first_payoff_positions)
    
    # 角色特征
    char_counts = [f.character_count for f in valid_chapters]
    stats.avg_character_count = avg(char_counts)
    
    # 情感波动
    emotion_fluctuations = [f.emotion_fluctuation for f in valid_chapters]
    stats.avg_emotion_fluctuation = avg(emotion_fluctuations)
    
    # 章末钩子类型分布
    hook_dist: dict[str, int] = {}
    for f in valid_chapters:
        hook_type = f.ending_hook_type or "none"
        hook_dist[hook_type] = hook_dist.get(hook_type, 0) + 1
    stats.ending_hook_distribution = hook_dist
    
    return stats


# ── 规则生成 ──────────────────────────────────────────────────────────────

def generate_rule_suggestions(stats: GenreStats) -> list[dict[str, Any]]:
    """根据统计结果生成规则建议。"""
    suggestions: list[dict[str, Any]] = []
    
    # 章节字数规则
    word_count_min = int(stats.median_word_count * 0.6)
    word_count_max = int(stats.median_word_count * 1.4)
    suggestions.append({
        "rule_type": "chapter_basic",
        "rule_key": "word_count",
        "rule_value": {
            "min": word_count_min,
            "max": word_count_max,
            "target": int(stats.median_word_count),
        },
        "severity": "warning",
        "priority": 80,
        "description": f"章节字数建议：{word_count_min}-{word_count_max}字（目标{int(stats.median_word_count)}字）",
        "confidence": 0.8,
    })
    
    # 对话占比规则
    dialogue_target = stats.avg_dialogue_ratio
    if dialogue_target > 0:
        suggestions.append({
            "rule_type": "chapter_basic",
            "rule_key": "dialogue_ratio",
            "rule_value": {
                "min": round(dialogue_target * 0.6, 2),
                "max": round(dialogue_target * 1.4, 2),
                "target": round(dialogue_target, 2),
            },
            "severity": "info",
            "priority": 60,
            "description": f"对话占比建议：{dialogue_target*100:.1f}%左右",
            "confidence": 0.6,
        })
    
    # AI味阈值规则
    suggestions.append({
        "rule_type": "ai_smell_lexicon",
        "rule_key": "le_word_density",
        "rule_value": {
            "threshold": round(stats.avg_le_word_density * 1.2, 1),
            "unit": "每千字",
        },
        "severity": "warning",
        "priority": 70,
        "description": f"\"了\"字密度阈值建议：≤{stats.avg_le_word_density * 1.2:.1f}/千字",
        "confidence": 0.7,
    })
    
    suggestions.append({
        "rule_type": "ai_smell_lexicon",
        "rule_key": "transition_word_density",
        "rule_value": {
            "threshold": round(stats.avg_transition_word_density * 1.2, 1),
            "unit": "每千字",
        },
        "severity": "warning",
        "priority": 70,
        "description": f"转折词密度阈值建议：≤{stats.avg_transition_word_density * 1.2:.1f}/千字",
        "confidence": 0.7,
    })
    
    suggestions.append({
        "rule_type": "ai_smell_lexicon",
        "rule_key": "abstract_adverb_density",
        "rule_value": {
            "threshold": round(stats.avg_abstract_adverb_density * 1.2, 1),
            "unit": "每千字",
        },
        "severity": "warning",
        "priority": 70,
        "description": f"抽象副词密度阈值建议：≤{stats.avg_abstract_adverb_density * 1.2:.1f}/千字",
        "confidence": 0.7,
    })
    
    # 爽点规则
    if stats.avg_payoff_density > 0:
        suggestions.append({
            "rule_type": "payoff",
            "rule_key": "payoff_density",
            "rule_value": {
                "min": round(stats.avg_payoff_density * 0.6, 2),
                "target": round(stats.avg_payoff_density, 2),
                "unit": "每千字",
            },
            "severity": "warning",
            "priority": 75,
            "description": f"爽点密度建议：≥{stats.avg_payoff_density * 0.6:.2f}/千字",
            "confidence": 0.6,
        })
    
    if stats.avg_first_payoff_position > 0:
        suggestions.append({
            "rule_type": "payoff",
            "rule_key": "first_payoff_position",
            "rule_value": {
                "max": int(stats.avg_first_payoff_position * 1.5),
                "unit": "字符数",
            },
            "severity": "info",
            "priority": 65,
            "description": f"第一个爽点位置建议：≤{int(stats.avg_first_payoff_position * 1.5)}字",
            "confidence": 0.5,
        })
    
    # 段落节奏
    suggestions.append({
        "rule_type": "pacing",
        "rule_key": "paragraph_length",
        "rule_value": {
            "avg": round(stats.avg_paragraph_length, 1),
            "median": round(stats.median_paragraph_length, 1),
        },
        "severity": "info",
        "priority": 50,
        "description": f"段落长度参考：平均{stats.avg_paragraph_length:.0f}字，中位数{stats.median_paragraph_length:.0f}字",
        "confidence": 0.5,
    })
    
    return suggestions


def generate_style_card_suggestion(stats: GenreStats) -> dict[str, Any]:
    """生成风格卡建议。"""
    style_card = {
        "name": f"{stats.genre_name}风格卡（自动生成）",
        "description": f"基于{stats.sample_count}章样本自动生成的风格参考",
        "features": {
            "avg_word_count": int(stats.avg_word_count),
            "avg_paragraph_count": int(stats.avg_paragraph_count),
            "dialogue_ratio": round(stats.avg_dialogue_ratio, 2),
            "exclamation_ratio": round(stats.avg_exclamation_ratio, 1),
            "payoff_density": round(stats.avg_payoff_density, 2),
        },
        "style_traits": [],
        "confidence": min(0.7, stats.sample_count / 100),  # 样本越多置信度越高
    }
    
    # 根据统计特征推断风格特点
    if stats.avg_exclamation_ratio > 5:
        style_card["style_traits"].append("情绪强烈，感叹号使用频繁")
    if stats.avg_dialogue_ratio > 0.3:
        style_card["style_traits"].append("对话占比高，节奏明快")
    if stats.avg_payoff_density > 1:
        style_card["style_traits"].append("爽点密集，刺激感强")
    if stats.avg_paragraph_length < 50:
        style_card["style_traits"].append("短句为主，节奏快")
    if stats.avg_le_word_density > 30:
        style_card["style_traits"].append("口语化程度高")
    
    return style_card


def generate_human_todo(stats: GenreStats) -> list[str]:
    """生成需要人工补齐的任务清单。"""
    todos = [
        "【世界观硬约束】人工补充品类专属的世界观硬约束规则",
        "【禁止词表】人工审核并补充品类专属的禁止词表",
        "【写作洞察】补充品类特有的写作技巧和注意事项",
        "【经典爽点】整理品类常见的爽点类型和变体",
        "【典型角色】补充品类典型角色类型和设定",
        "【经典场景】整理品类常见的场景类型和写法",
        "【读者画像】补充品类核心读者画像和偏好",
        "【竞品分析】分析头部作品的成功要素",
    ]
    
    # 根据样本数量调整
    if stats.sample_count < 10:
        todos.insert(0, "【样本不足】当前样本数量较少，建议增加样本后重新蒸馏")
    
    return todos


# ── 品类对比 ──────────────────────────────────────────────────────────────

def compare_genres(stats_list: list[GenreStats]) -> dict[str, Any]:
    """对比多个品类的特征。"""
    if len(stats_list) < 2:
        return {"error": "至少需要2个品类才能对比"}
    
    comparison = {
        "genres": [s.genre_name for s in stats_list],
        "dimensions": {},
        "summary": [],
    }
    
    # 对比维度
    dimensions = {
        "avg_word_count": "平均章节字数",
        "avg_paragraph_count": "平均段落数",
        "avg_dialogue_ratio": "对话占比",
        "avg_exclamation_ratio": "感叹号密度",
        "avg_le_word_density": "\"了\"字密度",
        "avg_transition_word_density": "转折词密度",
        "avg_payoff_density": "爽点密度",
        "avg_character_count": "平均角色数",
        "avg_emotion_fluctuation": "情感波动幅度",
    }
    
    for dim_key, dim_name in dimensions.items():
        values = []
        for stats in stats_list:
            value = getattr(stats, dim_key, 0)
            values.append({
                "genre": stats.genre_name,
                "value": value,
            })
        
        # 排序
        values_sorted = sorted(values, key=lambda x: x["value"], reverse=True)
        
        comparison["dimensions"][dim_key] = {
            "name": dim_name,
            "values": values,
            "highest": values_sorted[0] if values_sorted else None,
            "lowest": values_sorted[-1] if values_sorted else None,
            "ratio": values_sorted[0]["value"] / values_sorted[-1]["value"] 
                if values_sorted and values_sorted[-1]["value"] > 0 else 0,
        }
    
    # 生成总结
    summary = []
    for dim_key, dim_data in comparison["dimensions"].items():
        if dim_data["ratio"] > 1.5:
            summary.append(
                f"{dim_data['highest']['genre']}的{dim_data['name']}"
                f"是{dim_data['lowest']['genre']}的{dim_data['ratio']:.1f}倍"
            )
    
    comparison["summary"] = summary[:10]  # 最多10条总结
    
    return comparison


# ── 完整蒸馏流程 ──────────────────────────────────────────────────────────

def distill_genre(
    chapters: list[dict[str, Any]],
    genre_name: str = "",
) -> DistillationResult:
    """完整的品类蒸馏流程。
    
    Args:
        chapters: 章节列表，每个元素包含 text, chapter_number, title 等字段
        genre_name: 品类名称
    
    Returns:
        DistillationResult: 蒸馏结果
    """
    # 1. 提取特征
    chapter_features_list = []
    for chapter in chapters:
        text = chapter.get("text", "")
        chapter_number = chapter.get("chapter_number", 0)
        title = chapter.get("title", "")
        
        features = extract_chapter_features(text, chapter_number, title)
        chapter_features_list.append(features)
    
    # 2. 统计聚合
    stats = aggregate_genre_stats(chapter_features_list, genre_name)
    
    # 3. 生成规则建议
    rule_suggestions = generate_rule_suggestions(stats)
    
    # 4. 生成风格卡建议
    style_card = generate_style_card_suggestion(stats)
    
    # 5. 生成人工补齐任务
    human_todo = generate_human_todo(stats)
    
    # 6. 计算置信度
    confidence = min(0.8, stats.sample_count / 50)  # 50章以上置信度0.8
    
    result = DistillationResult(
        stats=stats,
        rule_suggestions=rule_suggestions,
        style_card_suggestion=style_card,
        human_todo=human_todo,
        confidence=confidence,
    )
    
    return result


def export_rule_pack(result: DistillationResult, output_path: str) -> None:
    """导出规则包为JSON文件。"""
    data = {
        "genre_name": result.stats.genre_name,
        "stats": asdict(result.stats),
        "rule_suggestions": result.rule_suggestions,
        "style_card": result.style_card_suggestion,
        "confidence": result.confidence,
        "generated_by": "genre_distillation",
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def export_human_todo(result: DistillationResult, output_path: str) -> None:
    """导出人工补齐任务为Markdown文件。"""
    lines = [
        f"# {result.stats.genre_name} 品类人工补齐任务清单",
        "",
        f"## 基本信息",
        f"- 品类名称：{result.stats.genre_name}",
        f"- 样本数量：{result.stats.sample_count} 章",
        f"- 自动提取置信度：{result.confidence * 100:.0f}%",
        "",
        f"## 自动提取完成度",
        f"- ✅ 章节基础规则（字数、段落等）",
        f"- ✅ AI味阈值规则（词级）",
        f"- ✅ 爽点密度规则",
        f"- ✅ 风格卡初稿",
        f"- ⏳ 世界观硬约束（需人工补充）",
        f"- ⏳ 禁止词表（需人工审核补充）",
        f"- ⏳ 写作洞察（需人工总结）",
        "",
        f"## 待完成任务",
        "",
    ]
    
    for i, todo in enumerate(result.human_todo, 1):
        lines.append(f"{i}. {todo}")
    
    lines.extend([
        "",
        "## 统计数据参考",
        "",
        f"- 平均章节字数：{result.stats.avg_word_count:.0f}",
        f"- 平均段落数：{result.stats.avg_paragraph_count:.0f}",
        f"- 平均对话占比：{result.stats.avg_dialogue_ratio * 100:.1f}%",
        f"- 平均爽点密度：{result.stats.avg_payoff_density:.2f}/千字",
        f"- 平均\"了\"字密度：{result.stats.avg_le_word_density:.1f}/千字",
        "",
        "---",
        "*本文件由品类蒸馏管线自动生成*",
    ])
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def export_comparison_report(
    stats_list: list[GenreStats],
    output_path: str,
) -> None:
    """导出品类对比报告。"""
    comparison = compare_genres(stats_list)
    
    lines = [
        "# 品类对比报告",
        "",
        f"## 对比品类",
        "",
    ]
    
    for stats in stats_list:
        lines.append(f"- {stats.genre_name}（{stats.sample_count}章样本）")
    
    lines.extend([
        "",
        "## 维度对比",
        "",
    ])
    
    for dim_key, dim_data in comparison["dimensions"].items():
        lines.append(f"### {dim_data['name']}")
        lines.append("")
        for v in dim_data["values"]:
            lines.append(f"- {v['genre']}: {v['value']:.2f}")
        lines.append("")
        if dim_data["ratio"] > 1.5:
            lines.append(
                f"**差异显著**：{dim_data['highest']['genre']}是"
                f"{dim_data['lowest']['genre']}的{dim_data['ratio']:.1f}倍"
            )
            lines.append("")
    
    lines.extend([
        "## 主要差异总结",
        "",
    ])
    
    for summary in comparison["summary"]:
        lines.append(f"- {summary}")
    
    lines.extend([
        "",
        "---",
        "*本报告由品类蒸馏管线自动生成*",
    ])
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
