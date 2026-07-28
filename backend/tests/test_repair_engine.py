"""Unit tests for V3 Repair Engine (§8) — tier classification + local repair.

Real logic only — no mock providers.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.gateway import validate_task_output, _RepairLocalOutput, _ReplanChapterOutput  # noqa: E402
from app.workers.tasks import _classify_repair_level, _apply_replacements  # noqa: E402


def test_classify_sentence_level():
    out = {"checks": {"文字": {"status": "fail", "issues": ["发现错别字"]}}}
    res = _classify_repair_level(out)
    assert res["level"] == "sentence"
    assert res["action"] == "repair_local"


def test_classify_paragraph_level():
    out = {"checks": {"表达": {"status": "fail", "issues": ["段落冗长拖沓"]}}}
    res = _classify_repair_level(out)
    assert res["level"] == "paragraph"
    assert res["action"] == "repair_local"


def test_classify_chapter_level():
    out = {"checks": {"逻辑": {"status": "fail", "issues": ["前后事实矛盾"]}}}
    res = _classify_repair_level(out)
    assert res["level"] == "chapter"
    assert res["action"] == "rewrite_chapter"


def test_classify_plot_level():
    out = {"checks": {"结构": {"status": "fail", "issues": ["剧情崩坏，偏离大纲"]}}}
    res = _classify_repair_level(out)
    assert res["level"] == "plot"
    assert res["action"] == "replan_chapter"


def test_classify_severity_prefers_plot_over_sentence():
    out = {"checks": {
        "文字": {"status": "fail", "issues": ["错别字"]},
        "结构": {"status": "fail", "issues": ["剧情崩坏"]},
    }}
    res = _classify_repair_level(out)
    assert res["level"] == "plot"  # most severe wins


def test_classify_none_when_all_pass():
    out = {"checks": {"文字": {"status": "pass", "issues": []}, "逻辑": {"status": "pass", "issues": []}}}
    res = _classify_repair_level(out)
    assert res["level"] == "none"
    assert res["action"] is None


def test_apply_replacements_list_body():
    body = ["他是一个好人。", "她默默走了。"]
    new_body, applied, skipped = _apply_replacements(
        body, [{"anchor": "他是一个好人。", "replacement": "他是个善良的人。"}]
    )
    assert applied == ["他是一个好人。"]
    assert new_body[0] == "他是个善良的人。"
    assert new_body[1] == "她默默走了。"


def test_apply_replacements_skips_unmatched():
    body = "原文片段A。片段B。"
    new_body, applied, skipped = _apply_replacements(
        body, [{"anchor": "不存在的片段", "replacement": "x"}]
    )
    assert applied == []
    assert skipped == ["不存在的片段"]
    assert new_body == body


def test_repair_local_contract_requires_replacements():
    try:
        _RepairLocalOutput.model_validate({"replacements": []})
        assert False, "empty replacements should be rejected"
    except Exception:
        pass
    out = validate_task_output("repair_local", {"replacements": [
        {"anchor": "原句", "replacement": "改后"}
    ]})
    assert len(out["replacements"]) == 1


def test_replan_chapter_contract():
    out = validate_task_output("replan_chapter", {
        "revised_outline": {"seq": 1, "title": "改后章", "outline": "新梗概"},
        "rationale": "原结构导致剧情崩坏，重新规划以回收伏笔",
    })
    assert "revised_outline" in out
    assert len(out["rationale"]) >= 10
