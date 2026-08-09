from app.services.quality_profiles import compile_quality_directive, select_quality_profile
from app.v7.quality.deai_metrics import analyze_deai_patterns
from app.v7.quality.report_distillation import (
    REPORT_SOURCE_ID,
    analyze_report_metrics,
    select_report_pack,
)

def test_report_pack_selects_non_urban_genres_without_raw_samples():
    for genre, expected in (
        ("悬疑", "genre-suspense"),
        ("历史", "genre-history"),
        ("科幻", "genre-science-fiction"),
        ("游戏", "genre-game"),
        ("洪荒", "genre-fengshen"),
    ):
        pack = select_report_pack(platform="番茄", genre=genre)
        assert pack["pack_id"].startswith(expected)
        assert pack["source_id"] == REPORT_SOURCE_ID
        assert pack["hard_gate"] is False
        assert all("R段" not in item for item in pack["report_refs"])

def test_quality_profile_compiles_report_rules_and_ledgers():
    profile = select_quality_profile(platform="番茄", genre="悬疑")
    directive = compile_quality_directive(profile, chapter_number=1)
    assert profile["report_pack_id"].startswith("genre-suspense")
    assert "线索与埋点" in profile["ledgers"]
    assert "报告蒸馏规则" in directive
    assert "突然想到式推理" in directive
    assert profile["report_provenance"]["hard_gate"] is False

def test_report_metrics_are_soft_only_and_visible_in_deai_evidence():
    profile = select_quality_profile(platform="番茄", genre="都市", subgenre="系统")
    text = "脚步声停在门外。\n\n他握紧钥匙，听见锁芯里传来轻响。"
    report_metrics = analyze_report_metrics(text, profile)
    deai_metrics = analyze_deai_patterns(text, profile=profile)
    assert report_metrics["enabled"] is True
    assert report_metrics["soft_only"] is True
    assert deai_metrics["report_metrics"]["pack_id"] == profile["report_pack_id"]
    assert all(item["severity"] == "low" for item in report_metrics["warnings"])
