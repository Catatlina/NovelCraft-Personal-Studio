"""书名/标题/简介/去AI味 prompt 质量门禁（对齐真实爆款范式）。

防止相关 prompt 退化回「关键词堆砌 + 字数硬卡 + 空泛要求」的老土风格。
覆盖全量审计发现的三类同类问题：
- P0 标题三处（plan_idea / regenerate_titles / shortstory.gen_titles）对齐 gen_titles 爆款范式
- P1 去AI味（editor.deai 复用 deai.rewrite 方法论；deai.detect 干净则可不改）
- P2 简介/自媒体标题（gen_synopsis / social.* 补范式）
"""
import pytest

from app.prompt_registry import PROMPT_SEEDS

SEED_BY_NAME = {s[0]: s for s in PROMPT_SEEDS}


def _body(name, version):
    seed = SEED_BY_NAME[name]
    assert seed[1] == version, f"{name} prompt 版本应已升级到 {version}（注入爆款范式）"
    return seed[3]


# (name, version, 必须出现的范式标记, 不得出现的退化标记)
PROMPT_CONTRACTS = [
    ("bootstrap.gen_titles", "3.2.0",
     ["爆款书名范式", "我真没想重生啊", "1979黄金时代", "判零分",
      "重生2010：我的AI笔记本", "我的AI能预知未来", "重生之算法为王",
      "带着AI去2010", "不要直接出现这些词", "人物状态、情绪"],
     ["4-8 个字", "商业感和时代感"]),
    ("bootstrap.plan_idea", "1.2.0",
     ["我真没想重生啊", "1979黄金时代", "SEO 式书名",
      "重生2010：我的AI笔记本", "人物状态、情绪"],
     []),
    ("bootstrap.regenerate_titles", "1.2.0",
     ["我真没想重生啊", "1979黄金时代", "SEO 式书名",
      "重生2010：我的AI笔记本", "人物状态、情绪"],
     []),
    ("shortstory.gen_titles", "3.1.0",
     ["像真人在榜单", "平铺堆砌", "烂俗模板词", "4-12 字"],
     []),
    ("bootstrap.gen_synopsis", "3.1.0",
     ["我不是戏神", "反差/悬念", "空泛总结"],
     ["制造期待感和好奇心"]),
    ("editor.deai", "3.1.0",
     ["段落炸碎", "口语化", "人味注入", "只改「味」不改「事」"],
     []),
    ("deai.detect", "1.1.0",
     ["干净则可为空", "切勿为凑数"],
     ["changes至少3条"]),
    ("social.hm_title_variants", "1.1.0",
     ["真实爆款", "平铺堆砌", "真的会谢"],
     []),
    ("social.gen_hotspot_content", "3.1.0",
     ["钩子", "平铺堆砌", "无依据夸张词"],
     []),
]


@pytest.mark.parametrize("name,version,required,forbidden", PROMPT_CONTRACTS)
def test_prompt_keeps_bestseller_paradigm(name, version, required, forbidden):
    body = _body(name, version)
    for marker in required:
        assert marker in body, f"{name} 缺少范式标记：{marker}"
    for marker in forbidden:
        assert marker not in body, f"{name} 仍含退化标记：{marker}"


def test_title_prompt_renders_with_variables():
    from app.prompt_registry import render_prompt

    body = _body("bootstrap.gen_titles", "3.2.0")
    out = render_prompt(body, {"genre": "都市", "style": "重生爽文", "idea": "重生2010创业"})
    assert "题材：都市" in out
    assert "风格：重生爽文" in out
    assert "核心创意：重生2010创业" in out
    assert "重生2010：我的AI笔记本" in out  # 反例仍在 prompt 中作为警告
