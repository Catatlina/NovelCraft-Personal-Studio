"""V3 §10 时间线真实锚点：确定性纯函数单元测试（不依赖 DB / AI）。"""
from app.services.timeline import (
    anchor_rule_for,
    check_anachronisms,
    is_reality_based,
    parse_year_anchor,
)


# ── is_reality_based ─────────────────────────────────────────────────────

def test_reality_based_enabled_by_dna_marker():
    dna = {"commercial_positioning": "起点·都市现实向职场文"}
    assert is_reality_based(dna) is True


def test_fantasy_book_not_reality_based():
    dna = {"commercial_positioning": "番茄·东方玄幻爽文"}
    assert is_reality_based(dna) is False


def test_non_dict_dna_degrades_to_disabled():
    assert is_reality_based(None) is False
    assert is_reality_based("现实向") is False


# ── parse_year_anchor ────────────────────────────────────────────────────

def test_parse_year_variants():
    assert parse_year_anchor("2010年") == 2010
    assert parse_year_anchor("1998年冬") == 1998
    assert parse_year_anchor("大约 2015 年前后") == 2015
    assert parse_year_anchor("第三纪元") is None
    assert parse_year_anchor(None) is None


# ── check_anachronisms ───────────────────────────────────────────────────

def test_anachronism_detected_before_product_era():
    res = check_anachronisms(2005, "他掏出手机扫了下微信付款码。")
    assert res["status"] == "warning"
    assert any("微信" in i for i in res["issues"])


def test_no_anachronism_after_product_era():
    res = check_anachronisms(2018, "他用微信叫了网约车，又刷了会抖音。")
    assert res["status"] == "pass"
    assert res["issues"] == []


def test_no_anchor_degrades_to_pass():
    assert check_anachronisms(None, "他掏出微信付款。")["status"] == "pass"
    assert check_anachronisms(2005, "")["status"] == "pass"


# ── anchor_rule_for ──────────────────────────────────────────────────────

def test_anchor_rule_generated_from_year():
    assert anchor_rule_for("2010年") == "不得出现2010年前不存在的产品/技术"
    assert anchor_rule_for("远古时代") == ""
    assert anchor_rule_for(None) == ""
