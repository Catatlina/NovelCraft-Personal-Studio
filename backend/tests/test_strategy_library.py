"""Unit tests for V3 Strategy Library MVP (§6) — compile logic + graceful degrade.

Real logic only — no mock providers.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.prompt_compiler import (  # noqa: E402
    compile_generic_prompt,
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


# ═══ V3-P3-⑫: Prompt Compiler 通用引擎 ═══

def test_compile_generic_prompt_no_layers_returns_base():
    base = "base prompt"
    assert compile_generic_prompt(base) == base
    assert compile_generic_prompt(base, layers={}) == base


def test_compile_generic_prompt_with_layers_and_priorities():
    base = "write chapter"
    layers = {
        "策略指引": "本章要打脸",
        "创作红线": "不碰历史虚无主义",
        "风格要求": "网络小说口语化",
    }
    priorities = {"策略指引": 1, "风格要求": 2, "创作红线": 3}
    out = compile_generic_prompt(base, layers, priorities)
    # Priority 1 (策略指引) should appear before priority 3 (创作红线)
    pos_strat = out.find("【策略指引】")
    pos_style = out.find("【风格要求】")
    pos_redline = out.find("【创作红线】")
    assert pos_strat < pos_style < pos_redline, f"order mismatch: {pos_strat} < {pos_style} < {pos_redline}"
    assert "打脸" in out
    assert "网络小说" in out


def test_compile_generic_prompt_empty_text_skipped():
    base = "prompt"
    layers = {"A": "", "B": "content"}
    out = compile_generic_prompt(base, layers)
    assert "【A】" not in out
    assert "【B】" in out


def test_compile_generic_prompt_unspecified_priority_defaults_last():
    base = "x"
    layers = {"低": "L", "高": "H"}
    priorities = {"高": 1}
    out = compile_generic_prompt(base, layers, priorities)
    assert out.find("【高】") < out.find("【低】")


def test_compile_prompt_extra_layers():
    base = "write chapter"
    out = compile_prompt(
        base,
        strategy_directive="策略来了",
        extra_layers={"场景分镜": "场景1: 起势\n场景2: 高潮"},
    )
    assert "策略指引" in out
    assert "场景分镜" in out
    assert "场景1" in out


def test_bootstrap_writer_uses_prompt_compiler_on_the_product_path(monkeypatch):
    from app.workers import tasks

    class FakeDb:
        def execute(self, _sql):
            return self

        def fetchall(self):
            return STRATEGIES

        def close(self):
            pass

    monkeypatch.setattr(tasks, "connect", FakeDb)
    directive, hints = tasks._strategy_directive_for_chapter({
        "_chapter_seq": 2,
        "novel_dna": {"forbidden_deviations": ["禁止无理由暴富"]},
        "chapter_outlines": [{
            "seq": 2,
            "function_type": "冲突",
            "chapter_goal": "主角守住第一笔订单",
            "reader_expectation": "看到主角反制",
        }],
    })

    assert "【本章策略指引】" in directive
    assert "黄金三章" in directive and "打脸策略" in directive
    assert "【创作红线】" in directive and "禁止无理由暴富" in directive
    assert "【本章功能】" in directive and "主角守住第一笔订单" in directive
    assert any("冲突" in hint for hint in hints)
