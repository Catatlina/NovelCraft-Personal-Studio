from __future__ import annotations

import asyncio

from app.v7.engines.base import EngineResult
from app.v7.engines.review_engine import REVIEW_DIMENSIONS, ReviewEngine
from app.v7.integration.quality import evaluate_review
from app.v7.quality.audit_dimensions import AUDIT_DIMENSIONS


def _valid_shape() -> dict:
    return {
        "chapter_number": 2,
        "overall_score": 90,
        "dimension_scores": {key: 90 for key in REVIEW_DIMENSIONS},
        "reader_experience": {
            "expectation": 90,
            "conflict": 90,
            "payoff": 90,
            "emotion_shift": 90,
            "worth_continuing": 90,
        },
        "audit_report": {
            "schema_version": "33d-v1",
            "count": len(AUDIT_DIMENSIONS),
            "items": {
                item.key: {"score": 90, "evidence": "evidence"}
                for item in AUDIT_DIMENSIONS
            },
            "coverage": 1.0,
        },
        "payoff_evidence_validation": {
            "required": True,
            "passed": False,
            "invalid": ["anchor not found"],
        },
        "issues": [],
        "constraint_violations": [],
    }


def test_invalid_review_contract_is_a_quality_hold_not_engine_failure():
    engine = object.__new__(ReviewEngine)
    result = asyncio.run(
        engine.validate(EngineResult(success=True, result=_valid_shape(), confidence=0.8))
    )

    assert result.success is True
    assert result.result["review_valid"] is False
    assert any(
        item["code"] == "payoff_evidence_invalid"
        for item in result.result["validation_failures"]
    )
    assert "review_validation_failed" in result.warnings


def test_quality_gate_keeps_review_contract_failure_blocking():
    result = evaluate_review(_valid_shape())

    assert result["passed"] is False
    assert any(item["dimension"] == "payoff_evidence" for item in result["failures"])
