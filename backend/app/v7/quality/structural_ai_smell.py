"""
模式级 AI 味检测模块

与词级检查互补：
- 词级检查（已有）：检测具体的词汇和短语
- 模式级检查（新增）：检测行文模式和结构模式

7 维检测：
1. 转折词密度（然而/但是/却/不过/可是）
2. 段落首句雷同（同一开头占比）
3. 抽象副词（深深地/缓缓地/默默地/轻轻地）
4. "了"字密度
5. 总结句（他知道/他忽然觉得/从此/也许这就是）
6. 对话完整度（省略主语/宾语比例）
7. 段落节奏标准差（段落长度均匀度）

设计原则：
- 纯统计，不需要AI调用
- 可配置阈值，支持不同品类
- 输出分数和详细信息
- 与现有去AI味管线并联
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import re
from statistics import mean, pstdev


@dataclass
class StructuralDimensionResult:
    """单个维度的检测结果"""
    name: str
    score: float  # 分数，越高越好，0-100
    actual: float  # 实际值
    threshold: float  # 阈值
    unit: str  # 单位
    passed: bool  # 是否通过
    detail: str = ""  # 详细说明
    examples: List[str] = field(default_factory=list)  # 示例

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 JSON 序列化"""
        return {
            "name": self.name,
            "score": self.score,
            "actual": self.actual,
            "threshold": self.threshold,
            "unit": self.unit,
            "passed": self.passed,
            "detail": self.detail,
            "examples": self.examples,
        }


@dataclass
class StructuralAISmellResult:
    """模式级 AI 味检测完整结果"""
    overall_score: float  # 总分，0-100
    grade: str  # 等级：🟢/🟡/🔴
    passed: bool  # 是否通过
    dimensions: List[StructuralDimensionResult] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 JSON 序列化"""
        return {
            "overall_score": self.overall_score,
            "grade": self.grade,
            "passed": self.passed,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "summary": self.summary,
        }


# ============== 阈值配置 ==============

# 番茄爽文阈值（最严格）
TOMATO_THRESHOLDS = {
    "transition_word_density": 5.0,       # 转折词：≤5/千字
    "paragraph_opening_repeat": 0.15,     # 段落首句雷同：≤15%
    "abstract_adverb_density": 2.0,       # 抽象副词：≤2/千字
    "le_word_density": 30.0,              # "了"字：≤30/千字
    "summary_sentence_density": 3.0,      # 总结句：≤3/千字
    "dialogue_omit_ratio": 0.30,          # 对话省略主语：≥30%
    "paragraph_rhythm_cv": 0.30,          # 段落节奏变异系数：≥30%
}

# 起点中文网阈值
QIDIAN_THRESHOLDS = {
    "transition_word_density": 8.0,
    "paragraph_opening_repeat": 0.20,
    "abstract_adverb_density": 3.0,
    "le_word_density": 45.0,
    "summary_sentence_density": 5.0,
    "dialogue_omit_ratio": 0.20,
    "paragraph_rhythm_cv": 0.25,
}

# 晋江文学城阈值
JJWXC_THRESHOLDS = {
    "transition_word_density": 6.0,
    "paragraph_opening_repeat": 0.15,
    "abstract_adverb_density": 2.0,
    "le_word_density": 35.0,
    "summary_sentence_density": 3.0,
    "dialogue_omit_ratio": 0.25,
    "paragraph_rhythm_cv": 0.30,
}

# 默认阈值（通用网文）
DEFAULT_THRESHOLDS = {
    "transition_word_density": 10.0,
    "paragraph_opening_repeat": 0.25,
    "abstract_adverb_density": 5.0,
    "le_word_density": 40.0,
    "summary_sentence_density": 8.0,
    "dialogue_omit_ratio": 0.15,
    "paragraph_rhythm_cv": 0.20,
}

THRESHOLD_PRESETS = {
    "tomato": TOMATO_THRESHOLDS,
    "qidian": QIDIAN_THRESHOLDS,
    "jjwxc": JJWXC_THRESHOLDS,
    "default": DEFAULT_THRESHOLDS,
}


def get_thresholds(preset: str = "default") -> Dict[str, float]:
    """获取指定预设的阈值配置"""
    return THRESHOLD_PRESETS.get(preset, DEFAULT_THRESHOLDS).copy()


# ============== 各维度检测函数 ==============

def _count_chars(text: str) -> int:
    """计算文本的字符数（不含空白）"""
    return len(re.sub(r"\s+", "", text))


def detect_transition_word_density(text: str) -> Dict[str, Any]:
    """
    维度1：转折词密度
    检测：然而/但是/却/不过/可是 等转折词的密度
    """
    transition_words = ["然而", "但是", "却", "不过", "可是", "但", "然而"]
    total_chars = _count_chars(text)
    if total_chars == 0:
        return {"density": 0.0, "count": 0, "per_1k": 0.0, "examples": []}
    
    count = 0
    examples = []
    for word in transition_words:
        matches = re.findall(word, text)
        count += len(matches)
        if matches:
            examples.extend(matches[:3])
    
    per_1k = (count / total_chars) * 1000
    
    return {
        "density": per_1k,
        "count": count,
        "per_1k": round(per_1k, 2),
        "examples": list(set(examples))[:5],
        "total_chars": total_chars
    }


def detect_paragraph_opening_repeat(text: str) -> Dict[str, Any]:
    """
    维度2：段落首句雷同
    检测：连续多段以相同词语开头的比例
    """
    paragraphs = [p.strip() for p in re.split(r"\n{2,}|\n", text) if p.strip()]
    if len(paragraphs) < 5:
        return {"ratio": 0.0, "most_common": "", "count": 0, "total": len(paragraphs)}
    
    openings = []
    for p in paragraphs:
        # 取段落前2-3个字作为开头
        clean = re.sub(r"^[「」『』\"“”‘’\s（(]+", "", p)
        if len(clean) >= 2:
            openings.append(clean[:2])
    
    if not openings:
        return {"ratio": 0.0, "most_common": "", "count": 0, "total": len(paragraphs)}
    
    from collections import Counter
    counter = Counter(openings)
    most_common, count = counter.most_common(1)[0]
    ratio = count / len(openings)
    
    return {
        "ratio": round(ratio, 3),
        "most_common": most_common,
        "count": count,
        "total": len(openings),
        "top_openings": counter.most_common(3)
    }


def detect_abstract_adverb_density(text: str) -> Dict[str, Any]:
    """
    维度3：抽象副词密度
    检测：深深地/缓缓地/默默地/轻轻地 等抽象副词
    """
    abstract_adverbs = [
        "深深地", "缓缓地", "默默地", "轻轻地", "静静地", "慢慢地",
        "悄悄地", "暗暗地", "微微地", "淡淡地", "冷冷地", "暖暖地",
        "深深", "缓缓", "默默", "轻轻", "静静", "慢慢", "悄悄",
    ]
    total_chars = _count_chars(text)
    if total_chars == 0:
        return {"density": 0.0, "count": 0, "per_1k": 0.0, "examples": []}
    
    count = 0
    examples = []
    for word in abstract_adverbs:
        matches = re.findall(word, text)
        count += len(matches)
        if matches:
            examples.extend(matches[:3])
    
    per_1k = (count / total_chars) * 1000
    
    return {
        "density": per_1k,
        "count": count,
        "per_1k": round(per_1k, 2),
        "examples": list(set(examples))[:5],
        "total_chars": total_chars
    }


def detect_le_word_density(text: str) -> Dict[str, Any]:
    """
    维度4："了"字密度
    检测：每千字"了"字出现次数
    """
    total_chars = _count_chars(text)
    if total_chars == 0:
        return {"density": 0.0, "count": 0, "per_1k": 0.0}
    
    count = len(re.findall("了", text))
    per_1k = (count / total_chars) * 1000
    
    return {
        "density": per_1k,
        "count": count,
        "per_1k": round(per_1k, 2),
        "total_chars": total_chars
    }


def detect_summary_sentence_density(text: str) -> Dict[str, Any]:
    """
    维度5：总结句密度
    检测：他知道/他忽然觉得/从此/也许这就是 等AI式总结句
    """
    summary_patterns = [
        r"他知道",
        r"她知道",
        r"他忽然觉得",
        r"她忽然觉得",
        r"他明白",
        r"她明白",
        r"从此",
        r"也许这就是",
        r"这就是",
        r"总而言之",
        r"综上所述",
        r"由此可见",
    ]
    total_chars = _count_chars(text)
    if total_chars == 0:
        return {"density": 0.0, "count": 0, "per_1k": 0.0, "examples": []}
    
    count = 0
    examples = []
    for pattern in summary_patterns:
        matches = re.findall(pattern, text)
        count += len(matches)
        if matches:
            examples.extend(matches[:3])
    
    per_1k = (count / total_chars) * 1000
    
    return {
        "density": per_1k,
        "count": count,
        "per_1k": round(per_1k, 2),
        "examples": list(set(examples))[:5],
        "total_chars": total_chars
    }


def detect_dialogue_omit_ratio(text: str) -> Dict[str, Any]:
    """
    维度6：对话完整度（省略主语比例）
    检测：对话中省略主语/宾语的比例
    注意：这是一个近似估算，不是精确值
    """
    # 提取对话内容（引号内的内容）
    dialogues = re.findall(r"[「『\"“](.*?)[」』\"”]", text, re.DOTALL)
    if not dialogues:
        return {"ratio": 0.0, "total_dialogues": 0, "omitted": 0}
    
    total = len(dialogues)
    omitted = 0
    
    # 简单判断：短对话（2-5字）通常省略了主语
    # 或者对话中没有明显的主语（你/我/他/她）
    for dialogue in dialogues:
        clean = dialogue.strip()
        if len(clean) == 0:
            continue
        
        # 短对话很可能省略了主语
        if len(clean) <= 5:
            omitted += 1
            continue
        
        # 检查是否有主语
        has_subject = any(word in clean for word in ["你", "我", "他", "她", "它", "我们", "你们", "他们"])
        if not has_subject:
            omitted += 1
    
    ratio = omitted / total if total > 0 else 0.0
    
    return {
        "ratio": round(ratio, 3),
        "total_dialogues": total,
        "omitted": omitted,
        "examples": dialogues[:3]
    }


def detect_paragraph_rhythm(text: str) -> Dict[str, Any]:
    """
    维度7：段落节奏标准差
    检测：段落长度的变异系数（标准差/均值）
    变异系数越小，说明段落越均匀，越像AI写的
    """
    paragraphs = [p.strip() for p in re.split(r"\n{2,}|\n", text) if p.strip()]
    if len(paragraphs) < 5:
        lengths = [len(re.sub(r"\s+", "", p)) for p in paragraphs]
        return {
            "cv": 0.0,
            "mean": round(mean(lengths), 1) if lengths else 0,
            "std": 0,
            "total_paragraphs": len(paragraphs),
            "min_length": min(lengths) if lengths else 0,
            "max_length": max(lengths) if lengths else 0,
        }
    
    lengths = [len(re.sub(r"\s+", "", p)) for p in paragraphs]
    
    avg = mean(lengths)
    std = pstdev(lengths) if len(lengths) > 1 else 0
    cv = std / avg if avg > 0 else 0.0
    
    return {
        "cv": round(cv, 3),
        "mean": round(avg, 1),
        "std": round(std, 1),
        "total_paragraphs": len(paragraphs),
        "min_length": min(lengths),
        "max_length": max(lengths)
    }


# ============== 综合检测 ==============

def analyze_structural_ai_smell(
    text: str,
    threshold_preset: str = "default",
    custom_thresholds: Dict[str, float] = None
) -> StructuralAISmellResult:
    """
    综合分析文本的模式级 AI 味
    
    Args:
        text: 要分析的文本
        threshold_preset: 阈值预设（tomato/qidian/jjwxc/default）
        custom_thresholds: 自定义阈值，会覆盖预设
        
    Returns:
        StructuralAISmellResult 检测结果
    """
    # 获取阈值
    thresholds = get_thresholds(threshold_preset)
    if custom_thresholds:
        thresholds.update(custom_thresholds)
    
    dimensions = []
    
    # 1. 转折词密度
    transition_result = detect_transition_word_density(text)
    transition_threshold = thresholds["transition_word_density"]
    transition_score = _calculate_score(
        transition_result["per_1k"],
        transition_threshold,
        higher_is_better=False
    )
    dimensions.append(StructuralDimensionResult(
        name="转折词密度",
        score=transition_score,
        actual=transition_result["per_1k"],
        threshold=transition_threshold,
        unit="个/千字",
        passed=transition_result["per_1k"] <= transition_threshold,
        detail=f"共 {transition_result['count']} 个转折词",
        examples=transition_result["examples"]
    ))
    
    # 2. 段落首句雷同
    opening_result = detect_paragraph_opening_repeat(text)
    opening_threshold = thresholds["paragraph_opening_repeat"]
    opening_score = _calculate_score(
        opening_result["ratio"],
        opening_threshold,
        higher_is_better=False
    )
    dimensions.append(StructuralDimensionResult(
        name="段落首句雷同",
        score=opening_score,
        actual=opening_result["ratio"] * 100,
        threshold=opening_threshold * 100,
        unit="%",
        passed=opening_result["ratio"] <= opening_threshold,
        detail=f"最常见开头：'{opening_result['most_common']}'，出现 {opening_result['count']} 次",
        examples=[f"{k}: {v}次" for k, v in opening_result.get("top_openings", [])]
    ))
    
    # 3. 抽象副词密度
    adverb_result = detect_abstract_adverb_density(text)
    adverb_threshold = thresholds["abstract_adverb_density"]
    adverb_score = _calculate_score(
        adverb_result["per_1k"],
        adverb_threshold,
        higher_is_better=False
    )
    dimensions.append(StructuralDimensionResult(
        name="抽象副词密度",
        score=adverb_score,
        actual=adverb_result["per_1k"],
        threshold=adverb_threshold,
        unit="个/千字",
        passed=adverb_result["per_1k"] <= adverb_threshold,
        detail=f"共 {adverb_result['count']} 个抽象副词",
        examples=adverb_result["examples"]
    ))
    
    # 4. "了"字密度
    le_result = detect_le_word_density(text)
    le_threshold = thresholds["le_word_density"]
    le_score = _calculate_score(
        le_result["per_1k"],
        le_threshold,
        higher_is_better=False
    )
    dimensions.append(StructuralDimensionResult(
        name='"了"字密度',
        score=le_score,
        actual=le_result["per_1k"],
        threshold=le_threshold,
        unit="个/千字",
        passed=le_result["per_1k"] <= le_threshold,
        detail=f"共 {le_result['count']} 个'了'字"
    ))
    
    # 5. 总结句密度
    summary_result = detect_summary_sentence_density(text)
    summary_threshold = thresholds["summary_sentence_density"]
    summary_score = _calculate_score(
        summary_result["per_1k"],
        summary_threshold,
        higher_is_better=False
    )
    dimensions.append(StructuralDimensionResult(
        name="总结句密度",
        score=summary_score,
        actual=summary_result["per_1k"],
        threshold=summary_threshold,
        unit="个/千字",
        passed=summary_result["per_1k"] <= summary_threshold,
        detail=f"共 {summary_result['count']} 个总结句式",
        examples=summary_result["examples"]
    ))
    
    # 6. 对话省略比例
    dialogue_result = detect_dialogue_omit_ratio(text)
    dialogue_threshold = thresholds["dialogue_omit_ratio"]
    dialogue_score = _calculate_score(
        dialogue_result["ratio"],
        dialogue_threshold,
        higher_is_better=True
    )
    dimensions.append(StructuralDimensionResult(
        name="对话省略比例",
        score=dialogue_score,
        actual=dialogue_result["ratio"] * 100,
        threshold=dialogue_threshold * 100,
        unit="%",
        passed=dialogue_result["ratio"] >= dialogue_threshold,
        detail=f"{dialogue_result['omitted']}/{dialogue_result['total_dialogues']} 句对话省略了主语"
    ))
    
    # 7. 段落节奏变异系数
    rhythm_result = detect_paragraph_rhythm(text)
    rhythm_threshold = thresholds["paragraph_rhythm_cv"]
    rhythm_score = _calculate_score(
        rhythm_result["cv"],
        rhythm_threshold,
        higher_is_better=True
    )
    dimensions.append(StructuralDimensionResult(
        name="段落节奏变异",
        score=rhythm_score,
        actual=rhythm_result["cv"] * 100,
        threshold=rhythm_threshold * 100,
        unit="%",
        passed=rhythm_result["cv"] >= rhythm_threshold,
        detail=f"均值 {rhythm_result['mean']} 字，标准差 {rhythm_result['std']} 字",
        examples=[f"最短 {rhythm_result['min_length']} 字", f"最长 {rhythm_result['max_length']} 字"]
    ))
    
    # 计算总分
    total_score = sum(d.score for d in dimensions) / len(dimensions)
    
    # 确定等级
    if total_score >= 80:
        grade = "🟢"
        passed = True
    elif total_score >= 60:
        grade = "🟡"
        passed = True
    else:
        grade = "🔴"
        passed = False
    
    # 统计
    passed_count = sum(1 for d in dimensions if d.passed)
    failed_count = len(dimensions) - passed_count
    
    return StructuralAISmellResult(
        overall_score=round(total_score, 1),
        grade=grade,
        passed=passed,
        dimensions=dimensions,
        summary={
            "total_dimensions": len(dimensions),
            "passed_dimensions": passed_count,
            "failed_dimensions": failed_count,
            "threshold_preset": threshold_preset
        }
    )


def _calculate_score(actual: float, threshold: float, higher_is_better: bool = False) -> float:
    """
    计算单个维度的分数（0-100）
    
    Args:
        actual: 实际值
        threshold: 阈值
        higher_is_better: True=越高越好，False=越低越好
        
    Returns:
        0-100 的分数
    """
    if threshold == 0:
        return 100.0 if actual == 0 else 0.0
    
    ratio = actual / threshold
    
    if higher_is_better:
        # 越高越好
        if ratio >= 1.0:
            return 100.0
        elif ratio >= 0.8:
            return 80.0 + (ratio - 0.8) * 100  # 80-100
        elif ratio >= 0.5:
            return 50.0 + (ratio - 0.5) * 100  # 50-80
        else:
            return ratio * 100  # 0-50
    else:
        # 越低越好
        if ratio <= 1.0:
            return 100.0 - (ratio * 20)  # 80-100
        elif ratio <= 1.5:
            return 80.0 - (ratio - 1.0) * 60  # 50-80
        elif ratio <= 2.0:
            return 50.0 - (ratio - 1.5) * 100  # 0-50
        else:
            return 0.0
