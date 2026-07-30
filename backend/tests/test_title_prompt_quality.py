"""书名生成 prompt 质量门禁（对齐番茄/起点真实爆款范式）。

防止书名 prompt 退化回「关键词堆砌 + 4-8字硬卡」的老土风格。
"""
import pytest

from app.prompt_registry import PROMPT_SEEDS


def _gen_titles_body() -> str:
    seed = next(s for s in PROMPT_SEEDS if s[0] == "bootstrap.gen_titles")
    assert seed[1] == "3.1.0", "gen_titles prompt 版本应已升级到 3.1.0（注入爆款范式）"
    return seed[3]


def test_title_prompt_uses_bestseller_paradigms():
    body = _gen_titles_body()
    # 必须引用真实爆款范式，而非泛泛的「商业感」
    assert "爆款书名范式" in body
    assert "我真没想重生啊" in body
    assert "1979黄金时代" in body
    # 必须禁止关键词平铺堆砌（用户吐槽的老土根因）
    assert "禁止把" in body and "平铺堆砌" in body
    # 字数约束放宽到 6-14，不再卡死 4-8
    assert "6-14 字" in body
    # 不得再出现旧版的「控制在 4-8 个字」
    assert "4-8 个字" not in body
    # 不得再出现旧版空泛的「商业感和时代感」
    assert "商业感和时代感" not in body


def test_title_prompt_renders_with_variables():
    from app.prompt_registry import render_prompt

    body = _gen_titles_body()
    out = render_prompt(body, {"genre": "都市", "style": "重生爽文", "idea": "重生2010创业"})
    assert "题材：都市" in out
    assert "风格：重生爽文" in out
    assert "核心创意：重生2010创业" in out
