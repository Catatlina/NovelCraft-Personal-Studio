"""Provider-backed semantic assessments used by the publishing gates.

This module deliberately has no heuristic fallback.  A configured publication
run either receives a validated result from the real gateway or raises, leaving
the chapter blocked and the failed provider attempt in the AI ledger.
"""
from __future__ import annotations

import hashlib
from typing import Any, Optional


def _mutation_id(task: str, project_id: str, subject_id: str, text: str = "") -> str:
    digest = hashlib.sha256(
        f"{task}\n{project_id}\n{subject_id}\n{text}".encode("utf-8")
    ).hexdigest()
    return f"publishing-{task}-{digest}"


def _complete(**kwargs: Any) -> dict[str, Any]:
    # Lazy import keeps deterministic gate/unit modules usable without loading
    # the full provider/database stack.
    from app.gateway import complete

    return complete(**kwargs)


def assess_payoff_semantically(
    *,
    project_id: str,
    chapter_id: str,
    text: str,
    platform: str,
    user_id: Optional[str] = None,
) -> dict[str, Any]:
    """Ask the real provider for a structured, evidence-backed payoff review."""
    if not project_id or not chapter_id or not platform:
        raise ValueError("语义爽点检测需要 project_id、chapter_id 和 platform")
    if not text.strip():
        raise ValueError("语义爽点检测不能处理空正文")

    output = _complete(
        run_id=None,
        node_key=f"publishing.payoff_semantic:{chapter_id}",
        project_id=project_id,
        task_type="publishing_payoff_semantic",
        prompt_name="publishing.payoff_semantic",
        variables={
            "chapter_id": chapter_id,
            "platform": platform,
            "chapter_text": text,
        },
        user_id=user_id,
        client_mutation_id=_mutation_id(
            "payoff-semantic", project_id, chapter_id, text
        ),
    )
    payoffs = output.get("payoffs")
    if not isinstance(payoffs, list):
        raise RuntimeError("Provider语义爽点评估缺少 payoffs 数组")
    if int(output.get("payoff_count", -1)) != len(payoffs):
        raise RuntimeError("Provider语义爽点评估的 payoff_count 与证据数量不一致")

    normalized: list[dict[str, Any]] = []
    for item in payoffs:
        if not isinstance(item, dict):
            raise RuntimeError("Provider语义爽点评估包含无效 payoff 证据")
        required = ("event", "evidence_quote", "reader_effect", "consequence")
        if any(not str(item.get(key) or "").strip() for key in required):
            raise RuntimeError("Provider语义爽点评估包含缺少证据或后果的 payoff")
        confidence = float(item.get("confidence", 0))
        if confidence < 0.6:
            raise RuntimeError("Provider语义爽点评估的证据置信度不足")
        normalized.append({
            "event": str(item["event"]).strip(),
            "evidence_quote": str(item["evidence_quote"]).strip(),
            "reader_effect": str(item["reader_effect"]).strip(),
            "consequence": str(item["consequence"]).strip(),
            "confidence": confidence,
        })

    score = float(output.get("semantic_score", -1))
    if not 0 <= score <= 100:
        raise RuntimeError("Provider语义爽点评估的 semantic_score 无效")
    return {
        "payoff_count": len(normalized),
        "payoffs": normalized,
        "ending_pressure": bool(output.get("ending_pressure")),
        "semantic_score": score,
        "rationale": str(output.get("rationale") or "").strip(),
        "provenance": {
            "gateway": "v6.complete",
            "task_type": "publishing_payoff_semantic",
            "prompt_name": "publishing.payoff_semantic",
            "project_id": project_id,
            "chapter_id": chapter_id,
            "platform": platform,
        },
    }


def generate_disclosure_text(
    *,
    project_id: str,
    variant_id: str,
    variant_title: str,
    variant_synopsis: str,
    platform: str,
    ai_usage_policy: str,
    source_models: Optional[list[str]] = None,
    chapter_context: str = "",
    user_id: Optional[str] = None,
) -> dict[str, Any]:
    """Generate a factual disclosure draft; caller must keep it unconfirmed."""
    if not project_id or not variant_id or not platform:
        raise ValueError("AI披露生成需要 project_id、variant_id 和 platform")
    output = _complete(
        run_id=None,
        node_key=f"publishing.ai_disclosure:{variant_id}",
        project_id=project_id,
        task_type="publishing_ai_disclosure",
        prompt_name="publishing.ai_disclosure",
        variables={
            "variant_title": variant_title,
            "variant_synopsis": variant_synopsis,
            "platform": platform,
            "ai_usage_policy": ai_usage_policy,
            "source_models": source_models or [],
            "chapter_context": chapter_context,
        },
        user_id=user_id,
        client_mutation_id=_mutation_id("ai-disclosure", project_id, variant_id),
    )
    text = str(output.get("disclosure_text") or "").strip()
    if len(text) < 20:
        raise RuntimeError("Provider生成的AI披露文案过短")
    models = output.get("ai_models_used") or []
    if (
        not isinstance(models, list)
        or not models
        or any(not str(model).strip() for model in models)
    ):
        raise RuntimeError("Provider生成的AI模型清单无效")
    estimate = output.get("usage_estimate")
    if estimate is not None and not 0 <= float(estimate) <= 100:
        raise RuntimeError("Provider生成的AI使用比例无效")
    return {
        "disclosure_text": text,
        "ai_models_used": [str(model).strip() for model in models],
        "ai_usage_estimate": float(estimate) if estimate is not None else None,
        "rationale": str(output.get("rationale") or "").strip(),
        "provenance": {
            "gateway": "v6.complete",
            "task_type": "publishing_ai_disclosure",
            "prompt_name": "publishing.ai_disclosure",
            "project_id": project_id,
            "variant_id": variant_id,
            "platform": platform,
        },
    }
