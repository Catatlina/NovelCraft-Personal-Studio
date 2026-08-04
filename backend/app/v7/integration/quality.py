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

QUALITY_PASS_SCORE = 85.0
QUALITY_REWORK_SCORE = 80.0
MAX_REWORKS = 2

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


def evaluate_review(review_data: dict[str, Any]) -> dict[str, Any]:
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
    payoff_contract = review_data.get("payoff_contract") or {}
    payoff_validation = review_data.get("payoff_validation") or {}
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
    if payoff_evidence.get("required") and payoff_evidence.get("passed") is not True:
        failures.append({
            "dimension": "payoff_evidence",
            "actual": "missing_or_unverifiable",
            "minimum": "verifiable",
            "reason": "爽点证据无法在正文中定位",
        })
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
        "quality_profile": quality_profile,
        # Reader experience is advisory; it must not replace the continuity
        # and writing hard gates above.  It is nevertheless returned with the
        # decision so weak expectation/payoff is visible to rework and UI.
        "reader_experience": reader_experience,
        "reader_experience_warnings": reader_experience_issues(reader_experience),
    }
