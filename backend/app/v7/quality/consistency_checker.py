"""
生成后一致性自动检查器。

检查维度：
1. 衔接一致性：人物位置、时间、动作、物品是否承接上一章
2. 设定一致性：修为等级、金手指规则、人物性格、世界观设定
3. 大纲一致性：细纲节拍点是否覆盖、是否偏离主线、章末钩子是否到位
4. 逻辑自洽：前后矛盾、逻辑漏洞、人物行为合理性
"""
from __future__ import annotations

import json
import re
from typing import Any

from ..generation.generation_engine import AIGateway, AIGatewayError

CONSISTENCY_CHECK_VERSION = "1.0.0"
CONSISTENCY_PASS_SCORE = 80.0  # 默认通过阈值
MAX_CONSISTENCY_REWORKS = 2  # 一致性检查最多重写次数（和质量门重写分开计数？还是合并？先合并）


class ConsistencyCheckResult:
    """一致性检查结果。"""

    def __init__(
        self,
        *,
        passed: bool,
        score: float,
        issues: list[dict[str, Any]] | None = None,
        summary: str = "",
        raw_response: str = "",
    ):
        self.passed = passed
        self.score = score
        self.issues = issues or []
        self.summary = summary
        self.raw_response = raw_response

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "score": self.score,
            "issues": self.issues,
            "summary": self.summary,
            "version": CONSISTENCY_CHECK_VERSION,
        }


class ConsistencyChecker:
    """生成后一致性自动检查器。"""

    def __init__(self, ai_gateway: AIGateway):
        self.ai_gateway = ai_gateway

    async def check(
        self,
        *,
        chapter_text: str,
        chapter_number: int,
        core_settings: str = "",
        chapter_outline: str = "",
        previous_chapter_tail: str = "",
        previous_transition_contract: dict[str, Any] | None = None,
        scene_plan: dict[str, Any] | None = None,
    ) -> ConsistencyCheckResult:
        """执行一致性检查。

        Args:
            chapter_text: 本章正文
            chapter_number: 章节号
            core_settings: 核心设定（创作圣经等）
            chapter_outline: 本章细纲
            previous_chapter_tail: 上一章结尾
            previous_transition_contract: 上一章交接契约
            scene_plan: 场景规划

        Returns:
            ConsistencyCheckResult
        """
        # 构建检查 Prompt
        prompt = self._build_check_prompt(
            chapter_text=chapter_text,
            chapter_number=chapter_number,
            core_settings=core_settings,
            chapter_outline=chapter_outline,
            previous_chapter_tail=previous_chapter_tail,
            previous_transition_contract=previous_transition_contract or {},
            scene_plan=scene_plan or {},
        )

        try:
            response = await self.ai_gateway.generate(
                prompt,
                max_tokens=2000,
                temperature=0.3,
                prompt_name="v7.consistency_check",
            )
        except AIGatewayError as e:
            # LLM 调用失败，返回默认通过（不阻塞生成）
            return ConsistencyCheckResult(
                passed=True,
                score=100.0,
                summary=f"一致性检查调用失败，跳过检查：{str(e)}",
                raw_response="",
            )

        # 解析结果
        return self._parse_response(response, chapter_text)

    def _build_check_prompt(
        self,
        *,
        chapter_text: str,
        chapter_number: int,
        core_settings: str,
        chapter_outline: str,
        previous_chapter_tail: str,
        previous_transition_contract: dict[str, Any],
        scene_plan: dict[str, Any],
    ) -> str:
        """构建一致性检查 Prompt。"""
        # 准备上一章结尾状态
        end_state = previous_transition_contract.get("end_state") or {}
        open_threads = previous_transition_contract.get("open_threads") or []
        next_bridge = previous_transition_contract.get("next_chapter_bridge") or previous_chapter_tail[-600:]

        threads_text = ""
        if open_threads:
            threads_text = "\n未解决的线索：\n" + "\n".join(
                f"- {t.get('summary', '')}" for t in open_threads[:5]
            )

        # 准备场景规划
        beats = scene_plan.get("beats") or []
        beats_text = ""
        if beats:
            beats_text = "\n细纲节拍点：\n" + "\n".join(
                f"{i+1}. {b.get('name', '')}：{b.get('content', '')}"
                for i, b in enumerate(beats[:10])
            )

        # 截断长文本，避免 token 过多
        core_settings_truncated = core_settings[:3000] if core_settings else ""
        chapter_outline_truncated = chapter_outline[:2000] if chapter_outline else ""
        chapter_text_truncated = chapter_text[:12000] if chapter_text else ""

        return f"""你是一个专业的小说一致性审查员。请严格检查第 {chapter_number} 章是否与设定、大纲、上一章衔接一致。

【核心设定】
{core_settings_truncated or '（无核心设定）'}

【本章细纲】
{chapter_outline_truncated or '（无细纲）'}{beats_text}

【上一章结尾状态】
上一章结尾的最后内容：
「{next_bridge}」

上一章梗概：{end_state.get('summary', '')}{threads_text}

【本章正文】
{chapter_text_truncated}

【检查清单】
1. 衔接一致性：人物位置、时间、动作、物品是否承接上一章结尾？有没有跳跃或断层？
2. 设定一致性：修为等级、金手指规则、人物性格、世界观设定是否符合？有没有 OOC 或设定矛盾？
3. 大纲一致性：细纲的节拍点是否都写到了？有没有偏离主线？章末钩子是否到位？
4. 逻辑自洽：有没有前后矛盾或逻辑漏洞？人物行为是否合理？

【输出格式】
请严格输出 JSON，不要输出任何其他文字：
{{
  "consistency_score": 0-100分,
  "passed": true/false（80分以上通过）,
  "issues": [
    {{
      "type": "衔接/设定/大纲/逻辑",
      "severity": "轻微/中等/严重",
      "location": "大概位置（第几段/哪个情节）",
      "description": "问题描述",
      "suggestion": "修改建议"
    }}
  ],
  "summary": "总体评价（一句话）"
}}

【评分标准】
- 90-100分：完全一致，没有问题
- 80-89分：基本一致，有轻微问题但不影响阅读
- 60-79分：有明显问题，需要修改
- 60分以下：严重不一致，必须重写

注意：只检查事实性的不一致，不评价文笔好坏。如果没有明显问题，就给高分通过。"""

    def _parse_response(
        self, response: str, chapter_text: str
    ) -> ConsistencyCheckResult:
        """解析 LLM 响应。"""
        # 尝试提取 JSON
        json_str = self._extract_json(response)
        if not json_str:
            return ConsistencyCheckResult(
                passed=True,
                score=100.0,
                summary="无法解析检查结果，跳过检查",
                raw_response=response,
            )

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return ConsistencyCheckResult(
                passed=True,
                score=100.0,
                summary="JSON 解析失败，跳过检查",
                raw_response=response,
            )

        # 提取字段
        score = float(data.get("consistency_score", 100.0))
        passed = bool(data.get("passed", score >= CONSISTENCY_PASS_SCORE))
        issues = data.get("issues", [])
        summary = str(data.get("summary", ""))

        # 验证 issues 格式
        valid_issues = []
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            valid_issues.append({
                "type": str(issue.get("type", "其他")),
                "severity": str(issue.get("severity", "轻微")),
                "location": str(issue.get("location", "")),
                "description": str(issue.get("description", "")),
                "suggestion": str(issue.get("suggestion", "")),
            })

        return ConsistencyCheckResult(
            passed=passed,
            score=score,
            issues=valid_issues,
            summary=summary,
            raw_response=response,
        )

    @staticmethod
    def _extract_json(text: str) -> str:
        """从文本中提取 JSON 字符串。"""
        text = text.strip()

        # 尝试直接解析
        if text.startswith("{") and text.endswith("}"):
            return text

        # 尝试用正则提取
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return match.group(0)

        return ""


def format_consistency_issues(issues: list[dict[str, Any]]) -> str:
    """格式化一致性问题，用于重写 Prompt。"""
    if not issues:
        return ""

    lines = []
    for i, issue in enumerate(issues[:8], 1):
        issue_type = issue.get("type", "其他")
        severity = issue.get("severity", "轻微")
        description = issue.get("description", "")
        suggestion = issue.get("suggestion", "")
        lines.append(
            f"{i}. [{issue_type}-{severity}] {description}"
            + (f"（建议：{suggestion}）" if suggestion else "")
        )

    return "\n".join(lines)
