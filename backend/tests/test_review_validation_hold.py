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

    # In the current 番茄爽文 profile payoff anchors are advisory because the
    # lexical matcher can false-negative; the review contract still exposes
    # the invalid evidence to callers.
    assert result["passed"] is True
    assert result["payoff_evidence_validation"]["passed"] is False
    assert not any(item["dimension"] == "payoff_evidence" for item in result["failures"])


def test_execute_repairs_only_invalid_payoff_evidence(monkeypatch):
    chapter_text = "沈砚抬手按住石门，石门当场退开，队伍里有人倒吸一口凉气。"

    class FakeGateway:
        def __init__(self):
            self.calls = 0

        async def generate_json(self, *_args, **_kwargs):
            self.calls += 1
            usage = {"tokens_input": 10, "tokens_output": 5, "cost": 0.01, "model": "test"}
            if self.calls == 1:
                return {
                    "data": {
                        "dimension_scores": {key: 90 for key in REVIEW_DIMENSIONS},
                        "overall_score": 90,
                        "reader_experience": {
                            "expectation": 90,
                            "conflict": 90,
                            "payoff": 90,
                            "emotion_shift": 90,
                            "worth_continuing": 90,
                        },
                        "audit_dimensions": {
                            item.key: {"score": 90, "evidence": "evidence", "repair": "none"}
                            for item in AUDIT_DIMENSIONS
                        },
                        "payoff_evidence": [{"type": "能力展示", "result": "石门退开"}],
                    },
                    "usage": usage,
                }
            return {
                "data": {
                    "payoff_evidence": [{
                        "type": "能力展示",
                        "anchor": "石门当场退开",
                        "result": "石门退开，队伍获得通路",
                        "reaction": "队伍震惊",
                    }],
                },
                "usage": usage,
            }

    engine = object.__new__(ReviewEngine)
    engine.ai_gateway = FakeGateway()
    engine.record_usage = lambda usage: None
    plan = EngineResult(success=True, result={
        "chapter_number": 2,
        "chapter_text": chapter_text,
        "constraints_to_check": [],
        "known_characters": [],
        "known_plot": [],
        "previous_chapter_tail": "",
        "previous_transition_contract": {},
        "chapter_plan": {},
        "scene_plan": {},
        "deai_metrics": {},
        "pov_metrics": {},
        "content_policy": {},
        "generation_quality": {},
        "quality_profile": {"profile_id": "test"},
        "payoff_contract": {"visible_result": "石门退开"},
    })

    result = asyncio.run(engine.execute(plan))

    assert result.success is True
    assert result.result["payoff_evidence_repair"]["passed"] is True
    assert result.result["payoff_evidence_validation"]["passed"] is True
    assert result.result["payoff_evidence"][0]["anchor"] == "石门当场退开"
    assert engine.ai_gateway.calls == 2
