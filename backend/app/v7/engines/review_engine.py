"""Review Engine - Sprint 2.

Real 7-macro / 33-detail AI review of generated chapters.
Dimensions: consistency / character_voice / pacing / plot_logic /
            writing_quality / emotional_impact / constraint_compliance
"""
from __future__ import annotations

import json
import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from .base import BaseEngine, EngineCapability, EngineResult
from ..generation.generation_engine import AIGateway, AIGatewayError, chinese_word_count
from ..integration.quality import QUALITY_PASS_SCORE
from ...services.reader_experience import (
    READER_EXPERIENCE_KEYS,
    normalize_reader_experience,
    summarize_reader_experience,
)
from ...services.chapter_payoff import validate_payoff_contract, validate_payoff_evidence
from ...services.content_policy import analyze_content_policy, content_generation_contract
from ...services.pov_quality import analyze_third_person_narrative, third_person_generation_contract
from ...services.quality_profiles import quality_profile_metadata
from ..quality.audit_dimensions import (
    AUDIT_DIMENSIONS,
    format_audit_dimensions,
    normalize_audit_report,
)
from ..quality.deai_metrics import analyze_deai_patterns
from ..quality.review_evidence import (
    build_review_evidence,
    validate_review_evidence,
)

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

_UNSAFE_CHARACTER_SUGGESTION_MARKERS = (
    "增加口头禅",
    "添加口头禅",
    "加入口头禅",
    "补充口头禅",
    "增加方言",
    "添加方言",
    "新增背景",
    "补充背景设定",
    "增加人物设定",
    "添加人物设定",
    "改变性格设定",
)


def _compact_issue_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip())


def _issue_excerpt(issue: dict[str, Any], chapter_text: str) -> str:
    """Find an exact source excerpt, including quoted text in descriptions."""
    candidates = [
        str(issue.get("excerpt") or "").strip(),
        str(issue.get("anchor") or "").strip(),
    ]
    description = str(issue.get("description") or issue.get("issue") or "")
    candidates.extend(
        match.strip()
        for match in re.findall(r"[“『「\"‘']([^”』」\"’']{2,80})[”』」\"’']", description)
    )
    compact_chapter = _compact_issue_text(chapter_text)
    for candidate in candidates:
        if len(candidate) < 2:
            continue
        if candidate in chapter_text or _compact_issue_text(candidate) in compact_chapter:
            return candidate
    return ""


def normalize_review_issues(
    issues: Any,
    chapter_text: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep only source-grounded issues and suppress invented advice.

    The reviewer may still be uncertain, but the editor must never present a
    suggestion that cannot point to the submitted正文. Character voice edits
    are local wording edits; they cannot silently invent a catchphrase,
    dialect, biography, or personality trait.
    """
    verified: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    for raw in issues or []:
        if not isinstance(raw, dict):
            suppressed.append({
                "description": str(raw),
                "evidence_status": "unverified",
                "evidence_reason": "审阅结果不是结构化问题，无法定位正文证据",
            })
            continue
        item = dict(raw)
        excerpt = _issue_excerpt(item, chapter_text)
        if not excerpt:
            item.update({
                "evidence_status": "unverified",
                "evidence_reason": "未提供可在当前正文中定位的连续原文片段",
            })
            suppressed.append(item)
            continue
        item["excerpt"] = excerpt
        item["evidence_status"] = "verified"
        suggestion = str(item.get("suggestion") or "")
        if any(marker in suggestion for marker in _UNSAFE_CHARACTER_SUGGESTION_MARKERS):
            item["suggestion"] = (
                "只基于这段已有对白、动作和潜台词做局部改写，"
                "不要新增口头禅、方言、背景或人物设定。"
            )
            item["suggestion_status"] = "bounded_local_rewrite"
        verified.append(item)
    return verified, suppressed


class ReviewEngine(BaseEngine):
    """Reviews chapters with a real LLM call across 7 dimensions."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.ai_gateway = AIGateway(
            self.tracer,
            db=self.db,
            novel_id=self.novel_id,
            project_id=self.project_id,
            provider_config=self.provider_config,
        )

    @property
    def capability(self) -> EngineCapability:
        return EngineCapability(
            engine_name="review_engine",
            engine_type="review",
            version="1.2.0",
            description="7 macro scores plus a 33-dimension evidence audit for quality and continuity",
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
            "audit_dimensions": [item.key for item in AUDIT_DIMENSIONS],
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
            "previous_chapter_tail": input_data.get("previous_chapter_tail") or "",
            "previous_transition_contract": input_data.get("previous_transition_contract") or {},
            "chapter_plan": input_data.get("chapter_plan") or {},
            "scene_plan": input_data.get("scene_plan") or {},
            "deai_metrics": input_data.get("deai_metrics") or analyze_deai_patterns(chapter_text),
            "pov_metrics": input_data.get("pov_metrics") or analyze_third_person_narrative(chapter_text),
            "content_policy": input_data.get("content_policy") or analyze_content_policy(
                chapter_text, input_data.get("quality_profile") or self.quality_profile or {}
            ),
            "generation_quality": input_data.get("generation_quality") or {},
            "quality_profile": input_data.get("quality_profile") or self.quality_profile or {},
            "payoff_contract": input_data.get("payoff_contract") or {},
            "chapter_text": chapter_text,
        }

        return EngineResult(
            success=True,
            result=analysis,
            confidence=0.9,
            reason=(
                f"Prepared 7-macro/33-detail review for {analysis['word_count']} chars, "
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
            "audit_dimensions": [item.key for item in AUDIT_DIMENSIONS],
            "score_threshold": QUALITY_PASS_SCORE,
            "checks_to_run": [
                "ai_dimensional_review",
                "constraint_compliance",
                "length_check",
                "continuity_contract_check",
                "deai_metrics_check",
                "third_person_narrative_check",
                "content_policy_check",
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
        audit_block = format_audit_dimensions()

        # Keep both ends when a provider context limit requires a cap.  The
        # chapter opening contains the continuation point; the ending carries
        # the new hook and state for the next chapter.
        review_text = chapter_text
        if len(review_text) > 20000:
            review_text = (
                review_text[:10000]
                + "\n【正文中段省略，仅因模型上下文限制；不得据此推断中段不存在】\n"
                + review_text[-10000:]
            )
        continuity_block = json.dumps(
            {
                "previous_chapter_tail": data.get("previous_chapter_tail", ""),
                "previous_transition_contract": data.get("previous_transition_contract") or {},
            },
            ensure_ascii=False,
        )
        plan_block = json.dumps(
            {
                "chapter_plan": data.get("chapter_plan") or {},
                "scene_plan": data.get("scene_plan") or {},
                "deai_metrics": data.get("deai_metrics") or {},
                "pov_metrics": data.get("pov_metrics") or {},
                "content_policy": data.get("content_policy") or {},
                "quality_profile": data.get("quality_profile") or {},
                "payoff_contract": data.get("payoff_contract") or {},
            },
            ensure_ascii=False,
        )

        prompt = (
            "请对下面这章小说正文做专业审稿，先给 7 个宏观维度打分，"
            "再完成 33 个内部审计项（均为 0-100 整数）。\n\n"
            f"【已确立设定】\n{setting_block}\n\n"
            f"【必须遵守的约束】\n{constraint_block}\n\n"
            f"【跨章连续性证据】\n{continuity_block}\n\n"
            f"【本章计划与确定性表达指标】\n{plan_block}\n\n"
            f"{third_person_generation_contract()}\n"
            f"{content_generation_contract(data.get('quality_profile') or {})}\n\n"
            f"【评分维度】\n{dimension_block}\n\n"
            f"【33个内部审计项】\n{audit_block}\n\n"
            f"【正文】\n{review_text}\n\n"
            "只输出 JSON：\n"
            "{\n"
            '  "dimension_scores": {"consistency":0,"character_voice":0,"pacing":0,'
            '"plot_logic":0,"writing_quality":0,"emotional_impact":0,'
            '"constraint_compliance":0},\n'
            '  "overall_score": 0,\n'
            '  "audit_dimensions": {"chapter_goal":{"score":0,"evidence":"证据","repair":"修复动作"}},\n'
            '  "reader_experience": {"expectation":0,"conflict":0,"payoff":0,'
            '"emotion_shift":0,"worth_continuing":0},\n'
            '  "payoff_evidence": [{"type":"兑现类型","anchor":"正文中逐字可定位的短片段",'
            '"result":"正文中实际发生的可见结果","reaction":"人物/环境反应"}],\n'
            '  "issues": [{"dimension":"pacing","severity":"low|medium|high",'
            '"description":"问题","suggestion":"改法","excerpt":"原文片段"}],\n'
            '  "constraint_violations": [{"name":"约束名","description":"如何违反的",'
            '"severity":"low|medium|high"}],\n'
            '  "strengths": ["优点"],\n'
            '  "confidence": 0.85,\n'
            '  "reason": "总体评价一句话"\n'
            "}\n"
            "读者体验五项必须全部给出 0-100 分：expectation（期待感）、"
            "conflict（冲突感）、payoff（爽点/情绪释放）、emotion_shift（情绪变化）、"
            "worth_continuing（追读意愿）。低于 60 分必须在 issues 中指出具体段落或"
            "具体缺口；读者体验分不计入 7 维 overall_score。\n"
            "问题必须具体落到可改的证据：如果存在节奏/铺垫问题，指出转折前缺少的动作、线索或高潮后的余波；"
            "如果存在逻辑问题，指出触发→依据→选择→阻碍→代价→结果哪一环断了；"
            "如果存在 AI 腔，指出具体套话、同构句、解释腔或过度工整段落，并给出替代表达方向。"
            "中高严重度的问题不得只写‘可加强’，必须写清位置和修复动作。"
            "每条 issues 必须提供 excerpt：从正文连续复制至少 8 个字，且可逐字搜索定位；"
            "若没有可靠原文证据就不要输出该问题。不要因为单个‘像是’、破折号或常用词出现就机械判定 AI 腔，"
            "只有在连续堆叠、明显削弱表达或形成同构模板时才指出。"
            "不得建议凭空增加口头禅、方言、背景、人物性格或新设定；人物声音问题只能改写现有对白的措辞、节奏、动作和潜台词，"
            "除非设定/正文已有证据支持新增特征。"
            "33个审计项必须全部出现；每项都要给 score、evidence、repair。"
            "如果某项确实不适用，也要给出 score，并在 evidence 说明不适用的理由。"
            "如果提供了本章爽点契约，必须从正文逐字摘取至少一条 payoff_evidence；"
            "anchor 必须能在正文中定位，不能用概括或虚构证据。"
            "叙述视角必须是第三人称：引号、短信、书信和直接引用里的‘我’不计入，"
            "其余叙述里的第一人称命中即判为严重问题；都市题材还必须使用完全架空的实体名称，"
            "不能用现实城市、公司、平台或公众人物替代。"
            f"overall_score 必须是 7 个维度分数的加权结果，不要凭空给分。"
            f"低于 {QUALITY_PASS_SCORE:.0f} 分，或 consistency/character_voice/plot_logic/"
            f"pacing/writing_quality/constraint_compliance 任一低于 85 分，均不得标记为通过。"
        )

        try:
            ai = await self.ai_gateway.generate_json(
                prompt,
                system_prompt=(
                    "你是严格的中文小说审稿编辑，只输出合法 JSON，不要客套。"
                    + third_person_generation_contract()
                    + content_generation_contract(data.get("quality_profile") or {})
                ),
                max_tokens=5000,
                temperature=0.0,
                prompt_name="v7.review.33_dimension",
                prompt_version="1.2.0",
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

        # A malformed payoff_evidence field is a review-contract defect, not
        # automatically a prose defect.  Ask the Provider for a bounded,
        # evidence-only repair before putting the chapter on a review hold.
        # The repair cannot change scores, audit items, or chapter text; it
        # only accepts a replacement when an anchor is an exact/fuzzy match in
        # the already-reviewed正文.
        payoff_contract = data.get("payoff_contract") or {}
        payoff_required = bool(data.get("quality_profile") and payoff_contract)
        payoff_evidence_repair: dict[str, Any] = {}
        if payoff_required:
            initial_evidence = raw.get("payoff_evidence") or []
            initial_validation = validate_payoff_evidence(
                chapter_text,
                initial_evidence,
                required=True,
            )
            if not initial_validation.get("passed"):
                payoff_evidence_repair = {
                    "attempted": True,
                    "initial_validation": initial_validation,
                    "passed": False,
                }
                repair_prompt = (
                    "上一次审稿的 payoff_evidence 字段无法通过逐字定位校验。"
                    "不要重新评分，不要修改任何审计结论，只补齐这个字段。"
                    "从下面正文中直接复制一段连续原文作为 anchor，至少 8 个字，"
                    "anchor 必须能在正文中逐字搜索到；result 只描述这段原文已经发生的可见结果，"
                    "不能写正文中没有发生的推测。只输出 JSON，不要解释。\n"
                    f"【本章爽点契约】{json.dumps(payoff_contract, ensure_ascii=False)}\n"
                    f"【正文】\n{review_text}\n"
                    '{"payoff_evidence":[{"type":"兑现类型","anchor":"正文连续原句",'
                    '"result":"可见结果","reaction":"人物或环境反应"}]}'
                )
                try:
                    repair_ai = await self.ai_gateway.generate_json(
                        repair_prompt,
                        system_prompt="你是严格的中文小说审稿证据校对员，只输出合法 JSON，不重评正文。",
                        max_tokens=800,
                        temperature=0.0,
                        prompt_name="v7.review.payoff_evidence_repair",
                        prompt_version="1.0.0",
                    )
                    self.record_usage(repair_ai["usage"])
                    repaired_evidence = (repair_ai.get("data") or {}).get("payoff_evidence") or []
                    repaired_validation = validate_payoff_evidence(
                        chapter_text,
                        repaired_evidence,
                        required=True,
                    )
                    payoff_evidence_repair.update({
                        "passed": repaired_validation.get("passed") is True,
                        "validation": repaired_validation,
                    })
                    if repaired_validation.get("passed") is True:
                        raw = {**raw, "payoff_evidence": repaired_evidence}
                except AIGatewayError as exc:
                    payoff_evidence_repair["error"] = type(exc).__name__

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
                result={
                    "raw": raw,
                    "validation_failures": [
                        {
                            "code": "missing_dimensions",
                            "fields": missing,
                            "message": "AI 审稿缺少宏观评分维度",
                        }
                    ],
                },
            )

        reader_experience = normalize_reader_experience(raw.get("reader_experience"))
        missing_reader_experience = [
            key for key in READER_EXPERIENCE_KEYS
            if reader_experience is None or key not in reader_experience
        ]
        if missing_reader_experience:
            return EngineResult(
                success=False,
                reason=(
                    "AI review missing reader-experience evidence: "
                    + ", ".join(missing_reader_experience)
                ),
                confidence=0.0,
                result={
                    "raw": raw,
                    "validation_failures": [
                        {
                            "code": "missing_reader_experience",
                            "fields": missing_reader_experience,
                            "message": "AI 审稿缺少读者体验评分",
                        }
                    ],
                },
            )

        overall = raw.get("overall_score")
        computed = round(sum(dimension_scores.values()) / len(dimension_scores), 1)
        if not isinstance(overall, (int, float)) or abs(overall - computed) > 15:
            # Trust the arithmetic over the model when they disagree wildly.
            overall = computed

        violations = raw.get("constraint_violations") or []
        audit_report = normalize_audit_report(
            raw.get("audit_dimensions"),
            macro_scores=dimension_scores,
            reader_experience=reader_experience,
        )
        payoff_evidence = raw.get("payoff_evidence") or []
        payoff_evidence_validation = validate_payoff_evidence(
            chapter_text,
            payoff_evidence,
            required=payoff_required,
        )
        verified_issues, suppressed_issues = normalize_review_issues(
            raw.get("issues") or [],
            chapter_text,
        )
        review_result = {
            "canonical_engine": "v7",
            "chapter_number": data.get("chapter_number"),
            "overall_score": float(overall),
            "computed_score": computed,
            "dimension_scores": dimension_scores,
            "audit_report": audit_report,
            "reader_experience": reader_experience,
            "reader_experience_summary": summarize_reader_experience(reader_experience),
            "issues": verified_issues,
            "unverified_issues": suppressed_issues,
            "issue_evidence": {
                "schema_version": "review-issue-evidence-v1",
                "total": len(verified_issues) + len(suppressed_issues),
                "verified": len(verified_issues),
                "suppressed": len(suppressed_issues),
            },
            "constraint_violations": violations,
            "strengths": raw.get("strengths") or [],
            "constraints_checked": len(constraints),
            "deai_metrics": data.get("deai_metrics") or analyze_deai_patterns(chapter_text),
            "pov_metrics": data.get("pov_metrics") or analyze_third_person_narrative(chapter_text),
            "content_policy": data.get("content_policy") or analyze_content_policy(
                chapter_text, data.get("quality_profile") or {}
            ),
            "generation_quality": data.get("generation_quality") or {},
            "word_count": data.get("word_count", 0),
            "model": ai["usage"].get("model"),
            "provenance": {
                "engine": "v7",
                "audit_source": "v7.review.33_dimension",
                "prompt_name": "v7.review.33_dimension",
                "prompt_version": "1.2.0",
                # Test doubles and older adapters do not necessarily expose
                # routing metadata.  Missing provenance must remain explicit;
                # it must not turn a valid review contract into an engine error.
                "provider": ai["usage"].get("provider") or getattr(self.ai_gateway, "provider", "unknown"),
                "model": ai["usage"].get("model") or getattr(self.ai_gateway, "default_model", None),
                "text_hash": hashlib.sha256(chapter_text.encode("utf-8")).hexdigest(),
                "scored_at": datetime.now(timezone.utc).isoformat(),
            },
            "reason": raw.get("reason", ""),
            "quality_profile": quality_profile_metadata(data.get("quality_profile") or {}) if data.get("quality_profile") else {},
            "payoff_contract": payoff_contract,
            "payoff_evidence": payoff_evidence,
            "payoff_evidence_validation": payoff_evidence_validation,
            "payoff_evidence_repair": payoff_evidence_repair,
        }
        review_result["review_evidence"] = build_review_evidence(
            review_result,
            require_continuity=False,
        )

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
            reason=(
                f"AI review score {overall} across 7 macro dimensions; "
                f"33-dimension coverage {audit_report['coverage']:.0%}"
            ),
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
        reader_experience = result.get("reader_experience") or {}
        reader_experience_complete = all(
            key in reader_experience
            and isinstance(reader_experience.get(key), (int, float))
            and 0 <= reader_experience[key] <= 100
            for key in READER_EXPERIENCE_KEYS
        )
        high_violations = [
            v
            for v in result.get("constraint_violations", [])
            if str(v.get("severity", "")).lower() == "high"
        ]
        audit_report = result.get("audit_report") or {}
        evidence_validation = validate_review_evidence(
            result,
            require_continuity=False,
        )
        audit_contract_valid = evidence_validation["audit_33"].get("complete") is True
        payoff_evidence_validation = result.get("payoff_evidence_validation") or {}
        payoff_evidence_valid = (
            not payoff_evidence_validation.get("required")
            or payoff_evidence_validation.get("passed") is True
        )

        validation = {
            **result,
            "review_valid": (
                all_dimensions_present
                and in_range
                and overall_in_range
                and reader_experience_complete
                and audit_contract_valid
                and payoff_evidence_valid
                and evidence_validation.get("passed") is True
            ),
            "dimensions_count": len(scores),
            "score_in_range": in_range and overall_in_range,
            "reader_experience_complete": reader_experience_complete,
            "audit_contract_valid": audit_contract_valid,
            "audit_coverage": audit_report.get("coverage", 0.0),
            "review_evidence": evidence_validation,
            "payoff_evidence_validation": payoff_evidence_validation,
            "reader_experience_summary": summarize_reader_experience(reader_experience),
            "blocking_violations": len(high_violations),
            "passed": result.get("overall_score", 0) >= QUALITY_PASS_SCORE and not high_violations,
        }

        validation_failures: list[dict[str, Any]] = []
        if not all_dimensions_present:
            validation_failures.append({
                "code": "missing_dimensions",
                "message": "审稿结果缺少一个或多个宏观评分维度",
            })
        if not in_range or not overall_in_range:
            validation_failures.append({
                "code": "score_out_of_range",
                "message": "审稿分数不在 0-100 范围内",
            })
        if not reader_experience_complete:
            validation_failures.append({
                "code": "reader_experience_incomplete",
                "message": "读者体验五项评分不完整或不在 0-100 范围内",
            })
        if not audit_contract_valid:
            validation_failures.append({
                "code": "audit_contract_invalid",
                "message": "33 维审计必须逐项返回分数、原文证据和修复动作，不能使用兼容投影",
            })
        if evidence_validation.get("passed") is not True:
            validation_failures.append({
                "code": "review_evidence_incomplete",
                "message": "V7 审阅证据链不完整：" + "；".join(evidence_validation.get("issues") or []),
                "detail": evidence_validation,
            })
        if not payoff_evidence_valid:
            validation_failures.append({
                "code": "payoff_evidence_invalid",
                "message": "爽点证据无法在正文中逐字定位",
                "detail": payoff_evidence_validation,
            })
        validation["validation_failures"] = validation_failures

        if not validation["review_valid"]:
            # A provider review contract failure is a quality hold, not a
            # transport failure. Keep the structured result so the director
            # can persist the generated draft as needs_review and continue an
            # explicitly ordered batch without ever marking it accepted.
            return EngineResult(
                success=True,
                result=validation,
                confidence=output.confidence,
                reason=(
                    "Review output held for validation: "
                    + "; ".join(item["code"] for item in validation_failures)
                ),
                warnings=[
                    *(output.warnings or []),
                    "review_validation_failed",
                ],
            )

        return EngineResult(
            success=True,
            result=validation,
            confidence=output.confidence,
            reason=(
                f"Validated 7/7 dimensions plus reader experience, "
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

        if data.get("review_valid") is False:
            # Do not project an invalid provider review into Novel Brain's
            # accepted-review state. The director persists the draft and the
            # validation evidence at the V6 boundary instead.
            return EngineResult(
                success=True,
                result={
                    **data,
                    "brain_updated": False,
                    "score_recorded": False,
                },
                confidence=validated.confidence,
                reason="Review held; invalid provider contract was not projected as accepted state",
                warnings=validated.warnings,
            )

        await self.brain.state.update_state(
            "global",
            "last_review_score",
            {
                "chapter_number": chapter_number,
                "overall_score": data.get("overall_score", 0),
                "dimension_scores": data.get("dimension_scores", {}),
                "reader_experience": data.get("reader_experience", {}),
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
            context={
                "dimension_scores": data.get("dimension_scores", {}),
                "reader_experience": data.get("reader_experience", {}),
            },
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
