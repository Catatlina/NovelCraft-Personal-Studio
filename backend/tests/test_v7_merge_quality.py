from __future__ import annotations

import asyncio

from app.v7.generation.generation_engine import ContextAssembler
from app.v7.engines.base import EngineResult
from app.v7.engines.memory_engine import MemoryEngine
from app.v7.integration.quality import QUALITY_PASS_SCORE, evaluate_review
from app.v7.integration.v6_bridge import (
    build_transition_contract,
    generation_key,
    _tiptap_body,
)
from app.v7.quality.continuity import validate_transition_contract


def test_quality_gate_rejects_weak_continuity_even_when_average_is_high():
    result = evaluate_review(
        {
            "overall_score": 91,
            "dimension_scores": {
                "consistency": 72,
                "character_voice": 92,
                "plot_logic": 93,
                "writing_quality": 94,
                "constraint_compliance": 95,
            },
        }
    )

    assert result["passed"] is False
    assert any(item["dimension"] == "consistency" for item in result["failures"])


def test_quality_gate_rejects_material_duplicate_paragraphs():
    result = evaluate_review(
        {
            "overall_score": 95,
            "dimension_scores": {
                "consistency": 95,
                "character_voice": 95,
                "plot_logic": 95,
                "pacing": 95,
                "writing_quality": 95,
                "constraint_compliance": 95,
            },
            "deai_metrics": {
                "risk_score": 10,
                "duplicate_paragraphs": {"duplicate_ratio": 0.74},
                "flags": [],
            },
        }
    )

    assert result["passed"] is False
    assert any(item["dimension"] == "duplicate_paragraph" for item in result["failures"])


def test_quality_gate_rejects_failed_generation_quality_even_with_high_scores():
    result = evaluate_review(
        {
            "overall_score": 96,
            "dimension_scores": {
                "consistency": 96,
                "character_voice": 96,
                "plot_logic": 96,
                "pacing": 96,
                "writing_quality": 96,
                "constraint_compliance": 96,
            },
            "generation_quality": {
                "passed": False,
                "failures": [
                    {
                        "code": "continuation_duplicate",
                        "severity": "high",
                        "message": "续写候选重复",
                    }
                ],
            },
        }
    )

    assert result["passed"] is False
    assert any(item["dimension"] == "continuation_duplicate" for item in result["failures"])


def test_continuity_gate_rejects_high_confidence_state_conflict():
    previous = build_transition_contract(
        chapter_number=1,
        title="第一章",
        text="他站在诊所门口。",
        summary="主角抵达诊所。",
        word_count=8,
        review_score=90,
        dimension_scores={"consistency": 90},
        memory_items=[{"category": "plot_events", "key": "clinic", "summary": "抵达诊所"}],
    )
    current = build_transition_contract(
        chapter_number=2,
        title="第二章",
        text="他在海边醒来。",
        summary="主角发现新的线索。",
        word_count=8,
        review_score=96,
        dimension_scores={"consistency": 96},
        previous_context={"previous_transition_contract": previous},
        memory_items=[{"category": "plot_events", "key": "clinic", "summary": "离开诊所"}],
    )
    result = validate_transition_contract(
        current,
        chapter_number=2,
        previous_contract=previous,
        state_conflicts=[
            {"key": "location", "description": "上一章仍在诊所，本章无过渡直接出现在海边", "severity": "high"}
        ],
    )

    assert result["passed"] is False
    assert any(item["code"] == "state_conflict" for item in result["issues"])


def test_rejected_chapter_is_not_loaded_as_future_context():
    class State:
        async def list_states(self, _state_type, limit=200):
            return [
                {"key": "chapter_1", "value": {"chapter_number": 1, "passed_review": True}},
                {"key": "chapter_2", "value": {"chapter_number": 2, "passed_review": False}},
            ]

    class Brain:
        state = State()

    chapters = asyncio.run(ContextAssembler(Brain()).load_previous_chapters(3, count=5))
    assert [item["chapter_number"] for item in chapters] == [1]


def test_memory_extraction_defers_writes_for_unaccepted_draft():
    result = asyncio.run(
        MemoryEngine.update(
            None,
            EngineResult(
                success=True,
                result={
                    "apply_updates": False,
                    "chapter_number": 2,
                    "valid_items": [{"key": "door", "state_type": "plot"}],
                    "rejected_items": [],
                    "conflicts": [],
                    "chapter_summary": "草稿",
                },
            ),
        )
    )

    assert result.success is True
    assert result.result["deferred"] is True
    assert result.result["brain_updated"] is False
    assert result.result["states_applied"] == 0


def test_context_budget_keeps_cross_chapter_anchors_after_state_compression():
    layers = {
        "characters": [
            {"key": f"character_{i}", "value": {"summary": "旧设定" * 20}}
            for i in range(60)
        ],
        "world": [],
        "plot": [],
        "active_goals": [],
        "constraints": [{"name": "能力代价", "description": "使用能力必须付出代价", "severity": "high"}],
        "recap": ["第9章梗概：门还没有关上。"],
        "previous_transition_contract": {"open_threads": [{"key": "door", "summary": "门未关"}]},
        "previous_tail": "上一章最后，周远山把手按在门缝上，门内传来三下敲击。",
    }

    rendered = ContextAssembler._fit_context(layers, 900)

    assert "上一章最后" in rendered
    assert "门未关" in rendered
    assert "能力代价" in rendered


def test_transition_contract_is_durable_and_has_next_bridge():
    contract = build_transition_contract(
        chapter_number=10,
        title="第10章 门后的声音",
        text="周远山没有松手。门内又响了三下。",
        summary="周远山确认门后有人，但没有开门。",
        word_count=18,
        review_score=89,
        dimension_scores={"consistency": 90, "writing_quality": 88},
        reader_experience={
            "expectation": 86,
            "conflict": 84,
            "payoff": 82,
            "emotion_shift": 88,
            "worth_continuing": 90,
        },
        previous_context={"previous_tail": "上一章结尾", "previous_transition_contract": {"x": 1}},
        memory_items=[
            {"category": "foreshadowing", "key": "door", "summary": "门后有人"},
        ],
        constraints=[{"name": "现实背景", "description": "不得出现超自然", "severity": "high"}],
    )

    assert contract["chapter_number"] == 10
    assert contract["open_threads"][0]["key"] == "door"
    assert "周远山没有松手" in contract["next_chapter_bridge"]
    assert contract["forbidden_changes"][0]["name"] == "现实背景"
    assert contract["quality"]["reader_experience"]["worth_continuing"] == 90


def test_reader_experience_is_visible_but_not_a_substitute_for_hard_gate():
    result = evaluate_review(
        {
            "overall_score": 90,
            "dimension_scores": {
                "consistency": 90,
                "character_voice": 90,
                "plot_logic": 90,
                "pacing": 90,
                "writing_quality": 90,
                "constraint_compliance": 90,
            },
            "reader_experience": {
                "expectation": 55,
                "conflict": 80,
                "payoff": 70,
                "emotion_shift": 80,
                "worth_continuing": 58,
            },
        }
    )

    assert result["passed"] is True
    assert result["reader_experience"]["status"] == "warning"
    assert len(result["reader_experience_warnings"]) == 2


def test_v6_bridge_uses_stable_generation_key_and_tiptap_body():
    novel_id = "novel-1"
    assert generation_key(novel_id, 3) == generation_key(novel_id, 3)
    assert generation_key(novel_id, 3) != generation_key(novel_id, 4)

    body = _tiptap_body(["第一段", "第二段"])
    assert body["type"] == "doc"
    assert body["content"][1]["content"][0]["text"] == "第二段"
    assert body["text"] == "第一段\n\n第二段"


def test_story_director_result_contract_exposes_bridge_evidence():
    from pathlib import Path

    source = Path(__file__).parents[1] / "app" / "v7" / "director" / "story_director.py"
    text = source.read_text(encoding="utf-8")
    assert '"transition_contract": update_result.get("transition_contract", {})' in text
    assert '"v6_content_id": (update_result.get("v6_content") or {}).get("content_id")' in text


def test_quality_gate_default_is_the_reported_85_point_bar():
    assert QUALITY_PASS_SCORE == 85.0
