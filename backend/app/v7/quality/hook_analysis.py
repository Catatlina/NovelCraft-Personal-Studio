"""
首章钩力分析模块

对首章（或前3章）做专项分析，输出"钩力报告"。
平台算法最看重前三章——尤其是第一章的读者留存率。

6个核心维度：
1. 开篇钩子强度（前100字吸引力评分）
2. 第1个爽点出现位置
3. 章末钩子锋利度评分
4. 信息释放节奏（信息密度曲线）
5. 人物辨识度（主角是否在前500字立住）
6. 预估首章留存率

设计原则：
- 纯规则/统计优先，不需要AI调用
- 需要AI调用的部分设计成可选增强
- 集成到质量门禁，作为信息输出（不阻塞）
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import re


@dataclass
class HookAnalysisResult:
    """首章钩力分析结果"""
    overall_score: float  # 总体钩力评分，0-100
    grade: str  # 等级：S/A/B/C/D
    
    # 6个核心维度
    opening_hook_strength: float  # 开篇钩子强度，0-10
    opening_hook_comment: str  # 开篇钩子评价
    
    first_payoff_position: int  # 第1个爽点出现位置（字数）
    first_payoff_comment: str  # 爽点位置评价
    
    ending_hook_sharpness: float  # 章末钩子锋利度，0-10
    ending_hook_comment: str  # 章末钩子评价
    
    information_release_score: float  # 信息释放节奏评分，0-10
    information_release_comment: str  # 信息释放评价
    info_density_curve: List[float]  # 信息密度曲线（每100字的信息密度）
    
    character_recognition: float  # 人物辨识度，0-10
    character_recognition_comment: str  # 人物辨识度评价
    
    estimated_retention_rate: float  # 预估留存率，百分比
    
    # 额外信息
    chapter_length: int  # 章节长度（字数）
    suggestions: List[str]  # 改进建议


# ============== 关键词库 ==============

# 爽点信号词
PAYOFF_SIGNAL_WORDS = [
    # 打脸类
    "打脸", "扇", "耳光", "啪", "震惊", "哗然", "震动", "震撼",
    "不敢相信", "难以置信", "目瞪口呆", "傻眼", "愣住", "呆住",
    # 升级/获得类
    "突破", "升级", "晋升", "获得", "得到", "觉醒", "激活", "解锁",
    "系统", "金手指", "外挂", "神器", "宝物", "秘籍", "功法",
    # 反转类
    "没想到", "竟然", "居然", "谁知", "哪知", "不料", "结果",
    # 装逼类
    "冷笑", "不屑", "轻蔑", "淡然", "淡定", "从容", "微微一笑",
    # 爽感类
    "爽", "痛快", "解气", "过瘾", "舒服",
]

# 钩子信号词（悬念、冲突、异常）
HOOK_SIGNAL_WORDS = [
    # 悬念类
    "什么", "怎么", "为什么", "难道", "莫非", "究竟", "到底",
    "秘密", "谜团", "真相", "隐藏", "神秘", "诡异", "奇怪",
    # 冲突类
    "冲突", "矛盾", "对立", "对抗", "战斗", "厮杀", "决斗",
    "威胁", "危险", "危机", "险境", "绝境",
    # 异常类
    "异常", "不对劲", "反常", "奇怪", "诡异", "离奇",
    "突然", "忽然", "猛地", "骤然",
]

# 章末钩子信号
ENDING_HOOK_SIGNALS = [
    "却没想到", "就在这时", "突然", "忽然", "下一秒",
    "谁知", "哪知", "不料", "结果",
    "等待他的", "迎接他的", "出现在眼前的",
    "竟然是", "居然是", "原来是",
    "……", "？", "！",
]

# 背景倒灌信号（一次性解释世界观）
BACKGROUND_DUMP_SIGNALS = [
    "在这个世界", "这个世界", "在这片大陆", "这片大陆",
    "传说", "据说", "相传", "自古以来",
    "分为", "分为几大", "共有", "总共有",
    "等级", "境界", "修为", "实力",
]

# 人物特征描写信号
CHARACTER_FEATURE_SIGNALS = [
    "穿着", "身着", "身穿", "打扮", "相貌", "长相", "面容", "脸庞",
    "眼睛", "眼神", "眉毛", "鼻子", "嘴巴", "身材", "身形", "体型",
    "气质", "气度", "气场", "神态", "表情",
    "性格", "脾气", "为人", "平时", "一向",
]


# ============== 工具函数 ==============

def _count_chinese_chars(text: str) -> int:
    """统计中文字符数"""
    return len(re.findall(r'[\u4e00-\u9fff]', text))


def _split_into_chunks(text: str, chunk_size: int = 100) -> List[str]:
    """把文本分成指定大小的块"""
    chunks = []
    current = ""
    count = 0
    for char in text:
        current += char
        if '\u4e00' <= char <= '\u9fff':
            count += 1
            if count >= chunk_size:
                chunks.append(current)
                current = ""
                count = 0
    if current:
        chunks.append(current)
    return chunks


def _count_keywords(text: str, keywords: List[str]) -> Tuple[int, List[str]]:
    """统计关键词出现次数和具体命中的词"""
    count = 0
    hits = []
    for word in keywords:
        if word in text:
            count += text.count(word)
            hits.append(word)
    return count, hits


# ============== 维度1：开篇钩子强度 ==============

def analyze_opening_hook(text: str, first_n_chars: int = 100) -> Dict[str, Any]:
    """
    分析开篇钩子强度（前N字的吸引力）
    
    检测维度：
    - 是否有对话开局
    - 是否有冲突/悬念
    - 是否有异常事件
    - 信息密度
    
    Args:
        text: 章节正文
        first_n_chars: 取前多少字分析
        
    Returns:
        开篇钩子分析结果
    """
    # 取前N字
    first_part = text[:first_n_chars * 2]  # 多取一点，避免截断
    actual_chars = _count_chinese_chars(first_part)
    
    score = 0
    details = []
    
    # 1. 是否有对话开局（+2分）
    has_dialogue = "「" in first_part or "“" in first_part or '"' in first_part
    if has_dialogue:
        score += 2
        details.append("对话开局，有代入感")
    
    # 2. 是否有悬念词（+2分）
    suspense_count, suspense_hits = _count_keywords(first_part, HOOK_SIGNAL_WORDS[:20])  # 只取悬念类
    if suspense_count >= 2:
        score += 2
        details.append(f"悬念感强（命中{suspense_count}个悬念词）")
    elif suspense_count >= 1:
        score += 1
        details.append(f"有一定悬念（命中{suspense_count}个悬念词）")
    
    # 3. 是否有冲突/危险信号（+2分）
    conflict_count, conflict_hits = _count_keywords(first_part, HOOK_SIGNAL_WORDS[20:30])  # 冲突类
    if conflict_count >= 1:
        score += 2
        details.append("开局有冲突，张力足")
    
    # 4. 是否有异常事件（+2分）
    anomaly_count, anomaly_hits = _count_keywords(first_part, HOOK_SIGNAL_WORDS[30:])  # 异常类
    if anomaly_count >= 2:
        score += 2
        details.append("开局有异常，吸引人")
    elif anomaly_count >= 1:
        score += 1
        details.append("开局有异常信号")
    
    # 5. 信息密度（+2分）
    # 简单估算：标点符号数量 / 字数
    punctuation_count = len(re.findall(r'[，。！？；：、]', first_part))
    if actual_chars > 0:
        info_density = punctuation_count / actual_chars
        if info_density >= 0.15:
            score += 2
            details.append("信息密度高，节奏快")
        elif info_density >= 0.10:
            score += 1
            details.append("信息密度适中")
    
    # 限制最高分10分
    score = min(10, score)
    
    # 评价
    if score >= 8:
        comment = "开篇钩子很强，能快速抓住读者"
    elif score >= 6:
        comment = "开篇钩子不错，有一定吸引力"
    elif score >= 4:
        comment = "开篇钩子一般，还可以加强"
    else:
        comment = "开篇钩子偏弱，建议增加悬念或冲突"
    
    return {
        "score": score,
        "comment": comment,
        "details": details,
        "has_dialogue": has_dialogue,
        "suspense_count": suspense_count,
        "conflict_count": conflict_count,
        "actual_chars": actual_chars,
    }


# ============== 维度2：第1个爽点出现位置 ==============

def find_first_payoff_position(text: str) -> Dict[str, Any]:
    """
    查找第1个爽点出现的位置
    
    Args:
        text: 章节正文
        
    Returns:
        第一个爽点的位置信息
    """
    first_position = len(text)  # 默认在最后
    first_word = ""
    
    for word in PAYOFF_SIGNAL_WORDS:
        pos = text.find(word)
        if pos != -1 and pos < first_position:
            first_position = pos
            first_word = word
    
    # 换算成中文字数
    text_before = text[:first_position]
    char_position = _count_chinese_chars(text_before)
    
    total_chars = _count_chinese_chars(text)
    
    # 评价
    if char_position <= 300:
        comment = "爽点出现很早，开局就有爽感"
        score = 10
    elif char_position <= 500:
        comment = "爽点出现时机合适"
        score = 8
    elif char_position <= 1000:
        comment = "爽点出现偏晚，建议提前"
        score = 5
    elif char_position <= 2000:
        comment = "爽点出现太晚，读者可能已经弃书"
        score = 3
    else:
        comment = "本章没有明显的爽点信号，建议增加"
        score = 0
        char_position = -1
        first_word = ""
    
    return {
        "position": char_position,
        "total_chars": total_chars,
        "first_word": first_word,
        "score": score,
        "comment": comment,
    }


# ============== 维度3：章末钩子锋利度 ==============

def analyze_ending_hook(text: str, last_n_chars: int = 300) -> Dict[str, Any]:
    """
    分析章末钩子锋利度
    
    Args:
        text: 章节正文
        last_n_chars: 取最后多少字分析
        
    Returns:
        章末钩子分析结果
    """
    # 取最后N字
    last_part = text[-last_n_chars * 2:]
    actual_chars = _count_chinese_chars(last_part)
    
    score = 0
    details = []
    
    # 1. 是否有悬念词（+3分）
    suspense_count, suspense_hits = _count_keywords(last_part, HOOK_SIGNAL_WORDS[:20])
    if suspense_count >= 3:
        score += 3
        details.append("章末悬念很强")
    elif suspense_count >= 2:
        score += 2
        details.append("章末有悬念")
    elif suspense_count >= 1:
        score += 1
        details.append("章末有一定悬念")
    
    # 2. 是否有章末钩子信号（+3分）
    ending_count, ending_hits = _count_keywords(last_part, ENDING_HOOK_SIGNALS)
    if ending_count >= 3:
        score += 3
        details.append("章末钩子信号强")
    elif ending_count >= 2:
        score += 2
        details.append("有章末钩子")
    elif ending_count >= 1:
        score += 1
        details.append("有一定钩子信号")
    
    # 3. 是否以问号/省略号结尾（+2分）
    if text.rstrip().endswith("？") or text.rstrip().endswith("?"):
        score += 2
        details.append("以问句结尾，留下悬念")
    elif text.rstrip().endswith("……") or text.rstrip().endswith("..."):
        score += 2
        details.append("以省略号结尾，意犹未尽")
    elif text.rstrip().endswith("！") or text.rstrip().endswith("!"):
        score += 1
        details.append("以感叹号结尾，有冲击力")
    
    # 4. 是否有新发现/新人物（+2分）
    new_signal_count = len(re.findall(r'(出现|走来|来人|声音|身影)', last_part))
    if new_signal_count >= 2:
        score += 2
        details.append("章末有新元素出现")
    elif new_signal_count >= 1:
        score += 1
        details.append("章末有新元素")
    
    # 限制最高分10分
    score = min(10, score)
    
    # 评价
    if score >= 8:
        comment = "章末钩子很锋利，读者一定会翻下一章"
    elif score >= 6:
        comment = "章末钩子不错，有追读动力"
    elif score >= 4:
        comment = "章末钩子一般，还可以加强"
    else:
        comment = "章末钩子偏弱，建议增加悬念"
    
    return {
        "score": score,
        "comment": comment,
        "details": details,
        "suspense_count": suspense_count,
        "ending_signal_count": ending_count,
        "actual_chars": actual_chars,
    }


# ============== 维度4：信息释放节奏 ==============

def analyze_information_release(text: str, chunk_size: int = 100) -> Dict[str, Any]:
    """
    分析信息释放节奏（信息密度曲线）
    
    检测是否有背景倒灌（一次性解释太多世界观）
    
    Args:
        text: 章节正文
        chunk_size: 每块多少字
        
    Returns:
        信息释放节奏分析结果
    """
    chunks = _split_into_chunks(text, chunk_size)
    density_curve = []
    background_dump_positions = []
    
    for i, chunk in enumerate(chunks):
        # 简单估算信息密度：标点符号数 / 字数
        punctuation_count = len(re.findall(r'[，。！？；：、]', chunk))
        char_count = _count_chinese_chars(chunk)
        if char_count > 0:
            density = punctuation_count / char_count
        else:
            density = 0
        density_curve.append(round(density, 3))
        
        # 检测背景倒灌
        bg_count, bg_hits = _count_keywords(chunk, BACKGROUND_DUMP_SIGNALS)
        if bg_count >= 2:
            background_dump_positions.append({
                "position": i * chunk_size,
                "count": bg_count,
                "hits": bg_hits,
            })
    
    # 计算评分
    score = 10
    issues = []
    
    # 1. 检查是否有背景倒灌
    if background_dump_positions:
        first_dump = background_dump_positions[0]
        if first_dump["position"] < 500:
            score -= 3
            issues.append(f"前{first_dump['position']}字出现背景倒灌，影响节奏")
        else:
            score -= 1
            issues.append(f"第{first_dump['position']}字出现背景集中解释")
    
    # 2. 检查信息密度是否过于均匀（AI味）
    if len(density_curve) >= 5:
        avg_density = sum(density_curve) / len(density_curve)
        variance = sum((d - avg_density) ** 2 for d in density_curve) / len(density_curve)
        if variance < 0.001:  # 太均匀了
            score -= 2
            issues.append("信息密度过于均匀，节奏平淡")
    
    # 3. 检查开头信息密度
    if density_curve and density_curve[0] < 0.08:
        score -= 2
        issues.append("开篇信息密度太低，节奏太慢")
    
    score = max(0, score)
    
    # 评价
    if score >= 8:
        comment = "信息释放节奏很好，张弛有度"
    elif score >= 6:
        comment = "信息释放节奏不错"
    elif score >= 4:
        comment = "信息释放节奏一般，有优化空间"
    else:
        comment = "信息释放节奏有问题，建议调整"
    
    return {
        "score": score,
        "comment": comment,
        "density_curve": density_curve,
        "background_dump_positions": background_dump_positions,
        "issues": issues,
        "chunk_count": len(chunks),
    }


# ============== 维度5：人物辨识度 ==============

def analyze_character_recognition(text: str, first_n_chars: int = 500) -> Dict[str, Any]:
    """
    分析人物辨识度（主角是否在前N字立住）
    
    检测：
    - 主角是否在前500字出现
    - 是否有外貌/性格/气质描写
    - 主角名字出现次数
    
    Args:
        text: 章节正文
        first_n_chars: 取前多少字分析
        
    Returns:
        人物辨识度分析结果
    """
    first_part = text[:first_n_chars * 2]
    actual_chars = _count_chinese_chars(first_part)
    
    score = 0
    details = []
    
    # 1. 检测是否有人名（简单 heuristic：2-3个字的重复词）
    # 这里简化处理，统计"他/她"出现次数作为主角存在的信号
    pronoun_count = first_part.count("他") + first_part.count("她")
    if pronoun_count >= 5:
        score += 2
        details.append("主角出场频繁")
    elif pronoun_count >= 3:
        score += 1
        details.append("主角有出场")
    
    # 2. 检测是否有外貌/特征描写
    feature_count, feature_hits = _count_keywords(first_part, CHARACTER_FEATURE_SIGNALS)
    if feature_count >= 3:
        score += 3
        details.append("人物特征描写丰富，读者能记住")
    elif feature_count >= 2:
        score += 2
        details.append("有人物特征描写")
    elif feature_count >= 1:
        score += 1
        details.append("有少量人物特征描写")
    
    # 3. 检测是否有性格/行为描写
    behavior_signals = ["总是", "喜欢", "习惯", "平时", "一向", "为人", "性格"]
    behavior_count, behavior_hits = _count_keywords(first_part, behavior_signals)
    if behavior_count >= 2:
        score += 2
        details.append("有性格/行为描写")
    elif behavior_count >= 1:
        score += 1
        details.append("有少量性格描写")
    
    # 4. 检测是否有对话（通过对话展现人物）
    dialogue_count = first_part.count("「") + first_part.count("“")
    if dialogue_count >= 3:
        score += 2
        details.append("通过对话展现人物性格")
    elif dialogue_count >= 1:
        score += 1
        details.append("有对话")
    
    # 5. 检测主角是否有主动行为
    action_signals = ["说", "道", "想", "走", "看", "听", "笑", "皱眉"]
    action_count, action_hits = _count_keywords(first_part, action_signals)
    if action_count >= 5:
        score += 1
        details.append("主角有主动行为")
    
    # 限制最高分10分
    score = min(10, score)
    
    # 评价
    if score >= 8:
        comment = "人物辨识度很高，主角形象鲜明"
    elif score >= 6:
        comment = "人物辨识度不错，读者能记住主角"
    elif score >= 4:
        comment = "人物辨识度一般，主角形象不够鲜明"
    else:
        comment = "人物辨识度低，读者记不住主角"
    
    return {
        "score": score,
        "comment": comment,
        "details": details,
        "pronoun_count": pronoun_count,
        "feature_count": feature_count,
        "dialogue_count": dialogue_count,
        "actual_chars": actual_chars,
    }


# ============== 维度6：预估留存率 ==============

def estimate_retention_rate(
    opening_score: float,
    payoff_score: float,
    ending_score: float,
    info_score: float,
    character_score: float,
    platform: str = "general"
) -> Dict[str, Any]:
    """
    预估首章留存率
    
    基于各个维度的评分，综合计算预估留存率
    
    Args:
        opening_score: 开篇钩子评分（0-10）
        payoff_score: 爽点位置评分（0-10）
        ending_score: 章末钩子评分（0-10）
        info_score: 信息节奏评分（0-10）
        character_score: 人物辨识度评分（0-10）
        platform: 平台类型
        
    Returns:
        预估留存率
    """
    # 权重：开篇最重要，然后是爽点位置，然后是章末钩子
    weights = {
        "opening": 0.30,
        "payoff": 0.25,
        "ending": 0.20,
        "info": 0.15,
        "character": 0.10,
    }
    
    # 计算加权平均分（0-10）
    weighted_avg = (
        opening_score * weights["opening"] +
        payoff_score * weights["payoff"] +
        ending_score * weights["ending"] +
        info_score * weights["info"] +
        character_score * weights["character"]
    )
    
    # 转换为留存率（0-100%）
    # 基准：6分对应60%留存率，8分对应80%，10分对应95%
    base_retention = weighted_avg * 10
    
    # 平台调整
    platform_adjustment = {
        "tomato": -5,  # 番茄读者更挑剔，留存率低5%
        "fanqie": -5,
        "qidian": 0,
        "jjwxc": 5,  # 晋江读者更有耐心，留存率高5%
        "general": 0,
    }
    adjustment = platform_adjustment.get(platform, 0)
    
    retention_rate = max(0, min(100, base_retention + adjustment))
    
    # 基准对比
    benchmarks = {
        "tomato": 72,
        "fanqie": 72,
        "qidian": 68,
        "jjwxc": 75,
        "general": 70,
    }
    benchmark = benchmarks.get(platform, 70)
    
    difference = retention_rate - benchmark
    
    return {
        "retention_rate": round(retention_rate, 1),
        "benchmark": benchmark,
        "difference": round(difference, 1),
        "weighted_avg": round(weighted_avg, 2),
    }


# ============== 综合分析 ==============

def analyze_hook_power(
    chapter_text: str,
    platform: str = "general",
    is_first_chapter: bool = True
) -> Dict[str, Any]:
    """
    综合分析首章钩力
    
    Args:
        chapter_text: 章节正文
        platform: 平台类型
        is_first_chapter: 是否是首章
        
    Returns:
        钩力分析完整结果
    """
    total_chars = _count_chinese_chars(chapter_text)
    
    # 1. 开篇钩子强度
    opening_result = analyze_opening_hook(chapter_text)
    
    # 2. 第1个爽点位置
    payoff_result = find_first_payoff_position(chapter_text)
    
    # 3. 章末钩子锋利度
    ending_result = analyze_ending_hook(chapter_text)
    
    # 4. 信息释放节奏
    info_result = analyze_information_release(chapter_text)
    
    # 5. 人物辨识度
    character_result = analyze_character_recognition(chapter_text)
    
    # 6. 预估留存率
    retention_result = estimate_retention_rate(
        opening_result["score"],
        payoff_result["score"],
        ending_result["score"],
        info_result["score"],
        character_result["score"],
        platform
    )
    
    # 总体评分（0-100）
    overall_score = retention_result["retention_rate"]
    
    # 等级
    if overall_score >= 90:
        grade = "S"
    elif overall_score >= 80:
        grade = "A"
    elif overall_score >= 70:
        grade = "B"
    elif overall_score >= 60:
        grade = "C"
    else:
        grade = "D"
    
    # 改进建议
    suggestions = []
    if opening_result["score"] < 6:
        suggestions.append("加强开篇钩子，前100字增加悬念或冲突")
    if payoff_result["score"] < 6:
        suggestions.append("提前第一个爽点的出现位置，建议前500字内出现")
    if ending_result["score"] < 6:
        suggestions.append("加强章末钩子，结尾留下悬念")
    if info_result["score"] < 6:
        suggestions.append("优化信息释放节奏，避免背景倒灌")
    if character_result["score"] < 6:
        suggestions.append("加强人物特征描写，让读者记住主角")
    
    return {
        "overall_score": round(overall_score, 1),
        "grade": grade,
        "is_first_chapter": is_first_chapter,
        "platform": platform,
        "chapter_length": total_chars,
        
        "opening_hook": {
            "score": opening_result["score"],
            "comment": opening_result["comment"],
            "details": opening_result["details"],
        },
        
        "first_payoff": {
            "position": payoff_result["position"],
            "first_word": payoff_result["first_word"],
            "score": payoff_result["score"],
            "comment": payoff_result["comment"],
        },
        
        "ending_hook": {
            "score": ending_result["score"],
            "comment": ending_result["comment"],
            "details": ending_result["details"],
        },
        
        "information_release": {
            "score": info_result["score"],
            "comment": info_result["comment"],
            "density_curve": info_result["density_curve"],
            "background_dump_positions": info_result["background_dump_positions"],
            "issues": info_result["issues"],
        },
        
        "character_recognition": {
            "score": character_result["score"],
            "comment": character_result["comment"],
            "details": character_result["details"],
        },
        
        "estimated_retention": retention_result,
        "suggestions": suggestions,
    }
