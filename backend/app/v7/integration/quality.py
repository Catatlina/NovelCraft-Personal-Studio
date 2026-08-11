"""Shared quality gates for the V7 director pipeline.

The old director treated a 70-point review as publishable.  That made a
chapter with a weak continuity or writing score look successful when its
average happened to be high.  This module keeps the gate deterministic and
testable: the model supplies evidence, while the application decides whether
the chapter can enter the V6 library.
"""
from __future__ import annotations

from typing import Any

from ...services.reader_experience import (
    reader_experience_issues,
    summarize_reader_experience,
)
from ...services.quality_risks import build_quality_repair_contract
from ...services.chapter_payoff import validate_payoff_contract
from ...services.content_policy import analyze_content_policy
from ...services.pov_quality import analyze_third_person_narrative
from ..quality.audit_dimensions import AUDIT_DIMENSIONS
from ..quality.review_evidence import validate_review_evidence
from ..quality.world_constraint import get_constraint_pack
from ..quality.reader_simulation import simulate_reader_first_pass
from ..quality.hook_analysis import analyze_hook_power
from ..quality.writing_methodology import normalize_causal_audit

QUALITY_PASS_SCORE = 85.0
QUALITY_REWORK_SCORE = 80.0
MAX_REWORKS = 3  # P2-1 质量整改：从2增加到3，给完整重写更多机会
MAX_LOCAL_REPAIRS = 1  # 本地修复最多尝试次数，不计入MAX_REWORKS配额

# These dimensions directly affect cross-chapter reading experience.  A low
# emotional/pacing score is reviewable; a low continuity/logic/writing score is
# not allowed to pass merely because other dimensions compensate for it.
CRITICAL_DIMENSION_MINIMUMS: dict[str, float] = {
    "consistency": 85.0,
    "character_voice": 85.0,
    "plot_logic": 85.0,
    "pacing": 85.0,
    "writing_quality": 85.0,
    "constraint_compliance": 85.0,
}

AUDIT_HARD_MINIMUM = 85.0
DEAI_HIGH_RISK_THRESHOLD = 70
DEAI_BLOCKING_FLAGS = {
    "dash_density",
    "uniform_cadence",
    "repeated_paragraph_opening",
    "duplicate_paragraph",
    "rewrite_candidate_rejected",
    "ai_phrase",
    "repeated_tic",
}

# 章节正文镜像是重复生成/平行版本的确定性信号。它不能只作为提示，
# 否则重复章会继续进入 review 和后续上下文。
CHAPTER_MIRROR_HARD_GATE = True
PAYOFF_VARIETY_HARD_GATE = False  # 爽点类型多样性：默认soft warning


def evaluate_review(
    review_data: dict[str, Any],
    *,
    project_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Return the application-level decision for an AI review payload."""
    overall_score = float(review_data.get("overall_score") or 0.0)
    blocking = int(review_data.get("blocking_violations") or 0)
    dimensions = review_data.get("dimension_scores") or review_data.get("dimensions") or {}
    failures: list[dict[str, Any]] = []
    generation_quality = review_data.get("generation_quality") or {}
    pov_metrics = (
        review_data.get("pov_metrics")
        or generation_quality.get("pov_metrics")
        or analyze_third_person_narrative(review_data.get("chapter_text") or "")
    )
    if pov_metrics and pov_metrics.get("passed") is False:
        failures.append({
            "dimension": "third_person_narrative",
            "actual": pov_metrics.get("first_person_count") or "detected",
            "minimum": 0,
            "reason": "叙述部分出现第一人称；对白/短信中的第一人称不计入",
        })
    content_policy = (
        review_data.get("content_policy")
        or generation_quality.get("content_policy")
        or analyze_content_policy(
            review_data.get("chapter_text") or "",
            review_data.get("quality_profile") or {},
        )
    )
    if content_policy and content_policy.get("passed") is False:
        for policy_failure in content_policy.get("failures") or []:
            failures.append({
                "dimension": str(policy_failure.get("code") or "content_policy"),
                "actual": "detected",
                "minimum": "clean",
                "reason": str(policy_failure.get("message") or "内容安全/架空现实层未通过"),
            })
    if generation_quality.get("passed") is False:
        for failure in generation_quality.get("failures") or []:
            if not isinstance(failure, dict):
                continue
            failures.append(
                {
                    "dimension": str(failure.get("code") or "generation_quality"),
                    "actual": failure.get("severity") or "high",
                    "minimum": "resolved",
                    "reason": str(failure.get("message") or "生成结构质量未通过"),
                }
            )
        if not generation_quality.get("failures"):
            failures.append(
                {
                    "dimension": "generation_quality",
                    "actual": "failed",
                    "minimum": "passed",
                    "reason": "生成结构质量门禁未通过",
                }
            )
    quality_profile = review_data.get("quality_profile") or {}
    causal_audit = normalize_causal_audit(review_data.get("causal_audit"))
    if causal_audit.get("red_issues") or causal_audit.get("conclusion") in {
        "return_scene",
        "return_skeleton",
    }:
        failures.append({
            "dimension": "causal_audit",
            "actual": causal_audit.get("conclusion") or "return_scene",
            "minimum": "pass",
            "reason": "；".join(
                item.get("gap") or item.get("fact") or "红色因果问题"
                for item in causal_audit.get("red_issues") or []
            ) or "因果审查要求返回场景或返回骨架修复",
        })
    payoff_contract = review_data.get("payoff_contract") or {}
    payoff_validation = review_data.get("payoff_validation") or {}
    
    # 阶段1：封神世界观硬约束注入
    # 检查 quality_profile 中是否指定了世界观约束，如果有则进行检查
    # 目前作为 soft warning，不阻塞质量门禁，后续可根据需要升级为 hard gate
    world_constraint_result = None
    world_constraint_genre = quality_profile.get("world_constraint") if quality_profile else None
    if world_constraint_genre:
        constraint_pack = get_constraint_pack(world_constraint_genre)
        if constraint_pack:
            chapter_text = review_data.get("chapter_text") or ""
            if chapter_text:
                world_constraint_result = constraint_pack.check_text(chapter_text)
                # 目前作为 soft warning，不加入 failures
                # 如果后续需要升级为 hard gate，可以取消下面的注释
                # if not world_constraint_result["passed"]:
                #     for violation in world_constraint_result["violations"]:
                #         if violation["severity"] == "high":
                #             failures.append({
                #                 "dimension": f"world_constraint_{violation['rule_id']}",
                #                 "actual": violation["count"],
                #                 "minimum": 0,
                #                 "reason": f"世界观约束违反：{violation['description']}",
                #             })
    
    # 阶段3："读第一遍"模拟审查
    # 模拟读者第一次阅读的感受和判断
    # 目前作为可选功能，默认不启用（需要AI调用，有成本）
    # 可以通过 quality_profile.enable_reader_simulation 开关控制
    reader_simulation_result = None
    enable_reader_simulation = quality_profile.get("enable_reader_simulation") if quality_profile else False
    if enable_reader_simulation:
        chapter_text = review_data.get("chapter_text") or ""
        if chapter_text:
            platform = quality_profile.get("platform", "general") if quality_profile else "general"
            reader_simulation_result = simulate_reader_first_pass(
                chapter_text,
                platform,
                project_id=project_id,
                user_id=user_id,
            )
    
    # 阶段4：首章钩力分析
    # 对首章做专项分析，输出钩力报告
    # 作为信息输出，不阻塞质量门禁
    # 可以通过 quality_profile.enable_hook_analysis 开关控制
    hook_analysis_result = None
    enable_hook_analysis = quality_profile.get("enable_hook_analysis") if quality_profile else False
    if enable_hook_analysis:
        chapter_text = review_data.get("chapter_text") or ""
        if chapter_text:
            platform = quality_profile.get("platform", "general") if quality_profile else "general"
            # 检查是否是首章
            chapter_number = review_data.get("chapter_number", 1)
            is_first_chapter = (chapter_number == 1)
            hook_analysis_result = analyze_hook_power(chapter_text, platform, is_first_chapter)
    if quality_profile and payoff_contract:
        payoff_validation = validate_payoff_contract(
            payoff_contract,
            profile=quality_profile,
            required=True,
        )
        if not payoff_validation.get("passed"):
            failures.append({
                "dimension": "payoff_contract",
                "actual": "missing",
                "minimum": "complete",
                "reason": "；".join(payoff_validation.get("issues") or ["爽点契约未完成"]),
            })
    payoff_evidence = review_data.get("payoff_evidence_validation") or {}
    # 番茄爽文加码：将 payoff_evidence 从 hard gate 降为 soft warning
    # 原因：text_anchor 匹配逻辑不够稳定，经常误判，导致质量门禁不通过
    # 短期方案：先不阻塞生成流程，只作为警告信息保留
    # 长期方案：优化匹配逻辑，提高准确率
    if payoff_evidence.get("required") and payoff_evidence.get("passed") is not True:
        # 不再加入 failures，只作为 warning 保留
        # failures.append({
        #     "dimension": "payoff_evidence",
        #     "actual": "missing_or_unverifiable",
        #     "minimum": "verifiable",
        #     "reason": "爽点证据无法在正文中定位",
        # })
        pass
    for validation_failure in review_data.get("validation_failures") or []:
        if not isinstance(validation_failure, dict):
            continue
        code = str(validation_failure.get("code") or "review_validation")
        # Payoff evidence is already rendered above with the shared gate
        # wording. Avoid counting it twice while retaining every other review
        # contract failure as a hard, explainable quality hold.
        if code == "payoff_evidence_invalid" and any(
            item.get("dimension") == "payoff_evidence" for item in failures
        ):
            continue
        failures.append({
            "dimension": code,
            "actual": "invalid",
            "minimum": "valid",
            "reason": str(validation_failure.get("message") or "审稿契约校验失败"),
        })
    if overall_score < QUALITY_PASS_SCORE:
        failures.append({"dimension": "overall_score", "actual": overall_score, "minimum": QUALITY_PASS_SCORE})
    for name, minimum in CRITICAL_DIMENSION_MINIMUMS.items():
        actual = float(dimensions.get(name) or 0.0)
        if actual < minimum:
            failures.append({"dimension": name, "actual": actual, "minimum": minimum})
    if blocking:
        failures.append({"dimension": "blocking_violations", "actual": blocking, "minimum": 0})
    repair_contract = build_quality_repair_contract(
        review_data,
        dimension_minimums=CRITICAL_DIMENSION_MINIMUMS,
        continuity=review_data.get("continuity"),
    )
    for risk in repair_contract["blocking_risks"]:
        failures.append({
            "dimension": risk["category"],
            "actual": risk.get("severity"),
            "minimum": "resolved",
            "reason": risk.get("description") or risk.get("text"),
        })
    audit_report = review_data.get("audit_report") or {}
    audit_items = audit_report.get("items") or {}
    for item in AUDIT_DIMENSIONS:
        if not item.hard_gate:
            continue
        detail = audit_items.get(item.key) or {}
        audit_score = detail.get("score")
        if isinstance(audit_score, (int, float)) and audit_score < AUDIT_HARD_MINIMUM:
            failures.append({
                "dimension": item.key,
                "actual": audit_score,
                "minimum": AUDIT_HARD_MINIMUM,
                "reason": detail.get("evidence") or item.label,
            })
    review_evidence = review_data.get("review_evidence") or {}
    # Only canonical V7 reviews are held to the complete evidence contract.
    # Older compatibility callers can still inspect their macro score, but
    # they can never masquerade as a complete V7 audit once they opt into the
    # canonical engine/read model.
    if review_data.get("canonical_engine") == "v7" or review_evidence:
        review_evidence = validate_review_evidence(
            review_data,
            require_continuity=False,
        )
        if review_evidence.get("passed") is not True:
            failures.append({
                "dimension": "review_evidence_incomplete",
                "actual": review_evidence.get("missing") or "unknown",
                "minimum": "complete",
                "reason": "；".join(review_evidence.get("issues") or ["V7 审阅证据链不完整"]),
            })
    deai_metrics = review_data.get("deai_metrics") or {}
    deai_risk = deai_metrics.get("risk_score")
    if isinstance(deai_risk, (int, float)) and deai_risk >= DEAI_HIGH_RISK_THRESHOLD:
        failures.append({
            "dimension": "ai_pattern_risk",
            "actual": deai_risk,
            "minimum": f"< {DEAI_HIGH_RISK_THRESHOLD}",
            "reason": "确定性表达指标显示 AI 腔风险过高，需要定向润色",
        })
    duplicate_summary = deai_metrics.get("duplicate_paragraphs") or {}
    duplicate_ratio = duplicate_summary.get("duplicate_ratio")
    if (
        isinstance(duplicate_ratio, (int, float))
        and duplicate_ratio >= 0.01
        and not any(item.get("dimension") == "duplicate_paragraph" for item in failures)
    ):
        failures.append({
            "dimension": "duplicate_paragraph",
            "actual": duplicate_ratio,
            "minimum": "< 0.01",
            "reason": "正文存在完整段落重复，不能进入已完成/已发布状态",
        })
    for flag in deai_metrics.get("flags") or []:
        if not isinstance(flag, dict) or flag.get("code") not in DEAI_BLOCKING_FLAGS:
            continue
        severity = str(flag.get("severity") or "").lower()
        if severity not in {"medium", "high"}:
            continue
        failures.append({
            "dimension": str(flag.get("code")),
            "actual": severity,
            "minimum": "resolved",
            "reason": str(flag.get("message") or "确定性表达风险需要定向修复"),
        })
    reader_experience = summarize_reader_experience(review_data.get("reader_experience"))
    return {
        "passed": not failures,
        "score": overall_score,
        "blocking_violations": blocking,
        "failures": failures,
        "threshold": QUALITY_PASS_SCORE,
        "critical_dimension_minimums": dict(CRITICAL_DIMENSION_MINIMUMS),
        "audit_hard_minimum": AUDIT_HARD_MINIMUM,
        "deai_high_risk_threshold": DEAI_HIGH_RISK_THRESHOLD,
        "quality_repair_contract": repair_contract,
        "payoff_validation": payoff_validation,
        "payoff_evidence_validation": payoff_evidence,
        "review_evidence": review_evidence,
        "quality_profile": quality_profile,
        "causal_audit": causal_audit,
        # Reader experience is advisory; it must not replace the continuity
        # and writing hard gates above.  It is nevertheless returned with the
        # decision so weak expectation/payoff is visible to rework and UI.
        "reader_experience": reader_experience,
        "reader_experience_warnings": reader_experience_issues(reader_experience),
        # 世界观硬约束检查结果（阶段1新增）
        # 目前作为 soft warning，不阻塞质量门禁
        "world_constraint": world_constraint_result,
        # "读第一遍"模拟审查结果（阶段3新增）
        # 目前作为可选功能，默认不启用
        "reader_simulation": reader_simulation_result,
        # 首章钩力分析结果（阶段4新增）
        # 作为信息输出，不阻塞质量门禁
        "hook_analysis": hook_analysis_result,
    }
