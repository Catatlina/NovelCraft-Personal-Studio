from __future__ import annotations

import pytest

from app.v7.quality.publishing_gates import gate_payoff_density
from app.v7.quality.semantic_assessments import assess_payoff_semantically, generate_disclosure_text
from app.v7.quality.statistics_v1 import compute_statistics


def _assessment(**overrides):
    value = {
        "payoff_count": 1,
        "payoffs": [{
            "event": "主角拿到关键证据",
            "evidence_quote": "账本上的印章是真的。",
            "reader_effect": "反击有了落点",
            "consequence": "幕后人会立刻追杀",
            "confidence": 0.92,
        }],
        "ending_pressure": True,
        "semantic_score": 84,
        "rationale": "有结果、反馈和新危机",
        "provenance": {"gateway": "v6.complete"},
    }
    value.update(overrides)
    return value


def test_semantic_payoff_gate_uses_provider_evidence_and_provenance():
    result = gate_payoff_density(
        "正文没有依赖关键词。",
        compute_statistics("正文没有依赖关键词。"),
        semantic_assessment=_assessment(),
    )

    assert result.passed is True
    assert result.runner == "v6.gateway"
    assert result.evidence["mode"] == "semantic_provider"
    assert result.evidence["provenance"]["gateway"] == "v6.complete"


def test_semantic_payoff_gate_fails_closed_on_low_score_or_missing_pressure():
    result = gate_payoff_density(
        "正文。",
        compute_statistics("正文。"),
        semantic_assessment=_assessment(semantic_score=59, ending_pressure=False),
    )

    assert result.passed is False
    assert {item["type"] for item in result.issues} == {
        "no_next_chapter_pressure",
        "semantic_score_below_threshold",
    }


def test_provider_assessment_rejects_mismatched_evidence(monkeypatch):
    monkeypatch.setattr(
        "app.v7.quality.semantic_assessments._complete",
        lambda **_: _assessment(payoff_count=2),
    )

    with pytest.raises(RuntimeError, match="payoff_count"):
        assess_payoff_semantically(
            project_id="project-1",
            chapter_id="chapter-1",
            text="正文。",
            platform="fanqie",
        )


def test_provider_disclosure_is_validated_and_kept_as_draft(monkeypatch):
    monkeypatch.setattr(
        "app.v7.quality.semantic_assessments._complete",
        lambda **_: {
            "disclosure_text": "本作品在资料整理和文字辅助环节使用了人工智能工具，最终内容由作者人工确认。",
            "ai_models_used": ["deepseek-chat"],
            "usage_estimate": None,
            "rationale": "输入资料明确提供了模型名称",
        },
    )

    result = generate_disclosure_text(
        project_id="project-1",
        variant_id="variant-1",
        variant_title="测试作品",
        variant_synopsis="一个关于选择与代价的故事",
        platform="fanqie",
        ai_usage_policy="required_disclosure",
    )

    assert result["disclosure_text"].startswith("本作品")
    assert result["ai_models_used"] == ["deepseek-chat"]
    assert result["provenance"]["task_type"] == "publishing_ai_disclosure"


def test_provider_disclosure_rejects_missing_model_provenance(monkeypatch):
    monkeypatch.setattr(
        "app.v7.quality.semantic_assessments._complete",
        lambda **_: {
            "disclosure_text": "本作品在资料整理和文字辅助环节使用了人工智能工具，最终内容由作者人工确认。",
            "ai_models_used": [],
            "usage_estimate": None,
            "rationale": "没有提供模型来源",
        },
    )

    with pytest.raises(RuntimeError, match="模型清单无效"):
        generate_disclosure_text(
            project_id="project-1",
            variant_id="variant-1",
            variant_title="测试作品",
            variant_synopsis="一个关于选择与代价的故事",
            platform="fanqie",
            ai_usage_policy="required_disclosure",
        )
