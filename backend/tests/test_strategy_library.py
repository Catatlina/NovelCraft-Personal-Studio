"""Unit tests for V3 Strategy Library MVP (§6) — compile logic + graceful degrade.

Real logic only — no mock providers.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.prompt_compiler import (  # noqa: E402
    select_strategies,
    compile_strategy_directive,
    compile_prompt,
    SKILL_GENERATE_CONFLICT,
    SKILL_GENERATE_HOOK,
)


STRATEGIES = [
    {"name": "黄金三章", "category": "开篇", "stages": ["立人设", "抛悬念", "给甜头", "埋长线"], "description": "前3章立人设"},
    {"name": "打脸策略", "category": "爽点", "stages": ["压制", "误解", "隐藏实力", "事件触发", "能力展示"], "description": "先压后扬"},
    {"name": "身份反转", "category": "爽点", "stages": ["铺垫平凡", "误会轻视", "真相引爆"], "description": "反转"},
]


def test_select_golden_three_for_early_chapters():
    sel = select_strategies(STRATEGIES, 2, "")
    names = [s["name"] for s in sel]
    assert "黄金三章" in names
    assert "打脸策略" not in names  # no matching function_type


def test_select_face_slap_for_conflict_function():
    sel = select_strategies(STRATEGIES, 10, "冲突")
    names = [s["name"] for s in sel]
    assert "打脸策略" in names
    assert "黄金三章" not in names  # seq 10 out of range


def test_select_identity_reversal():
    sel = select_strategies(STRATEGIES, 15, "身份反转")
    names = [s["name"] for s in sel]
    assert "身份反转" in names


def test_select_none_when_no_match():
    sel = select_strategies(STRATEGIES, 50, "日常")
    assert sel == []


def test_compile_strategy_directive_formats_stages():
    sel = select_strategies(STRATEGIES, 5, "爽点")
    directive = compile_strategy_directive(sel)
    assert "打脸策略" in directive
    assert "压制 → 误解" in directive


def test_compile_strategy_directive_empty_when_none():
    assert compile_strategy_directive([]) == ""


def test_compile_prompt_degrades_when_no_strategy():
    base = "请写第一章。"
    out = compile_prompt(base)  # nothing added
    assert out == base


def test_compile_prompt_appends_directive_and_dna_and_function():
    base = "请写第一章。"
    sel = select_strategies(STRATEGIES, 2, "")
    directive = compile_strategy_directive(sel)
    out = compile_prompt(
        base,
        strategy_directive=directive,
        novel_dna={"forbidden_deviations": ["禁止圣母"]},
        chapter_function={"chapter_goal": "立人设", "reader_expectation": "期待打脸"},
    )
    assert "策略指引" in out
    assert "创作红线" in out and "禁止圣母" in out
    assert "本章功能" in out and "立人设" in out
    assert out.startswith(base)


def test_skill_constants_exist():
    assert SKILL_GENERATE_CONFLICT == "generate_conflict"
    assert SKILL_GENERATE_HOOK == "generate_hook"
