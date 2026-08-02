from __future__ import annotations

from app.services.quality_risks import (
    build_quality_repair_contract,
    evaluate_editor_review_gate,
)


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
