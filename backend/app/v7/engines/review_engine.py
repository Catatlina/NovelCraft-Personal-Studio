"""Review Engine - Sprint 2.

Real 7-dimensional AI review of generated chapters.
Dimensions: consistency / character_voice / pacing / plot_logic /
            writing_quality / emotional_impact / constraint_compliance
"""
from __future__ import annotations

import json
from typing import Any

from .base import BaseEngine, EngineCapability, EngineResult
from ..generation.generation_engine import AIGateway, AIGatewayError, chinese_word_count

REVIEW_DIMENSIONS: tuple[str, ...] = (
    "consistency",
    "character_voice",
    "pacing",
    "plot_logic",
    "writing_quality",
    "emotional_impact",
    "constraint_compliance",
)

DIMENSION_LABELS: dict[str, str] = {
    "consistency": "设定一致性（与已确立的人物/世界/情节状态是否冲突）",
    "character_voice": "人物声音（对白与行为是否符合人物设定）",
    "pacing": "节奏（张弛、场景切换、信息密度）",
    "plot_logic": "情节逻辑（因果链是否成立、有无硬伤）",
    "writing_quality": "文字质量（画面感、词句、避免AI腔）",
    "emotional_impact": "情感冲击（是否让读者产生情绪波动）",
    "constraint_compliance": "约束遵守（是否违反必须遵守的约束）",
}


class ReviewEngine(BaseEngine):
    """Reviews chapters with a real LLM call across 7 dimensions."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.ai_gateway = AIGateway(self.tracer)

    @property
    def capability(self) -> EngineCapability:
        return EngineCapability(
            engine_name="review_engine",
            engine_type="review",
            version="1.0.0",
            description="7-dimensional AI review for quality, consistency and constraints",
            input_types=["chapter_text", "scene_text", "full_text"],
            output_types=["review_report", "issues", "score"],
        )

    # ── Phase 1: analyze ────────────────────────────────────────────────
    async def analyze(self, input_data: dict[str, Any]) -> EngineResult:
        chapter_text = input_data.get("chapter_text", "") or ""

        if not chapter_text.strip():
            return EngineResult(
                success=False,
                reason="No text provided for review",
                confidence=0.0,
            )

        constraints = await self.brain.constraints.list_constraints(limit=50)
        character_states = await self.brain.state.list_states("character", limit=20)
        plot_states = await self.brain.state.list_states("plot", limit=20)

        analysis = {
            "chapter_number": input_data.get("chapter_number"),
            "word_count": chinese_word_count(chapter_text),
            "review_dimensions": list(REVIEW_DIMENSIONS),
            "constraints_to_check": [
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "description": c.get("description"),
                    "severity": c.get("severity"),
                }
                for c in constraints
            ],
            "known_characters": [
                {"key": s["key"], "value": s["value"]} for s in character_states
            ],
            "known_plot": [
                {"key": s["key"], "value": s["value"]} for s in plot_states
            ],
            "chapter_text": chapter_text,
        }

        return EngineResult(
            success=True,
            result=analysis,
            confidence=0.9,
            reason=(
                f"Prepared 7-dimension review for {analysis['word_count']} chars, "
                f"{len(analysis['constraints_to_check'])} constraints"
            ),
        )

    # ── Phase 2: plan ───────────────────────────────────────────────────
    async def plan(self, analysis: EngineResult) -> EngineResult:
        if not analysis.success:
            return analysis

        data = analysis.result or {}
        plan = {
            **data,
            "dimensions": list(REVIEW_DIMENSIONS),
            "score_threshold": 70,
            "checks_to_run": [
                "ai_dimensional_review",
                "constraint_compliance",
                "length_check",
            ],
        }
        return EngineResult(
            success=True,
            result=plan,
            confidence=0.9,
            reason=f"Review plan with {len(REVIEW_DIMENSIONS)} dimensions",
        )

    # ── Phase 3: execute (real AI) ──────────────────────────────────────
    async def execute(self, plan: EngineResult) -> EngineResult:
        if not plan.success:
            return plan

        data = plan.result or {}
        chapter_text = data.get("chapter_text", "")
        constraints = data.get("constraints_to_check", [])

        constraint_block = (
            "\n".join(
                f"- [{c.get('severity')}] {c.get('name')}：{c.get('description') or ''}"
                for c in constraints
            )
            or "（无显式约束）"
        )
        setting_block = json.dumps(
            {
                "characters": data.get("known_characters", [])[:10],
                "plot": data.get("known_plot", [])[:10],
            },
            ensure_ascii=False,
        )
        dimension_block = "\n".join(
            f"- {k}: {v}" for k, v in DIMENSION_LABELS.items()
        )

        # Cap the reviewed text so a single review stays inside the context window.
        review_text = chapter_text[:12000]

        prompt = (
            "请对下面这章小说正文做专业审稿，从 7 个维度打分（0-100 整数）。\n\n"
            f"【已确立设定】\n{setting_block}\n\n"
            f"【必须遵守的约束】\n{constraint_block}\n\n"
            f"【评分维度】\n{dimension_block}\n\n"
            f"【正文】\n{review_text}\n\n"
            "只输出 JSON：\n"
            "{\n"
            '  "dimension_scores": {"consistency":0,"character_voice":0,"pacing":0,'
            '"plot_logic":0,"writing_quality":0,"emotional_impact":0,'
            '"constraint_compliance":0},\n'
            '  "overall_score": 0,\n'
            '  "issues": [{"dimension":"pacing","severity":"low|medium|high",'
            '"description":"问题","suggestion":"改法","excerpt":"原文片段"}],\n'
            '  "constraint_violations": [{"name":"约束名","description":"如何违反的",'
            '"severity":"low|medium|high"}],\n'
            '  "strengths": ["优点"],\n'
            '  "confidence": 0.85,\n'
            '  "reason": "总体评价一句话"\n'
            "}\n"
            "overall_score 必须是 7 个维度分数的加权结果，不要凭空给分。"
        )

        try:
            ai = await self.ai_gateway.generate_json(
                prompt,
                system_prompt="你是严格的中文小说审稿编辑，只输出合法 JSON，不要客套。",
                max_tokens=3000,
                temperature=0.2,
                prompt_name="v7.review.seven_dimension",
                prompt_version="1.0.0",
            )
        except AIGatewayError as exc:
            return EngineResult(
                success=False,
                reason=f"AI review failed: {exc}",
                confidence=0.0,
                warnings=["review engine requires a working LLM; no fallback score"],
            )

        self.record_usage(ai["usage"])
        raw = ai["data"]

        scores_raw = raw.get("dimension_scores") or {}
        dimension_scores: dict[str, int] = {}
        missing: list[str] = []
        for dim in REVIEW_DIMENSIONS:
            value = scores_raw.get(dim)
            if isinstance(value, (int, float)):
                dimension_scores[dim] = int(max(0, min(100, value)))
            else:
                missing.append(dim)

        if missing:
            return EngineResult(
                success=False,
                reason=f"AI review missing dimensions: {', '.join(missing)}",
                confidence=0.0,
                result={"raw": raw},
            )

        overall = raw.get("overall_score")
        computed = round(sum(dimension_scores.values()) / len(dimension_scores), 1)
        if not isinstance(overall, (int, float)) or abs(overall - computed) > 15:
            # Trust the arithmetic over the model when they disagree wildly.
            overall = computed

        violations = raw.get("constraint_violations") or []
        review_result = {
            "chapter_number": data.get("chapter_number"),
            "overall_score": float(overall),
            "computed_score": computed,
            "dimension_scores": dimension_scores,
            "issues": raw.get("issues") or [],
            "constraint_violations": violations,
            "strengths": raw.get("strengths") or [],
            "constraints_checked": len(constraints),
            "word_count": data.get("word_count", 0),
            "model": ai["usage"].get("model"),
            "reason": raw.get("reason", ""),
        }

        confidence = raw.get("confidence")
        confidence = (
            float(confidence) if isinstance(confidence, (int, float)) else 0.8
        )

        warnings: list[str] = []
        if violations:
            warnings.append(f"{len(violations)} constraint violation(s) reported")

        return EngineResult(
            success=True,
            result=review_result,
            confidence=max(0.0, min(1.0, confidence)),
            reason=f"AI review score {overall} across 7 dimensions",
            warnings=warnings,
        )

    # ── Phase 4: validate ───────────────────────────────────────────────
    async def validate(self, output: EngineResult) -> EngineResult:
        if not output.success:
            return output

        result = output.result or {}
        scores = result.get("dimension_scores", {})

        all_dimensions_present = all(d in scores for d in REVIEW_DIMENSIONS)
        in_range = all(0 <= v <= 100 for v in scores.values())
        overall_in_range = 0 <= result.get("overall_score", -1) <= 100
        high_violations = [
            v
            for v in result.get("constraint_violations", [])
            if str(v.get("severity", "")).lower() == "high"
        ]

        validation = {
            **result,
            "review_valid": all_dimensions_present and in_range and overall_in_range,
            "dimensions_count": len(scores),
            "score_in_range": in_range and overall_in_range,
            "blocking_violations": len(high_violations),
            "passed": result.get("overall_score", 0) >= 70 and not high_violations,
        }

        if not validation["review_valid"]:
            return EngineResult(
                success=False,
                result=validation,
                confidence=0.0,
                reason="Review output failed validation",
            )

        return EngineResult(
            success=True,
            result=validation,
            confidence=output.confidence,
            reason=(
                f"Validated 7/7 dimensions, "
                f"{validation['blocking_violations']} blocking violation(s)"
            ),
            warnings=output.warnings,
        )

    # ── Phase 5: update ─────────────────────────────────────────────────
    async def update(self, validated: EngineResult) -> EngineResult:
        if not validated.success:
            return validated

        data = validated.result or {}
        chapter_number = data.get("chapter_number")

        await self.brain.state.update_state(
            "global",
            "last_review_score",
            {
                "chapter_number": chapter_number,
                "overall_score": data.get("overall_score", 0),
                "dimension_scores": data.get("dimension_scores", {}),
                "issues_count": len(data.get("issues", [])),
                "blocking_violations": data.get("blocking_violations", 0),
            },
            validated.confidence,
            source="review_engine",
            reason="7-dimension AI review",
        )

        for violation in data.get("constraint_violations", []):
            await self.event_bus.publish(
                "constraint_violated",
                f"Constraint violated: {violation.get('name')}",
                "review",
                source="review_engine",
                severity="warning"
                if str(violation.get("severity")).lower() != "high"
                else "error",
                event_data={
                    "chapter_number": chapter_number,
                    "constraint": violation.get("name"),
                    "description": violation.get("description"),
                    "severity": violation.get("severity"),
                },
            )

        await self.brain.record_decision(
            "review_score",
            f"score:{data.get('overall_score', 0)}",
            decision_reason=(
                f"Chapter {chapter_number} 7-dimension review scored "
                f"{data.get('overall_score', 0)}. "
                f"{data.get('reason') or ''}"
            ).strip(),
            confidence=validated.confidence,
            permission_level="auto",
            status="completed",
            decided_by="ai",
            context={"dimension_scores": data.get("dimension_scores", {})},
        )

        return EngineResult(
            success=True,
            result={
                **data,
                "brain_updated": True,
                "score_recorded": True,
            },
            confidence=validated.confidence,
            reason="Brain updated with 7-dimension review results",
            warnings=validated.warnings,
        )
