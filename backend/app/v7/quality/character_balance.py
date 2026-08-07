"""
角色出场时间平衡检查模块

长篇常出现"前期重要角色中后期蒸发"的问题。
每N章自动统计每个角色的出场次数和字数占比，标记"连续N章未出场的重要角色"。

设计原则：
- 纯统计，不需要AI调用
- 支持自定义角色列表
- 支持自动提取候选角色名（简单 heuristic）
- 输出平衡报告，提醒作者哪些角色可能被遗忘
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import re


@dataclass
class CharacterStats:
    """单个角色的统计数据"""
    name: str  # 角色名
    appearance_count: int = 0  # 出场次数（出现的章节数）
    total_mentions: int = 0  # 总提及次数
    word_count: int = 0  # 涉及字数（近似估算）
    word_ratio: float = 0.0  # 字数占比
    first_appearance_chapter: int = 0  # 首次出场章节
    last_appearance_chapter: int = 0  # 最近一次出场章节
    chapters_since_last: int = 0  # 距离上次出场的章节数
    importance: str = "medium"  # 重要性等级：high/medium/low
    forget_risk: str = "low"  # 遗忘风险等级：high/medium/low


@dataclass
class CharacterBalanceResult:
    """角色平衡检查结果"""
    total_characters: int  # 总角色数
    total_chapters: int  # 总章节数
    
    high_risk_characters: List[CharacterStats]  # 高遗忘风险角色
    medium_risk_characters: List[CharacterStats]  # 中遗忘风险角色
    low_risk_characters: List[CharacterStats]  # 低遗忘风险角色
    
    balance_score: float  # 平衡评分（0-100）
    has_warnings: bool  # 是否有警告
    
    suggestions: List[str]  # 改进建议
    character_stats: Dict[str, CharacterStats]  # 所有角色的统计数据


# ============== 常见非人名词（用于过滤） ==============

COMMON_NON_NAME_WORDS = {
    # 代词
    "他", "她", "它", "他们", "她们", "它们",
    "你", "我", "我们", "你们", "大家", "众人",
    "自己", "本人", "人家", "别人", "旁人",
    
    # 称谓
    "先生", "小姐", "女士", "夫人", "太太",
    "爷爷", "奶奶", "爸爸", "妈妈", "哥哥", "弟弟", "姐姐", "妹妹",
    "叔叔", "阿姨", "舅舅", "舅妈", "姑姑", "姑父",
    "师傅", "徒弟", "学生", "老师", "同学",
    "老板", "员工", "经理", "总监", "董事长",
    "国王", "王子", "公主", "皇后", "皇帝", "大臣",
    "将军", "士兵", "队长", "团长", "旅长", "师长",
    "掌门", "长老", "弟子", "徒弟", "门主",
    "少爷", "小姐", "丫鬟", "仆人", "管家",
    
    # 身份/职业
    "医生", "护士", "警察", "律师", "法官",
    "司机", "厨师", "服务员", "收银员",
    "学生", "老师", "教授", "博士", "硕士",
    "作家", "画家", "歌手", "演员", "导演",
    
    # 时间/地点
    "今天", "明天", "昨天", "现在", "刚才",
    "这里", "那里", "哪里", "这边", "那边",
    "上面", "下面", "里面", "外面", "前面", "后面",
    
    # 常见词
    "什么", "怎么", "为什么", "难道", "莫非",
    "知道", "明白", "清楚", "了解",
    "觉得", "感觉", "认为", "以为",
    "说道", "说道", "回答", "问道",
    "看着", "望着", "盯着", "看着",
    "走了", "来了", "出去", "进来",
    "时候", "地方", "事情", "东西",
    "因为", "所以", "但是", "然而",
    "如果", "假如", "要是", "只要",
    "已经", "正在", "将要", "马上",
    "一个", "两个", "三个", "几个",
    "非常", "十分", "特别", "相当",
    "可以", "能够", "应该", "必须",
}


# ============== 工具函数 ==============

def _count_chinese_chars(text: str) -> int:
    """统计中文字符数"""
    return len(re.findall(r'[\u4e00-\u9fff]', text))


def extract_candidate_characters(text: str, min_length: int = 2, max_length: int = 3) -> List[str]:
    """
    从文本中提取候选角色名（简单 heuristic）
    
    注意：这是一个简单的启发式方法，准确率有限。
    建议在实际使用中传入明确的角色列表。
    
    方法：
    1. 统计所有2-3个字的重复词
    2. 过滤掉常见非人名词
    3. 按出现次数排序，取前N个
    
    Args:
        text: 文本内容
        min_length: 最小词长
        max_length: 最大词长
        
    Returns:
        候选角色名列表
    """
    # 简单的 n-gram 统计
    word_counts = {}
    
    # 只提取中文字符
    chinese_text = re.findall(r'[\u4e00-\u9fff]', text)
    chinese_text = ''.join(chinese_text)
    
    # 统计 n-gram
    for n in range(min_length, max_length + 1):
        for i in range(len(chinese_text) - n + 1):
            word = chinese_text[i:i+n]
            # 过滤掉包含常见字开头/结尾的
            if word[0] in {'的', '了', '是', '在', '有', '和', '与', '及'}:
                continue
            if word[-1] in {'的', '了', '是', '在', '有', '和', '与', '及'}:
                continue
            word_counts[word] = word_counts.get(word, 0) + 1
    
    # 过滤掉出现次数太少的
    candidates = [(word, count) for word, count in word_counts.items() if count >= 3]
    
    # 过滤掉常见非人名词
    candidates = [(word, count) for word, count in candidates if word not in COMMON_NON_NAME_WORDS]
    
    # 按出现次数排序
    candidates.sort(key=lambda x: x[1], reverse=True)
    
    # 取前20个
    return [word for word, count in candidates[:20]]


def estimate_character_word_count(text: str, character_name: str) -> int:
    """
    估算角色涉及的字数（近似）
    
    简单估算：角色名出现的位置前后各50字算作该角色的戏份
    这只是一个粗略估算，不是精确值。
    
    Args:
        text: 章节文本
        character_name: 角色名
        
    Returns:
        估算的字数
    """
    total_chars = 0
    pos = 0
    
    while True:
        pos = text.find(character_name, pos)
        if pos == -1:
            break
        
        # 前后各50字
        start = max(0, pos - 50)
        end = min(len(text), pos + len(character_name) + 50)
        segment = text[start:end]
        
        # 统计中文字数
        char_count = _count_chinese_chars(segment)
        total_chars += char_count
        
        pos += len(character_name)
    
    # 去重（避免重叠区域重复计算）
    # 简单处理：除以一个系数来近似去重
    total_chars = int(total_chars * 0.7)
    
    return total_chars


# ============== 核心分析函数 ==============

def analyze_character_balance(
    chapters: List[str],
    character_list: List[str] = None,
    current_chapter: int = None,
    high_risk_threshold: int = 10,
    medium_risk_threshold: int = 5,
    auto_extract: bool = True
) -> CharacterBalanceResult:
    """
    分析角色出场平衡
    
    Args:
        chapters: 章节文本列表（按章节顺序）
        character_list: 角色名列表（可选，如果不提供则自动提取）
        current_chapter: 当前章节号（可选，默认是最后一章）
        high_risk_threshold: 高风险阈值（多少章没出场算高风险）
        medium_risk_threshold: 中风险阈值
        auto_extract: 是否自动提取候选角色（当没有角色列表时）
        
    Returns:
        角色平衡分析结果
    """
    total_chapters = len(chapters)
    if total_chapters == 0:
        return CharacterBalanceResult(
            total_characters=0,
            total_chapters=0,
            high_risk_characters=[],
            medium_risk_characters=[],
            low_risk_characters=[],
            balance_score=100,
            has_warnings=False,
            suggestions=[],
            character_stats={}
        )
    
    if current_chapter is None:
        current_chapter = total_chapters
    
    # 确定角色列表
    if character_list is None or len(character_list) == 0:
        if auto_extract:
            # 从所有章节中提取候选角色
            all_text = "\n".join(chapters)
            character_list = extract_candidate_characters(all_text)
        else:
            character_list = []
    
    # 统计每个角色的出场情况
    character_stats = {}
    
    for name in character_list:
        stats = CharacterStats(name=name)
        character_stats[name] = stats
    
    total_word_count = 0
    
    for chapter_idx, chapter_text in enumerate(chapters, 1):
        chapter_word_count = _count_chinese_chars(chapter_text)
        total_word_count += chapter_word_count
        
        for name in character_list:
            if name in chapter_text:
                stats = character_stats[name]
                
                # 出场次数 +1
                stats.appearance_count += 1
                
                # 提及次数
                mention_count = chapter_text.count(name)
                stats.total_mentions += mention_count
                
                # 估算涉及字数
                word_count = estimate_character_word_count(chapter_text, name)
                stats.word_count += word_count
                
                # 更新首次/最近出场章节
                if stats.first_appearance_chapter == 0:
                    stats.first_appearance_chapter = chapter_idx
                stats.last_appearance_chapter = chapter_idx
    
    # 计算字数占比和距离上次出场的章节数
    for name, stats in character_stats.items():
        if total_word_count > 0:
            stats.word_ratio = stats.word_count / total_word_count
        
        # 距离上次出场的章节数
        if stats.last_appearance_chapter > 0:
            stats.chapters_since_last = current_chapter - stats.last_appearance_chapter
        else:
            stats.chapters_since_last = current_chapter
        
        # 判断重要性（基于出场次数和字数占比）
        if stats.appearance_count >= total_chapters * 0.5 or stats.word_ratio >= 0.10:
            stats.importance = "high"
        elif stats.appearance_count >= total_chapters * 0.2 or stats.word_ratio >= 0.03:
            stats.importance = "medium"
        else:
            stats.importance = "low"
        
        # 计算遗忘风险
        if stats.importance == "high":
            # 重要角色：5章没出场算中风险，10章没出场算高风险
            if stats.chapters_since_last >= high_risk_threshold:
                stats.forget_risk = "high"
            elif stats.chapters_since_last >= medium_risk_threshold:
                stats.forget_risk = "medium"
            else:
                stats.forget_risk = "low"
        elif stats.importance == "medium":
            # 中等角色：10章没出场算中风险，15章没出场算高风险
            if stats.chapters_since_last >= high_risk_threshold + 5:
                stats.forget_risk = "high"
            elif stats.chapters_since_last >= medium_risk_threshold + 5:
                stats.forget_risk = "medium"
            else:
                stats.forget_risk = "low"
        else:
            # 次要角色：15章没出场算中风险，20章没出场算高风险
            if stats.chapters_since_last >= high_risk_threshold + 10:
                stats.forget_risk = "high"
            elif stats.chapters_since_last >= medium_risk_threshold + 10:
                stats.forget_risk = "medium"
            else:
                stats.forget_risk = "low"
    
    # 分类
    high_risk = [stats for stats in character_stats.values() if stats.forget_risk == "high"]
    medium_risk = [stats for stats in character_stats.values() if stats.forget_risk == "medium"]
    low_risk = [stats for stats in character_stats.values() if stats.forget_risk == "low"]
    
    # 按重要性和未出场章节数排序
    importance_order = {"high": 0, "medium": 1, "low": 2}
    high_risk.sort(key=lambda x: (importance_order[x.importance], -x.chapters_since_last))
    medium_risk.sort(key=lambda x: (importance_order[x.importance], -x.chapters_since_last))
    
    # 计算平衡评分
    balance_score = 100
    
    # 高风险角色扣分
    for stats in high_risk:
        if stats.importance == "high":
            balance_score -= 15
        elif stats.importance == "medium":
            balance_score -= 8
        else:
            balance_score -= 3
    
    # 中风险角色扣分
    for stats in medium_risk:
        if stats.importance == "high":
            balance_score -= 8
        elif stats.importance == "medium":
            balance_score -= 4
        else:
            balance_score -= 1
    
    balance_score = max(0, min(100, balance_score))
    
    # 生成建议
    suggestions = []
    
    if high_risk:
        high_importance_high_risk = [s for s in high_risk if s.importance == "high"]
        if high_importance_high_risk:
            names = "、".join([s.name for s in high_importance_high_risk[:3]])
            suggestions.append(f"⚠️ 重要角色{names}已经{high_importance_high_risk[0].chapters_since_last}章没出场了，建议尽快安排出场")
    
    if medium_risk:
        medium_importance_medium_risk = [s for s in medium_risk if s.importance == "medium"]
        if medium_importance_medium_risk:
            names = "、".join([s.name for s in medium_importance_medium_risk[:3]])
            suggestions.append(f"角色{names}已经{medium_importance_medium_risk[0].chapters_since_last}章没出场了，注意不要被读者遗忘")
    
    if not high_risk and not medium_risk:
        suggestions.append("✅ 角色出场平衡良好，没有遗忘风险")
    
    has_warnings = len(high_risk) > 0 or len(medium_risk) > 0
    
    return CharacterBalanceResult(
        total_characters=len(character_list),
        total_chapters=total_chapters,
        high_risk_characters=high_risk,
        medium_risk_characters=medium_risk,
        low_risk_characters=low_risk,
        balance_score=balance_score,
        has_warnings=has_warnings,
        suggestions=suggestions,
        character_stats=character_stats
    )


# ============== 单章快速检查 ==============

def check_single_chapter_characters(
    chapter_text: str,
    character_list: List[str],
    previous_chapter_stats: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    检查单章的角色出场情况（用于每章生成后快速检查）
    
    Args:
        chapter_text: 章节文本
        character_list: 角色列表
        previous_chapter_stats: 之前的统计数据（可选）
        
    Returns:
        单章角色出场检查结果
    """
    appearing_characters = []
    missing_characters = []
    
    for name in character_list:
        if name in chapter_text:
            appearing_characters.append(name)
        else:
            missing_characters.append(name)
    
    return {
        "appearing_characters": appearing_characters,
        "missing_characters": missing_characters,
        "appearing_count": len(appearing_characters),
        "missing_count": len(missing_characters),
        "total_count": len(character_list),
    }
