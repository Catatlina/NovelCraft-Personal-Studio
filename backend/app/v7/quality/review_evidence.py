"""One truthful evidence contract shared by V7 review surfaces.

The product has several ways to display a review: generation-time review,
the editor's live audit, and the review page.  A score without its source
evidence is not a completed review, so this module turns the required pieces
into one small, serialisable read model.

This is intentionally deterministic.  It does not invent scores or evidence
when an older provider only returned the seven macro dimensions; it reports
the missing pieces so the caller can keep the chapter in a review hold.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ...services.reader_experience import READER_EXPERIENCE_KEYS
from .audit_dimensions import AUDIT_DIMENSIONS


REVIEW_EVIDENCE_SCHEMA_VERSION = "review-evidence-v1"
_MACRO_DIMENSIONS = (
    "consistency",
    "character_voice",
    "pacing",
    "plot_logic",
    "writing_quality",
    "emotional_impact",
    "constraint_compliance",
)
_PROVENANCE_FIELDS = (
    "engine",
    "audit_source",
    "prompt_name",
    "prompt_version",
    "model",
    "text_hash",
)


def _is_score(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 100


def _text(value: Any) -> str:
    return str(value or "").strip()


def _continuity(review: dict[str, Any]) -> dict[str, Any]:
    value = review.get("continuity")
    if isinstance(value, dict):
        return value
    final = review.get("final_continuity_audit")
    if isinstance(final, dict) and isinstance(final.get("continuity"), dict):
        return final["continuity"]
    return {}


def _audit_component(review: dict[str, Any]) -> dict[str, Any]:
    report = review.get("audit_report")
    report = report if isinstance(report, dict) else {}
    items = report.get("items") if isinstance(report.get("items"), dict) else {}
    expected = {item.key for item in AUDIT_DIMENSIONS}
    missing = sorted(expected - set(items))
    unscored: list[str] = []
    missing_evidence: list[str] = []
    projected: list[str] = []
    for definition in AUDIT_DIMENSIONS:
        item = items.get(definition.key)
        if not isinstance(item, dict) or not _is_score(item.get("score")):
            unscored.append(definition.key)
        if not isinstance(item, dict) or not _text(item.get("evidence")):
            missing_evidence.append(definition.key)
        if isinstance(item, dict) and str(item.get("source") or "") != "llm":
            projected.append(definition.key)

    issues = [
        *(f"缺少审计项：{', '.join(missing)}" for _ in [0] if missing),
        *(f"审计项未评分：{', '.join(unscored)}" for _ in [0] if unscored),
        *(f"审计项没有原文证据：{', '.join(missing_evidence)}" for _ in [0] if missing_evidence),
        *(f"审计项来自兼容投影而非逐项模型审计：{', '.join(projected)}" for _ in [0] if projected),
    ]
    complete = bool(
        report.get("schema_version") == "33d-v1"
        and report.get("count") == len(AUDIT_DIMENSIONS)
        and not missing
        and not unscored
        and not missing_evidence
        and not projected
        and report.get("complete") is True
    )
    missing_fields = sorted(set([*missing, *unscored, *missing_evidence]))
    return {
        "status": "complete" if complete else "incomplete",
        "required": len(AUDIT_DIMENSIONS),
        "scored": len(AUDIT_DIMENSIONS) - len(unscored),
        "with_evidence": len(AUDIT_DIMENSIONS) - len(missing_evidence),
        "source": report.get("source") or "unknown",
        "coverage": float(report.get("coverage") or 0.0),
        "missing": missing_fields,
        "projected": projected,
        "issues": issues,
        "complete": complete,
    }


def _supporting_component(review: dict[str, Any], key: str) -> dict[str, Any]:
    report = review.get("audit_report") if isinstance(review.get("audit_report"), dict) else {}
    items = report.get("items") if isinstance(report.get("items"), dict) else {}
    item = items.get(key) if isinstance(items.get(key), dict) else {}
    score = item.get("score")
    evidence = _text(item.get("evidence"))
    complete = _is_score(score) and bool(evidence) and item.get("source") == "llm"
    return {
        "status": "complete" if complete else "incomplete",
        "score": score if _is_score(score) else None,
        "evidence": evidence,
        "repair": _text(item.get("repair")),
        "source": item.get("source") or "unknown",
        "complete": complete,
    }


def _provenance_component(review: dict[str, Any]) -> dict[str, Any]:
    provenance = review.get("provenance")
    provenance = provenance if isinstance(provenance, dict) else {}
    missing = [field for field in _PROVENANCE_FIELDS if not _text(provenance.get(field))]
    # ``scored_at`` is not needed to validate an old cached snapshot, but all
    # new V7 reviews write it.  Expose it as a warning rather than making old
    # persisted evidence silently disappear from the page.
    warnings = [] if _text(provenance.get("scored_at")) else ["缺少评分时间戳；该记录可能来自旧缓存"]
    complete = not missing
    return {
        "status": "complete" if complete else "incomplete",
        "missing": missing,
        "warnings": warnings,
        "complete": complete,
        "snapshot": dict(provenance),
    }


def build_review_evidence(
    review: dict[str, Any] | None,
    *,
    require_continuity: bool = False,
) -> dict[str, Any]:
    """Build a stable evidence read model without fabricating missing data."""
    review = review if isinstance(review, dict) else {}
    macro_scores = review.get("dimension_scores") if isinstance(review.get("dimension_scores"), dict) else {}
    macro_missing = [key for key in _MACRO_DIMENSIONS if not _is_score(macro_scores.get(key))]
    reader_scores = review.get("reader_experience") if isinstance(review.get("reader_experience"), dict) else {}
    reader_missing = [key for key in READER_EXPERIENCE_KEYS if not _is_score(reader_scores.get(key))]
    audit = _audit_component(review)
    continuity = _continuity(review)
    continuity_checked = bool(
        continuity.get("checked") is True
        and (
            _text(continuity.get("narrative_flow"))
            or isinstance(continuity.get("deterministic_contract"), dict)
            or isinstance(continuity.get("deterministic"), dict)
        )
    )
    continuity_component = {
        "status": "complete" if continuity_checked else "not_checked",
        "checked": continuity_checked,
        "score": continuity.get("model_score"),
        "narrative_flow": _text(continuity.get("narrative_flow")),
        "gaps": list(continuity.get("gaps") or continuity.get("issues") or []),
        "deterministic_contract": continuity.get("deterministic_contract")
        or continuity.get("deterministic")
        or {},
        "complete": continuity_checked,
    }
    provenance = _provenance_component(review)
    missing: list[str] = []
    if macro_missing:
        missing.append("macro_scores")
    if reader_missing:
        missing.append("reader_experience")
    if not audit["complete"]:
        missing.append("audit_33")
    if not provenance["complete"]:
        missing.append("provenance")
    if require_continuity and not continuity_component["complete"]:
        missing.append("continuity")

    complete = not missing
    return {
        "schema_version": REVIEW_EVIDENCE_SCHEMA_VERSION,
        "status": "complete" if complete else "incomplete",
        "complete": complete,
        "required_continuity": require_continuity,
        "missing": missing,
        "macro_scores": {
            "status": "complete" if not macro_missing else "incomplete",
            "scored": len(_MACRO_DIMENSIONS) - len(macro_missing),
            "required": len(_MACRO_DIMENSIONS),
            "missing": macro_missing,
            "complete": not macro_missing,
        },
        "reader_experience": {
            "status": "complete" if not reader_missing else "incomplete",
            "scored": len(READER_EXPERIENCE_KEYS) - len(reader_missing),
            "required": len(READER_EXPERIENCE_KEYS),
            "missing": reader_missing,
            "complete": not reader_missing,
        },
        "audit_33": audit,
        "timeline": _supporting_component(review, "timeline"),
        "character_arcs": _supporting_component(review, "character_arc_progress"),
        "continuity": continuity_component,
        "provenance": provenance,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def validate_review_evidence(
    review: dict[str, Any] | None,
    *,
    require_continuity: bool = False,
) -> dict[str, Any]:
    """Return an explicit pass/fail result for the evidence contract."""
    evidence = build_review_evidence(review, require_continuity=require_continuity)
    return {
        **evidence,
        "passed": evidence["complete"],
        "issues": [f"缺少或不可验证的审计证据：{item}" for item in evidence["missing"]],
    }
