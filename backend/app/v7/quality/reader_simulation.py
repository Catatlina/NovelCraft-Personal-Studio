"""
"读第一遍"模拟审查模块

模拟读者第一次阅读章节的感受和判断，从读者视角给出直观评价。

5个核心问题：
1. 开篇100字能抓住你吗？
2. 想立刻翻下一章吗？
3. 有没有让你共情的时刻？
4. 有没有哪段让你觉得"像AI写的"？
5. 如果能改一处让本章更好——改哪？

设计原则：
- 模拟真实读者的第一遍阅读感受
- 不做深度分析，只给直观判断
- 给出具体的改进建议
- 作为审稿的补充维度，不替代现有质量门禁
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class ReaderSimulationResult:
    """读者模拟审查结果"""
    overall_score: float  # 总体评分，0-100
    grade: str  # 等级：强烈推荐/推荐/一般/不推荐
    
    # 5个核心问题的回答
    opening_hook_score: float  # 开篇钩子评分，0-10
    opening_hook_comment: str  # 开篇钩子评价
    
    continuation_intent_score: float  # 追读意愿评分，0-10
    continuation_intent_comment: str  # 追读意愿评价
    
    empathy_moments: List[str]  # 共情时刻列表
    empathy_score: float  # 共情评分，0-10
    
    ai_smell_sections: List[str]  # 像AI写的段落
    ai_smell_severity: str  # AI味严重程度：无/轻微/中等/严重
    
    top_suggestion: str  # 最想改的一处
    suggestion_priority: str  # 建议优先级：高/中/低
    
    # 额外信息
    reader_persona: str  # 模拟的读者画像
    reading_time_estimate: str  # 预计阅读时间
    overall_comment: str  # 总体评价


# ============== Prompt 模板 ==============

READER_SIMULATION_PROMPT = """
你是一个普通的网文读者，正在第一次阅读这一章小说。
请完全以读者的视角，给出你最直观的感受和判断。
不要做专业分析，不要考虑写作技巧，就像你平时看小说一样。

读者画像：{reader_persona}

请回答以下5个问题：

1. 开篇100字能抓住你吗？
   - 给一个0-10分的分数
   - 简单说一句为什么

2. 看完这一章，你想立刻翻下一章吗？
   - 给一个0-10分的分数
   - 简单说一句为什么

3. 这一章里，有没有让你共情的时刻？
   - 如果有，列出1-3个具体的时刻
   - 如果没有，就说"没有"

4. 有没有哪段让你觉得"像AI写的"？
   - 如果有，简单描述是哪段，为什么觉得像AI
   - 如果没有，就说"没有"

5. 如果只能改一处让本章更好——你最想改哪？
   - 给出具体的建议
   - 说明为什么要改

最后，给这一章一个总体评分（0-100分），以及总体评价（一句话）。

请用JSON格式返回，结构如下：
{{
  "opening_hook_score": 0-10,
  "opening_hook_comment": "...",
  "continuation_intent_score": 0-10,
  "continuation_intent_comment": "...",
  "empathy_moments": ["...", "..."],
  "empathy_score": 0-10,
  "ai_smell_sections": ["..."],
  "ai_smell_severity": "无/轻微/中等/严重",
  "top_suggestion": "...",
  "suggestion_priority": "高/中/低",
  "overall_score": 0-100,
  "overall_comment": "..."
}}

章节内容：
---
{chapter_text}
---
"""


# ============== 读者画像预设 ==============

READER_PERSONAS = {
    "tomato_casual": """
番茄小说的普通读者，25岁左右，上班族，喜欢快节奏爽文。
每天通勤时看小说，追求爽感和放松，不喜欢太复杂的剧情。
对开篇要求很高，前三章抓不住就弃书。
喜欢打脸、升级、系统流等元素。
""".strip(),
    
    "qidian_veteran": """
起点中文网的老读者，30岁左右，看了十几年网文。
喜欢有深度的剧情和设定，对文笔有一定要求。
能接受慢热，但讨厌逻辑漏洞和降智。
对世界观设定、人物塑造比较挑剔。
""".strip(),
    
    "jjwxc_romance": """
晋江文学城的读者，20-30岁女性，喜欢言情小说。
注重感情线和人物互动，喜欢细腻的心理描写。
对文笔要求较高，讨厌油腻和爹味。
喜欢虐恋、甜宠、强强等各种言情类型。
""".strip(),
    
    "general": """
普通网文读者，没有特别偏好，什么类型都看一点。
追求故事性和可读性，只要好看就行。
对文笔要求不高，但也不能太烂。
""".strip(),
}


def get_reader_persona(platform: str = "general") -> str:
    """
    获取指定平台的读者画像
    
    Args:
        platform: 平台类型（tomato/qidian/jjwxc/general）
        
    Returns:
        读者画像描述
    """
    return READER_PERSONAS.get(platform, READER_PERSONAS["general"])


# ============== 结果解析 ==============

def parse_reader_simulation_result(data: Dict[str, Any]) -> ReaderSimulationResult:
    """
    解析AI返回的读者模拟结果
    
    Args:
        data: AI返回的JSON数据
        
    Returns:
        ReaderSimulationResult 对象
    """
    overall_score = float(data.get("overall_score", 50))
    
    # 确定等级
    if overall_score >= 85:
        grade = "强烈推荐"
    elif overall_score >= 70:
        grade = "推荐"
    elif overall_score >= 50:
        grade = "一般"
    else:
        grade = "不推荐"
    
    return ReaderSimulationResult(
        overall_score=overall_score,
        grade=grade,
        opening_hook_score=float(data.get("opening_hook_score", 5)),
        opening_hook_comment=str(data.get("opening_hook_comment", "")),
        continuation_intent_score=float(data.get("continuation_intent_score", 5)),
        continuation_intent_comment=str(data.get("continuation_intent_comment", "")),
        empathy_moments=data.get("empathy_moments", []),
        empathy_score=float(data.get("empathy_score", 5)),
        ai_smell_sections=data.get("ai_smell_sections", []),
        ai_smell_severity=str(data.get("ai_smell_severity", "无")),
        top_suggestion=str(data.get("top_suggestion", "")),
        suggestion_priority=str(data.get("suggestion_priority", "中")),
        reader_persona="",
        reading_time_estimate="",
        overall_comment=str(data.get("overall_comment", ""))
    )


# ============== 模拟函数（占位，实际需要调用AI） ==============

def simulate_reader_first_pass(
    chapter_text: str,
    platform: str = "general",
    reader_persona: str = None
) -> Dict[str, Any]:
    """
    模拟读者第一遍阅读的感受
    
    注意：这是一个占位函数，实际实现需要调用AI gateway。
    目前返回一个示例结果，用于测试和集成。
    
    Args:
        chapter_text: 章节正文
        platform: 平台类型，用于选择读者画像
        reader_persona: 自定义读者画像（可选，覆盖platform）
        
    Returns:
        读者模拟结果（字典格式）
    """
    # TODO: 实际实现需要调用 AI gateway
    # 目前返回一个示例结果，用于测试集成
    
    persona = reader_persona or get_reader_persona(platform)
    
    # 简单的示例结果（实际应该由AI生成）
    text_length = len(chapter_text)
    has_dialogue = "「" in chapter_text or "“" in chapter_text
    
    # 根据文本特征给出一个简单的示例评分
    base_score = 60
    if text_length > 2000:
        base_score += 10
    if has_dialogue:
        base_score += 5
    
    example_result = {
        "opening_hook_score": 7,
        "opening_hook_comment": "开头还行，能看下去，但不是特别惊艳",
        "continuation_intent_score": 6,
        "continuation_intent_comment": "有点好奇后面会发生什么，但也不是特别急",
        "empathy_moments": ["主角遇到困难的时候有点代入感"],
        "empathy_score": 6,
        "ai_smell_sections": [],
        "ai_smell_severity": "无",
        "top_suggestion": "建议增加更多冲突，让节奏更快一点",
        "suggestion_priority": "中",
        "overall_score": base_score,
        "overall_comment": "整体还可以，能看，但还不够吸引人"
    }
    
    return {
        "result": example_result,
        "reader_persona": persona,
        "text_length": text_length,
        "note": "这是示例结果，实际使用时需要调用AI生成"
    }
