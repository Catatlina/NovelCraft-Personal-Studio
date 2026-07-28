"""KI-007 regression: write_polish output-repair before schema validation.

deepseek-chat sometimes returns a structurally-loose but content-valid payload.
The repair layer must normalise it into the canonical contract instead of
hard-failing the whole run; genuinely empty / non-narrative output must still
raise OutputValidationError.
"""
from __future__ import annotations

import pytest

from app.gateway import OutputValidationError, validate_task_output


def test_canonical_polish_passes_untouched():
    out = validate_task_output(
        "write_polish",
        {"polished": {"title": "章名", "body": ["p1", "p2", "p3", "p4"]}, "changes_summary": "润色了开头"},
    )
    assert out["polished"]["body"] == ["p1", "p2", "p3", "p4"]
    assert out["changes_summary"] == "润色了开头"


def test_bare_body_list_is_wrapped():
    out = validate_task_output(
        "write_polish",
        {"body": ["a", "b", "c", "d"], "changes_summary": "ok"},
    )
    assert out["polished"]["body"] == ["a", "b", "c", "d"]


def test_string_body_is_split_into_paragraphs():
    out = validate_task_output(
        "write_polish",
        {"polished": {"title": "章名", "body": "第一段。\n第二段。\n第三段。\n第四段。"}},
    )
    assert isinstance(out["polished"]["body"], list)
    assert len(out["polished"]["body"]) >= 4


def test_single_block_string_body_sentence_chunked():
    long_text = "。".join(f"这是第{i}句话内容很长用来测试分句" for i in range(30)) + "。"
    out = validate_task_output("write_polish", {"polished": {"body": long_text}})
    assert isinstance(out["polished"]["body"], list)
    assert len(out["polished"]["body"]) >= 4


def test_missing_changes_summary_is_filled():
    out = validate_task_output(
        "write_polish",
        {"polished": {"title": "章名", "body": ["a", "b", "c", "d"]}},
    )
    assert out["changes_summary"] == ""


def test_changes_list_feeds_changes_summary():
    out = validate_task_output(
        "write_polish",
        {"polished": {"body": ["a", "b", "c", "d"]}, "changes": ["改了开头", "润色对话"]},
    )
    assert "改了开头" in out["changes_summary"]


def test_dict_items_in_body_list_are_cleaned():
    out = validate_task_output(
        "write_polish",
        {
            "polished": {
                "body": [
                    {"text": "a"},
                    {"text": "b"},
                    {"text": "c"},
                    {"text": "d"},
                ]
            },
            "changes_summary": "ok",
        },
    )
    assert out["polished"]["body"] == ["a", "b", "c", "d"]


def test_empty_polish_still_raises():
    with pytest.raises(OutputValidationError):
        validate_task_output("write_polish", {})
