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

CONSISTENCY_CHECK_VERSION = "1.1.0"
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
        chapter_outline: Any = "",
        previous_chapter_tail: str = "",
        previous_transition_contract: dict[str, Any] | None = None,
        scene_plan: dict[str, Any] | None = None,
        active_rules: list[dict[str, Any]] | dict[str, Any] | None = None,
        chapter_title: str = "",
        previous_chapter_title: str = "",
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
            active_rules=active_rules or [],
            chapter_title=chapter_title,
            previous_chapter_title=previous_chapter_title,
        )

        try:
            response = await self.ai_gateway.generate(
                prompt,
                max_tokens=2000,
                temperature=0.3,
                prompt_name="v7.consistency_check",
            )
        except AIGatewayError as e:
            # Provider failure is an unverified review, never a pass.  The
            # director persists the draft as needs_review/needs_rewrite.
            return ConsistencyCheckResult(
                passed=False,
                score=0.0,
                issues=[{
                    "type": "审阅执行",
                    "severity": "严重",
                    "location": "一致性检查调用",
                    "description": f"一致性检查调用失败，结果未验证：{str(e)}",
                    "suggestion": "修复 AI Provider 后重新执行一致性检查",
                }],
                summary=f"一致性检查调用失败，跳过检查：{str(e)}",
                raw_response="",
            )

        # AIGateway.generate returns a usage envelope whose provider text is
        # stored under ``text``.  Older test doubles returned a bare string;
        # _parse_response accepts both so the real provider path and existing
        # seams share one strict parser.
        result = self._parse_response(response, chapter_text)
        if chapter_number <= 1 and not previous_chapter_tail and not previous_transition_contract:
            # A new novel has no previous chapter by definition. Do not let a
            # Provider turn that missing input into a cross-chapter blocker;
            # the first chapter is checked against its own outline, rules and
            # opening pressure instead.
            previous_missing_markers = (
                "上一章",
                "上章",
                "前章",
            )
            absence_markers = (
                "为空",
                "没有",
                "无",
                "无法验证",
                "缺失",
                "未提供",
            )
            retained: list[dict[str, Any]] = []
            removed = False
            for issue in result.issues:
                description = str(issue.get("description") or "")
                if (
                    any(marker in description for marker in previous_missing_markers)
                    and any(marker in description for marker in absence_markers)
                ):
                    removed = True
                    continue
                retained.append(issue)
            if removed:
                result.issues = retained
                result.passed = (
                    result.score >= CONSISTENCY_PASS_SCORE
                    and not any(
                        str(item.get("severity") or "") in {"严重", "高", "high", "critical"}
                        for item in retained
                    )
                )
                result.summary = (
                    f"首章无上一章可承接；已忽略缺失前章输入，保留本章内部一致性检查。"
                    f" {result.summary}"
                ).strip()
        return result

    def _build_check_prompt(
        self,
        *,
        chapter_text: str,
        chapter_number: int,
        core_settings: str,
        chapter_outline: Any,
        previous_chapter_tail: str,
        previous_transition_contract: dict[str, Any],
        scene_plan: dict[str, Any],
        active_rules: list[dict[str, Any]] | dict[str, Any],
        chapter_title: str,
        previous_chapter_title: str,
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

        # 截断长文本，避免 token 过多.  The caller supplies structured
        # plot_brief data, while the prompt contract is text; serialise it
        # explicitly instead of slicing a dict (which used to abort every
        # consistency check before the provider call).
        if isinstance(chapter_outline, (dict, list)):
            chapter_outline_text = json.dumps(chapter_outline, ensure_ascii=False)
        else:
            chapter_outline_text = str(chapter_outline or "")
        core_settings_truncated = core_settings[:3000] if core_settings else ""
        chapter_outline_truncated = chapter_outline_text[:2000]
        chapter_text_truncated = chapter_text[:12000] if chapter_text else ""
        if isinstance(active_rules, dict):
            active_rules_text = json.dumps(active_rules, ensure_ascii=False)[:3000]
        else:
            active_rules_text = "\n".join(
                f"- {item.get('name') or item.get('key') or '规则'}：{item.get('description') or item.get('instruction') or item}"
                if isinstance(item, dict) else f"- {item}"
                for item in active_rules[:12]
            )

        first_chapter_note = (
            "这是第1章，也是新书开端；没有上一章结尾是正常输入，不得因为‘上一章为空/无法验证’判定跨章失败。"
            "本章应改查自身开场锚点、细纲节拍、人物动机、规则来源和具体风险。"
            if chapter_number <= 1
            else "本章不是第一章，必须严格承接上一章已落地的动作、地点、人物状态和未决线索。"
        )
        return f"""你是一个专业的小说一致性审查员。请严格检查第 {chapter_number} 章是否与设定、大纲、上一章衔接一致。

【章节范围】
{first_chapter_note}

【核心设定】
{core_settings_truncated or '（无核心设定）'}

【本章细纲】
{chapter_outline_truncated or '（无细纲）'}{beats_text}

【上一章结尾状态】
上一章结尾的最后内容：
「{next_bridge}」

上一章梗概：{end_state.get('summary', '')}{threads_text}

【章节标题】
上一章：{previous_chapter_title or end_state.get('title', '') or '（未知）'}
本章：{chapter_title or '（未知）'}

【不可随意改变的规则账本】
{active_rules_text or '（无额外规则）'}

【本章正文】
{chapter_text_truncated}

【检查清单】
1. 衔接一致性：第1章检查自身开场锚点和内部动作链；后续章节检查人物位置、时间、动作、物品是否承接上一章结尾，不能把第一章缺少上一章当成问题。
2. 设定一致性：修为等级、金手指规则、人物性格、世界观设定是否符合？有没有 OOC 或设定矛盾？
3. 大纲一致性：细纲的节拍点是否都写到了？有没有偏离主线？章末钩子是否到位？
4. 逻辑自洽：有没有前后矛盾或逻辑漏洞？人物行为是否合理？
5. 跨章语义：本章开头是否从上一章最后动作/地点/人物状态自然接起？如果标题沿用同一情节基名，却直接切到另一地点、另一组人物或另一条因果链，必须判定为严重问题。
6. 规则账本：能力触发条件、冷却、代价、物品状态和人物位置是否被无依据地重置？

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
  "opening_anchor": {{"matched": true/false, "evidence": "..."}},
  "parallel_version": {{"suspected": true/false, "evidence": "..."}},
  "summary": "总体评价（一句话）"
}}

【评分标准】
- 90-100分：完全一致，没有问题
- 80-89分：基本一致，有轻微问题但不影响阅读
- 60-79分：有明显问题，需要修改
- 60分以下：严重不一致，必须重写

注意：只检查事实性的不一致，不评价文笔好坏。如果没有明显问题，就给高分通过。"""

    def _parse_response(
        self, response: Any, chapter_text: str
    ) -> ConsistencyCheckResult:
        """解析 LLM 响应。"""
        if isinstance(response, dict):
            response_text = response.get("text") or response.get("content") or ""
        else:
            response_text = response or ""
        response_text = str(response_text)
        # 尝试提取 JSON
        json_str = self._extract_json(response_text)
        if not json_str:
            return ConsistencyCheckResult(
                passed=False,
                score=0.0,
                issues=[{
                    "type": "审阅执行",
                    "severity": "严重",
                    "location": "一致性检查响应",
                    "description": "无法解析一致性检查 JSON，结果未验证",
                    "suggestion": "修复 Provider 输出格式后重新执行",
                }],
                summary="无法解析检查结果，不能放行",
                raw_response=response_text,
            )

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return ConsistencyCheckResult(
                passed=False,
                score=0.0,
                issues=[{
                    "type": "审阅执行",
                    "severity": "严重",
                    "location": "一致性检查响应",
                    "description": "一致性检查 JSON 解析失败，结果未验证",
                    "suggestion": "修复 Provider 输出格式后重新执行",
                }],
                summary="JSON 解析失败，不能放行",
                raw_response=response_text,
            )

        # 提取字段
        if not isinstance(data, dict) or "consistency_score" not in data or "passed" not in data:
            return ConsistencyCheckResult(
                passed=False,
                score=0.0,
                issues=[{
                    "type": "审阅执行",
                    "severity": "严重",
                    "location": "一致性检查响应",
                    "description": "一致性检查缺少必需字段 consistency_score/passed",
                    "suggestion": "按契约返回完整 JSON 后重新执行",
                }],
                summary="一致性检查契约不完整，不能放行",
                raw_response=response_text,
            )
        try:
            score = float(data["consistency_score"])
        except (TypeError, ValueError):
            score = -1.0
        if score < 0 or score > 100:
            return ConsistencyCheckResult(
                passed=False,
                score=0.0,
                issues=[{
                    "type": "审阅执行",
                    "severity": "严重",
                    "location": "consistency_score",
                    "description": "一致性评分不在 0-100 范围内",
                    "suggestion": "返回有效的一致性评分",
                }],
                summary="一致性评分无效，不能放行",
                raw_response=response_text,
            )
        passed = bool(data["passed"]) and score >= CONSISTENCY_PASS_SCORE
        issues = data.get("issues", [])
        if not isinstance(issues, list):
            return ConsistencyCheckResult(
                passed=False,
                score=0.0,
                issues=[{
                    "type": "审阅执行",
                    "severity": "严重",
                    "location": "issues",
                    "description": "一致性检查 issues 字段不是数组",
                    "suggestion": "按契约返回 issues 数组后重新执行",
                }],
                summary="一致性检查契约不完整，不能放行",
                raw_response=response_text,
            )
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

        if any(item["severity"] in {"严重", "高", "high", "critical"} for item in valid_issues):
            passed = False

        return ConsistencyCheckResult(
            passed=passed,
            score=score,
            issues=valid_issues,
            summary=summary,
            raw_response=response_text,
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
