"""Reader-facing synopsis must never silently fall back to the creative brief."""

from app.api.v1.ranking import _reader_synopsis


def test_missing_synopsis_is_empty_even_when_idea_exists():
    idea = "项目完整设定：主角、金手指、世界规则、爽点设计和前三章安排。"
    assert _reader_synopsis({"idea": idea}) == ""


def test_legacy_idea_shaped_synopsis_is_rejected_from_reader_surface():
    idea = "两界资源交换，主角要在现代与异界之间完成三次交易。"
    assert _reader_synopsis({"idea": idea, "synopsis": idea}) == ""
    assert _reader_synopsis({
        "idea": idea,
        "synopsis": "项目完整设定：" + "主角在异界获得能力，金手指有严格边界，爽点设计围绕交易升级展开。" * 8,
    }) == ""


def test_valid_synopsis_is_preserved_separately():
    synopsis = "沈砚接手一间快要倒闭的修理铺，却从一只送来的旧表里发现父亲失踪前留下的线索。每修好一件旧物，他就离真相更近一步，也更接近那场会毁掉整座城市的交易。"
    assert _reader_synopsis({"idea": "旧城修理铺悬疑", "synopsis": synopsis}) == synopsis
