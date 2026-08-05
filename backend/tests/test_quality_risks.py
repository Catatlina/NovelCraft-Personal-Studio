from __future__ import annotations

from app.services.quality_risks import (
    build_quality_repair_contract,
    evaluate_editor_review_gate,
)
from app.v7.quality.audit_dimensions import AUDIT_DIMENSIONS


def _strong_review(**extra):
    review = {
        "score": 92,
        "dimensions": {
            "prose": 92,
            "plot": 92,
            "logic_consistency": 92,
            "pace": 92,
            "foreshadowing": 92,
        },
        "issues": [],
    }
    review.update(extra)
    return review


def test_material_pacing_logic_and_ai_risks_block_high_average_review():
    gate = evaluate_editor_review_gate(
        _strong_review(
            issues=[
                {"dimension": "pacing", "severity": "medium", "description": "转折前铺垫不足"},
                {"dimension": "plot_logic", "severity": "high", "description": "人物选择缺少因果依据"},
                {"dimension": "writing_quality", "severity": "medium", "description": "句式过于工整，有 AI 腔"},
            ]
        ),
        chars=2600,
        minimum_chars=2000,
    )

    assert gate["passed"] is False
    assert set(gate["quality_repair_contract"]["blocking_categories"]) == {
        "pacing", "plot_logic", "ai_feel",
    }
    assert len(gate["quality_repair_contract"]["required_repair_feedback"]) == 3


def test_low_generic_note_does_not_create_false_blocker():
    gate = evaluate_editor_review_gate(
        _strong_review(issues=["节奏可加强"]),
        chars=2600,
        minimum_chars=2000,
    )

    assert gate["passed"] is True
    assert gate["quality_repair_contract"]["blocking_categories"] == []


def test_continuity_without_evidence_is_fail_closed():
    contract = build_quality_repair_contract(
        _strong_review(),
        dimension_minimums={"continuity": 85},
        continuity={"status": "unchecked", "error": "continuity service unavailable"},
    )

    assert contract["passed"] is False
    assert contract["blocking_categories"] == ["continuity"]
    assert "可验证" in contract["required_repair_feedback"][0]


def test_editor_score_below_product_bar_cannot_pass_even_without_issue_text():
    gate = evaluate_editor_review_gate(
        _strong_review(score=84),
        chars=2600,
        minimum_chars=2000,
    )

    assert gate["passed"] is False
    assert any(item["dimension"] == "overall_score" for item in gate["failures"])


def _canonical_review(audit_complete: bool = True):
    return {
        "canonical_engine": "v7",
        "overall_score": 90,
        "dimension_scores": {
            "consistency": 90,
            "character_voice": 90,
            "pacing": 90,
            "plot_logic": 90,
            "writing_quality": 90,
            "emotional_impact": 90,
            "constraint_compliance": 90,
        },
        "audit_report": {
            "schema_version": "33d-v1",
            "count": len(AUDIT_DIMENSIONS),
            "complete": audit_complete,
            "source": "llm" if audit_complete else "macro_projection",
            "coverage": 1.0 if audit_complete else 0.0,
            "items": {
                item.key: {
                    "score": 90,
                    "evidence": "原文证据" if audit_complete else "",
                    "repair": "无需修复",
                    "source": "llm" if audit_complete else "macro_projection",
                }
                for item in AUDIT_DIMENSIONS
            },
        },
        "reader_experience": {
            "expectation": 90,
            "conflict": 90,
            "payoff": 90,
            "emotion_shift": 90,
            "worth_continuing": 90,
        },
        "provenance": {
            "engine": "v7",
            "audit_source": "v7.review.33_dimension",
            "prompt_name": "v7.review.33_dimension",
            "prompt_version": "1.1.0",
            "model": "test-model",
            "text_hash": "hash",
        },
        "issues": [],
        "constraint_violations": [],
    }


def test_canonical_editor_gate_uses_same_v7_evidence_gate_as_generation():
    incomplete = evaluate_editor_review_gate(_canonical_review(False), chars=2600, minimum_chars=2000)
    assert incomplete["passed"] is False
    assert any(item["dimension"] == "review_evidence_incomplete" for item in incomplete["failures"])

    complete = evaluate_editor_review_gate(_canonical_review(True), chars=2600, minimum_chars=2000)
    assert complete["passed"] is True
    assert complete["canonical_gate"]["review_evidence"]["passed"] is True
