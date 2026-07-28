"""V3 P1-① Chapter Function: required outline fields + pacing gate.

- blueprint_chapter_outline schema now requires function_type / chapter_goal /
  reader_expectation (missing -> invalid_output -> retry, i.e. 打回重新细纲).
- _check_chapter_function_pacing flags monotonous function_type runs (水字风险)
  and feeds the 节奏检测 dimension without blocking the consistency gate.
"""
from __future__ import annotations

import pytest

from app.gateway import OutputValidationError, validate_task_output
from app.workers.tasks import _check_chapter_function_pacing


def _outline(seq: int, ft: str) -> dict:
    return {
        "volume": 1,
        "seq": seq,
        "title": f"第{seq}章",
        "outline": "梗概",
        "beats": ["a", "b"],
        "foreshadow_plant": [],
        "foreshadow_reap": [],
        "function_type": ft,
        "chapter_goal": f"目标{seq}",
        "reader_expectation": f"期待{seq}",
    }


def test_valid_outline_with_function_fields_passes():
    out = validate_task_output(
        "blueprint_chapter_outline",
        {"chapter_outlines": [_outline(1, "开篇吸引"), _outline(2, "爽点释放"), _outline(3, "伏笔埋设")]},
    )
    assert out["chapter_outlines"][0]["function_type"] == "开篇吸引"
    assert out["chapter_outlines"][0]["chapter_goal"] == "目标1"


def test_missing_function_field_is_rejected():
    bad = _outline(1, "开篇吸引")
    del bad["function_type"]
    with pytest.raises(OutputValidationError):
        validate_task_output(
            "blueprint_chapter_outline",
            {"chapter_outlines": [bad, _outline(2, "爽点释放"), _outline(3, "伏笔埋设")]},
        )


def test_pacing_flags_monotonous_run():
    outlines = [_outline(i, "信息展示") for i in range(6)]  # 6 consecutive identical
    res = _check_chapter_function_pacing(outlines)
    assert res["status"] == "fail"
    assert any("连续" in str(i) for i in res["issues"])


def test_pacing_passes_for_varied_sequence():
    fts = ["开篇吸引", "人物成长", "关系推进", "冲突升级", "爽点释放", "转折"]
    outlines = [_outline(i + 1, ft) for i, ft in enumerate(fts)]
    res = _check_chapter_function_pacing(outlines)
    assert res["status"] == "pass"
    assert res["issues"] == []


def test_pacing_degrades_when_no_function_types():
    # Books outlined before V3 (no function_type) must not be penalised.
    legacy = [{"volume": 1, "seq": i, "title": f"第{i}章", "outline": "x"} for i in range(8)]
    res = _check_chapter_function_pacing(legacy)
    assert res["status"] == "pass"
    assert res["sampled"] == 0
