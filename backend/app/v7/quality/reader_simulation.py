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

from dataclasses import asdict, dataclass
import hashlib
from typing import List, Dict, Any

from ...gateway import complete


class ReaderSimulationError(RuntimeError):
    """The reader simulation could not produce a real, structured result."""


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
    if not isinstance(data, dict):
        raise ReaderSimulationError("reader simulation provider output must be an object")

    def validated_numeric(name: str, maximum: float) -> float:
        if name not in data:
            raise ReaderSimulationError(f"reader simulation output missing {name}")
        try:
            value = float(data[name])
        except (TypeError, ValueError) as exc:
            raise ReaderSimulationError(f"reader simulation output has invalid {name}") from exc
        if not 0 <= value <= maximum:
            raise ReaderSimulationError(f"reader simulation output has out-of-range {name}")
        return value

    def text(name: str) -> str:
        value = data.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ReaderSimulationError(f"reader simulation output missing {name}")
        return value.strip()

    def string_list(name: str) -> list[str]:
        value = data.get(name)
        if not isinstance(value, list):
            raise ReaderSimulationError(f"reader simulation output has invalid {name}")
        return [str(item).strip() for item in value if str(item).strip()][:5]

    overall_score = validated_numeric("overall_score", 100)
    
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
        opening_hook_score=validated_numeric("opening_hook_score", 10),
        opening_hook_comment=text("opening_hook_comment"),
        continuation_intent_score=validated_numeric("continuation_intent_score", 10),
        continuation_intent_comment=text("continuation_intent_comment"),
        empathy_moments=string_list("empathy_moments"),
        empathy_score=validated_numeric("empathy_score", 10),
        ai_smell_sections=string_list("ai_smell_sections"),
        ai_smell_severity=text("ai_smell_severity"),
        top_suggestion=text("top_suggestion"),
        suggestion_priority=text("suggestion_priority"),
        reader_persona="",
        reading_time_estimate="",
        overall_comment=text("overall_comment")
    )


# ============== 真实 AI 读者模拟 ==============

def simulate_reader_first_pass(
    chapter_text: str,
    platform: str = "general",
    reader_persona: str = None,
    *,
    project_id: str | None = None,
    user_id: str | None = None,
    client_mutation_id: str | None = None,
) -> Dict[str, Any]:
    """
    模拟读者第一遍阅读的感受
    
    结果必须来自统一 AI Gateway。缺少项目作用域或 Provider 失败时直接
    抛错，调用方不能把失败伪装成一份示例评分。
    
    Args:
        chapter_text: 章节正文
        platform: 平台类型，用于选择读者画像
        reader_persona: 自定义读者画像（可选，覆盖platform）
        project_id: AI 调用和预算记账所需的项目作用域
        user_id: 可选的预算/审计用户
        
    Returns:
        读者模拟结果（字典格式）
    """
    if not project_id:
        raise ReaderSimulationError("reader simulation requires project_id for AI accounting")
    if not isinstance(chapter_text, str) or not chapter_text.strip():
        raise ReaderSimulationError("reader simulation requires chapter text")
    if len(chapter_text) > 24000:
        raise ReaderSimulationError("reader simulation chapter text exceeds the 24000-character limit")

    persona = str(reader_persona or get_reader_persona(platform)).strip()[:3000]
    mutation_id = client_mutation_id or (
        "reader-simulation:" + hashlib.sha256(
            f"{project_id}:{platform}:{persona}:{chapter_text}".encode("utf-8")
        ).hexdigest()
    )
    output = complete(
        run_id=None,
        node_key="reader_simulation",
        project_id=str(project_id),
        user_id=user_id,
        task_type="reader_simulation",
        prompt_name="v7.reader.simulation",
        variables={
            "reader_persona": persona,
            "chapter_text": chapter_text,
            "platform": platform,
        },
        client_mutation_id=mutation_id,
    )
    parsed = parse_reader_simulation_result(output)
    parsed.reader_persona = persona
    parsed.reading_time_estimate = f"约 {max(1, round(len(chapter_text) / 500))} 分钟"
    return {
        "result": asdict(parsed),
        "reader_persona": persona,
        "text_length": len(chapter_text),
        "provenance": {
            "gateway": "v6.complete",
            "task_type": "reader_simulation",
            "prompt_name": "v7.reader.simulation",
            "client_mutation_id": mutation_id,
        },
    }
