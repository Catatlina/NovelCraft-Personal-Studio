"""
金句检测与存储模块

每章至少应该有一句读者会划线、截图、分享的话。
AI生成往往没有，所以需要自动检测并积累。

筛选标准：
- 字数 ≤ 30 字
- 结构独特（对仗/排比/反转等）
- 有情绪冲击力或哲理感
- 不是对话中的普通台词

设计原则：
- 纯规则 + 简单 NLP，不需要 AI 调用
- 输出候选金句列表，按评分排序
- 可配置阈值，适配不同风格
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import re


@dataclass
class GoldenQuote:
    """候选金句"""
    text: str  # 金句文本
    score: float  # 评分（0-100）
    reasons: List[str]  # 入选理由
    position: int  # 在原文中的位置（字符偏移）
    quote_type: str  # 金句类型：antithesis/parallelism/reversal/philosophy/emotional/mixed
    word_count: int  # 字数


@dataclass
class GoldenQuoteResult:
    """金句检测结果"""
    quotes: List[GoldenQuote]  # 候选金句列表（按评分降序）
    total_count: int  # 候选数量
    has_high_quality: bool  # 是否有高质量金句（≥80分）
    best_quote: Optional[GoldenQuote]  # 最佳金句
    suggestions: List[str]  # 改进建议
    chapter_length: int  # 章节长度（字数）


# ============== 关键词库 ==============

# 哲理类词汇
PHILOSOPHY_WORDS = [
    "命运", "人生", "世界", "时间", "生命", "死亡", "意义", "真相",
    "选择", "代价", "牺牲", "成长", "蜕变", "觉醒", "顿悟",
    "原来", "其实", "终究", "毕竟", "终归", "到底",
    "这就是", "这才是", "所谓", "所谓的",
]

# 情绪强烈的词汇
EMOTIONAL_WORDS = [
    "永远", "绝不", "一定", "必须", "只能", "只有",
    "最", "太", "真", "好", "恨", "爱", "痛", "死",
    "崩溃", "绝望", "希望", "失望", "心碎", "心疼",
    "震撼", "感动", "温暖", "冰冷", "孤独", "寂寞",
]

# 断言/总结性词汇
ASSERTION_WORDS = [
    "就是", "才是", "都是", "不是", "没有",
    "从来", "一直", "永远", "始终",
    "这就是", "那就是", "这才是",
    "所谓", "所谓的",
]

# 对仗/排比常见结构
PARALLEL_STRUCTURES = [
    ("不是...而是...", ["不是", "而是"]),
    ("没有...只有...", ["没有", "只有"]),
    ("要么...要么...", ["要么", "要么"]),
    ("或者...或者...", ["或者", "或者"]),
    ("因为...所以...", ["因为", "所以"]),
    ("虽然...但是...", ["虽然", "但是"]),
    ("即使...也...", ["即使", "也"]),
    ("只要...就...", ["只要", "就"]),
    ("只有...才...", ["只有", "才"]),
    ("无论...都...", ["无论", "都"]),
]

# 反转信号词
REVERSAL_SIGNALS = [
    "但是", "然而", "却", "可是", "不过", "反而", "反倒",
    "没想到", "谁知", "哪知", "不料", "结果",
    "原来", "其实", "事实上", "实际上",
]


# ============== 工具函数 ==============

def _count_chinese_chars(text: str) -> int:
    """统计中文字符数"""
    return len(re.findall(r'[\u4e00-\u9fff]', text))


def _split_sentences(text: str) -> List[Tuple[str, int]]:
    """
    把文本分成句子
    
    Args:
        text: 原文
        
    Returns:
        句子列表，每个元素是 (句子文本, 起始位置)
    """
    sentences = []
    current = ""
    current_pos = 0
    
    for i, char in enumerate(text):
        current += char
        
        # 句子结束标记
        if char in ['。', '！', '？', '…', '.', '!', '?']:
            # 省略号特殊处理
            if char == '…' and len(current) >= 2 and current[-2] == '…':
                continue
            
            # 去掉首尾空白
            stripped = current.strip()
            if stripped and _count_chinese_chars(stripped) >= 3:
                sentences.append((stripped, current_pos))
            
            current = ""
            current_pos = i + 1
    
    # 处理最后一句
    if current.strip():
        stripped = current.strip()
        if stripped and _count_chinese_chars(stripped) >= 3:
            sentences.append((stripped, current_pos))
    
    return sentences


def _is_in_dialogue(text: str, position: int) -> bool:
    """
    判断某个位置是否在对话中（引号内）
    
    简单实现：统计该位置之前的引号数量，奇数表示在对话内
    """
    before = text[:position]
    quote_count = before.count('「') + before.count('“') + before.count('"')
    quote_count -= before.count('」') + before.count('”') + before.count('"')
    
    return quote_count % 2 == 1


# ============== 检测函数 ==============

def _check_antithesis(sentence: str) -> Tuple[float, List[str]]:
    """
    检测对仗结构
    
    对仗：前后两部分结构相似、字数相近、意思相对或相关
    
    Returns:
        (分数, 理由列表)
    """
    score = 0
    reasons = []
    
    # 检查常见的对仗结构
    for name, keywords in PARALLEL_STRUCTURES:
        if all(kw in sentence for kw in keywords):
            score += 30
            reasons.append(f"对仗结构：{name}")
            break
    
    # 检查是否有逗号分隔的两部分，且字数相近
    if '，' in sentence or ',' in sentence:
        parts = re.split(r'[，,]', sentence)
        if len(parts) == 2:
            len1 = _count_chinese_chars(parts[0])
            len2 = _count_chinese_chars(parts[1])
            
            # 字数相近（相差不超过30%）
            if len1 > 0 and len2 > 0:
                ratio = min(len1, len2) / max(len1, len2)
                if ratio >= 0.7:
                    score += 20
                    reasons.append("前后字数相近，有对称感")
                
                # 检查是否有相同的字开头或结尾
                if parts[0][0] == parts[1][0]:
                    score += 10
                    reasons.append("首字相同，有排比感")
                if parts[0][-1] == parts[1][-1]:
                    score += 10
                    reasons.append("尾字相同，有韵律感")
    
    return min(100, score), reasons


def _check_parallelism(sentence: str) -> Tuple[float, List[str]]:
    """
    检测排比结构
    
    排比：三个以上结构相似的短语或句子
    
    Returns:
        (分数, 理由列表)
    """
    score = 0
    reasons = []
    
    # 检查是否有多个逗号分隔的部分
    parts = re.split(r'[，,、]', sentence)
    if len(parts) >= 3:
        # 检查各部分字数是否相近
        lengths = [_count_chinese_chars(p) for p in parts if p.strip()]
        if len(lengths) >= 3:
            avg_len = sum(lengths) / len(lengths)
            if avg_len > 0:
                variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
                std_dev = variance ** 0.5
                # 标准差小于平均的30%，说明比较整齐
                if std_dev / avg_len < 0.3:
                    score += 25
                    reasons.append(f"{len(parts)}个短语排比，结构整齐")
    
    # 检查是否有重复的词语
    words = re.findall(r'[\u4e00-\u9fff]{2,}', sentence)
    if len(words) >= 3:
        word_set = set(words)
        if len(word_set) < len(words):
            # 有重复词
            score += 15
            reasons.append("有重复词语，有节奏感")
    
    return min(100, score), reasons


def _check_reversal(sentence: str) -> Tuple[float, List[str]]:
    """
    检测反转/转折
    
    反转：前后意思相反，有意外感
    
    Returns:
        (分数, 理由列表)
    """
    score = 0
    reasons = []
    
    # 检查反转信号词
    reversal_count = 0
    for signal in REVERSAL_SIGNALS:
        if signal in sentence:
            reversal_count += 1
    
    if reversal_count >= 2:
        score += 20
        reasons.append("多重转折，有反转感")
    elif reversal_count >= 1:
        score += 10
        reasons.append("有转折，有变化感")
    
    # 检查是否有"以为...没想到..."之类的结构
    if "以为" in sentence and ("没想到" in sentence or "谁知" in sentence or "哪知" in sentence):
        score += 25
        reasons.append("预期反转结构，有意外感")
    
    # 检查是否有否定+肯定的结构
    has_negative = any(word in sentence for word in ["不", "没", "无", "非"])
    has_positive = any(word in sentence for word in ["是", "有", "就", "才"])
    if has_negative and has_positive:
        score += 15
        reasons.append("否定+肯定，有张力")
    
    return min(100, score), reasons


def _check_philosophy(sentence: str) -> Tuple[float, List[str]]:
    """
    检测哲理感
    
    哲理感：关于人生、命运、世界等的深刻思考
    
    Returns:
        (分数, 理由列表)
    """
    score = 0
    reasons = []
    
    # 检查哲理词汇
    philosophy_count = 0
    for word in PHILOSOPHY_WORDS:
        if word in sentence:
            philosophy_count += 1
    
    if philosophy_count >= 3:
        score += 30
        reasons.append(f"富含哲理词汇（{philosophy_count}个）")
    elif philosophy_count >= 2:
        score += 20
        reasons.append(f"有哲理词汇（{philosophy_count}个）")
    elif philosophy_count >= 1:
        score += 10
        reasons.append("有哲理词汇")
    
    # 检查断言/总结性词汇
    assertion_count = 0
    for word in ASSERTION_WORDS:
        if word in sentence:
            assertion_count += 1
    
    if assertion_count >= 2:
        score += 20
        reasons.append("有断言语气，有力量感")
    elif assertion_count >= 1:
        score += 10
        reasons.append("有断言语气")
    
    # 句子以"。"结尾，且比较短，像格言
    if _count_chinese_chars(sentence) <= 20:
        score += 10
        reasons.append("简短有力，像格言")
    
    return min(100, score), reasons


def _check_emotional_impact(sentence: str) -> Tuple[float, List[str]]:
    """
    检测情绪冲击力
    
    情绪冲击力：有强烈的情绪表达，能打动读者
    
    Returns:
        (分数, 理由列表)
    """
    score = 0
    reasons = []
    
    # 检查情绪词汇
    emotional_count = 0
    for word in EMOTIONAL_WORDS:
        if word in sentence:
            emotional_count += sentence.count(word)
    
    if emotional_count >= 4:
        score += 30
        reasons.append(f"情绪词汇丰富（{emotional_count}个）")
    elif emotional_count >= 2:
        score += 20
        reasons.append(f"有情绪词汇（{emotional_count}个）")
    elif emotional_count >= 1:
        score += 10
        reasons.append("有情绪词汇")
    
    # 检查是否有感叹号
    if '！' in sentence or '!' in sentence:
        score += 15
        reasons.append("有感叹号，情绪强烈")
    
    # 检查是否有重复词（强调）
    words = list(sentence)
    for i in range(len(words) - 1):
        if words[i] == words[i+1] and '\u4e00' <= words[i] <= '\u9fff':
            score += 10
            reasons.append("有叠词，有强调感")
            break
    
    return min(100, score), reasons


# ============== 综合检测 ==============

def detect_golden_quotes(
    text: str,
    max_quotes: int = 5,
    min_score: float = 25,
    max_length: int = 30,
    include_dialogue: bool = True
) -> GoldenQuoteResult:
    """
    检测文本中的候选金句
    
    Args:
        text: 章节正文
        max_quotes: 最多返回多少个候选
        min_score: 最低分数阈值
        max_length: 最大字数（超过的句子不考虑）
        include_dialogue: 是否包含对话中的句子
        
    Returns:
        金句检测结果
    """
    total_chars = _count_chinese_chars(text)
    
    # 分句
    sentences = _split_sentences(text)
    
    candidates = []
    
    for sentence, position in sentences:
        word_count = _count_chinese_chars(sentence)
        
        # 字数限制
        if word_count > max_length or word_count < 3:
            continue
        
        # 是否排除对话
        if not include_dialogue and _is_in_dialogue(text, position):
            continue
        
        # 各项检测
        antithesis_score, antithesis_reasons = _check_antithesis(sentence)
        parallelism_score, parallelism_reasons = _check_parallelism(sentence)
        reversal_score, reversal_reasons = _check_reversal(sentence)
        philosophy_score, philosophy_reasons = _check_philosophy(sentence)
        emotional_score, emotional_reasons = _check_emotional_impact(sentence)
        
        # 综合评分（加权）
        weights = {
            "antithesis": 0.25,
            "parallelism": 0.15,
            "reversal": 0.20,
            "philosophy": 0.25,
            "emotional": 0.15,
        }
        
        total_score = (
            antithesis_score * weights["antithesis"] +
            parallelism_score * weights["parallelism"] +
            reversal_score * weights["reversal"] +
            philosophy_score * weights["philosophy"] +
            emotional_score * weights["emotional"]
        )
        
        # 低于阈值的跳过
        if total_score < min_score:
            continue
        
        # 收集理由
        all_reasons = []
        all_reasons.extend(antithesis_reasons)
        all_reasons.extend(parallelism_reasons)
        all_reasons.extend(reversal_reasons)
        all_reasons.extend(philosophy_reasons)
        all_reasons.extend(emotional_reasons)
        
        # 判断类型
        scores = {
            "antithesis": antithesis_score,
            "parallelism": parallelism_score,
            "reversal": reversal_score,
            "philosophy": philosophy_score,
            "emotional": emotional_score,
        }
        max_type = max(scores, key=scores.get)
        if scores[max_type] < 30:
            quote_type = "mixed"
        else:
            quote_type = max_type
        
        quote = GoldenQuote(
            text=sentence,
            score=round(total_score, 1),
            reasons=all_reasons,
            position=position,
            quote_type=quote_type,
            word_count=word_count
        )
        candidates.append(quote)
    
    # 按评分排序
    candidates.sort(key=lambda x: x.score, reverse=True)
    
    # 取前 N 个
    result_quotes = candidates[:max_quotes]
    
    # 最佳金句
    best_quote = result_quotes[0] if result_quotes else None
    
    # 是否有高质量金句
    has_high_quality = any(q.score >= 80 for q in result_quotes)
    
    # 改进建议
    suggestions = []
    if not result_quotes:
        suggestions.append("本章没有检测到明显的金句，建议添加1-2句有冲击力或哲理感的话")
    elif len(result_quotes) < 2:
        suggestions.append("本章金句较少，建议再添加1-2句")
    elif not has_high_quality:
        suggestions.append("本章金句质量一般，建议打磨一句更有冲击力的核心金句")
    else:
        suggestions.append("✅ 本章有高质量金句，传播力不错")
    
    return GoldenQuoteResult(
        quotes=result_quotes,
        total_count=len(result_quotes),
        has_high_quality=has_high_quality,
        best_quote=best_quote,
        suggestions=suggestions,
        chapter_length=total_chars
    )
