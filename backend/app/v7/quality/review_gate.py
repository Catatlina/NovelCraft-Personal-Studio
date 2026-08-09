"""Fail-closed status gate for canonical V7 chapter reviews."""
from __future__ import annotations

from typing import Any

from .review_evidence import validate_review_evidence


def _canonical_status_view(review_data: dict[str, Any] | None) -> dict[str, Any]:
    """Flatten the persisted V7 review envelope for final status decisions."""
    source = review_data if isinstance(review_data, dict) else {}
    nested = source.get("canonical_review")
    result = dict(nested) if isinstance(nested, dict) else {}
    result.update(source)
    return result


def reviewed_gate_failures(review_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return blockers that make canonical V7 ineligible for ``reviewed``."""
    data = _canonical_status_view(review_data)
    if data.get("canonical_engine") != "v7":
        return []

    failures: list[dict[str, Any]] = []
    continuity = data.get("continuity")
    if not isinstance(continuity, dict) or continuity.get("passed") is not True:
        failures.append({
            "dimension": "continuity",
            "actual": continuity.get("status") if isinstance(continuity, dict) else "missing",
            "minimum": "passed",
            "reason": "V7 跨章连续性未通过，不能标记为 reviewed",
        })

    final_audit = data.get("final_continuity_audit")
    final_continuity = final_audit.get("continuity") if isinstance(final_audit, dict) else None
    if not isinstance(final_continuity, dict) or final_continuity.get("passed") is not True:
        failures.append({
            "dimension": "final_continuity_audit",
            "actual": final_continuity.get("status") if isinstance(final_continuity, dict) else "missing",
            "minimum": "passed",
            "reason": "最终连续性审计未通过或缺失，不能标记为 reviewed",
        })

    evidence = data.get("review_evidence")
    if not isinstance(evidence, dict) or evidence.get("passed") is not True:
        evidence = validate_review_evidence(data, require_continuity=True)
    if evidence.get("passed") is not True:
        failures.append({
            "dimension": "review_evidence",
            "actual": evidence.get("missing") or "incomplete",
            "minimum": "complete",
            "reason": "；".join(evidence.get("issues") or ["V7 审阅证据链不完整"]),
        })

    transition_contract = data.get("transition_contract")
    conflicts = transition_contract.get("state_conflicts") if isinstance(transition_contract, dict) else []
    for conflict in conflicts or []:
        if not isinstance(conflict, dict):
            continue
        if str(conflict.get("severity") or "").lower() == "high" and str(
            conflict.get("resolution_status") or ""
        ).lower() != "resolved":
            failures.append({
                "dimension": "state_conflict",
                "actual": "high",
                "minimum": "resolved",
                "reason": str(conflict.get("description") or conflict.get("message") or "存在未解决的高等级状态冲突"),
            })
    return failures


def can_mark_reviewed(review_data: dict[str, Any] | None) -> bool:
    """Fail closed at every persistence boundary that can publish a chapter."""
    return not reviewed_gate_failures(review_data)
