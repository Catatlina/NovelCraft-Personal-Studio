"""V3 P1-② Novel DNA: structured positioning/promise/red-line fields + self-consistency.

Real-AI contract (not mocked): the plan_idea provider MUST now also emit
commercial_positioning / story_promise / forbidden_deviations in the same call
as creative_bible. A forbidden deviation must not contradict the positioning
or promise — that is a deterministic self-check stored on the novel meta.
"""
import pytest
from app.gateway import validate_task_output
from app.workers.tasks import _check_novel_dna_consistency


def test_plan_idea_accepts_novel_dna_fields():
    """gateway contract accepts (and tolerates missing) the new DNA fields."""
    out = validate_task_output("plan_idea", {
        "idea_expanded": "末世重生复仇题材，主角利用前世记忆提前布局逆转命运",
        "core_hook": "重生回来提前布局",
        "target_audience": "男频末世爱好者",
        "title_candidates": ["《末世归来》", "《重生之渊》", "《凛冬王座》"],
        "source_facts": ["重生前 2035", "醒来 2024", "主角职业工程师"],
        "design_additions": [],
        "forbidden_changes": ["不得改职业", "不得改年代", "不得加系统"],
        "downstream_deliverables": ["生成 8 卷总纲", "生成前 30 章细纲"],
        "creative_bible": "x" * 320,
        "commercial_positioning": "男频末世，硬核求生+复仇，核心爽点是信息差碾压",
        "story_promise": "看主角用前世记忆改写命运",
        "forbidden_deviations": ["禁止圣母", "禁止无理由暴富"],
    })
    assert out["commercial_positioning"]
    assert out["forbidden_deviations"] == ["禁止圣母", "禁止无理由暴富"]


def test_novel_dna_self_check_passes_when_consistent():
    dna = {
        "commercial_positioning": "男频末世硬核求生，信息差碾压",
        "story_promise": "看主角用前世记忆改写命运",
        "forbidden_deviations": ["禁止圣母", "禁止无理由暴富"],
    }
    res = _check_novel_dna_consistency(dna)
    assert res["status"] == "pass"
    assert res["checked"] is True
    assert res["issues"] == []


def test_novel_dna_self_check_fails_on_contradiction():
    """'禁止重生' contradicts a positioning that sells 重生穿越."""
    dna = {
        "commercial_positioning": "重生穿越爽文，卖点就是重生改写命运",
        "story_promise": "看主角重生后逆袭",
        "forbidden_deviations": ["禁止重生", "禁止圣母"],
    }
    res = _check_novel_dna_consistency(dna)
    assert res["status"] == "fail"
    assert any("禁止重生" in i for i in res["issues"])


def test_novel_dna_self_check_graceful_on_empty():
    assert _check_novel_dna_consistency({})["status"] == "pass"
    assert _check_novel_dna_consistency(None)["status"] == "pass"
    assert _check_novel_dna_consistency("not a dict")["status"] == "pass"
