from app.services.quality_profiles import (
    compile_quality_directive,
    quality_profile_metadata,
    select_quality_profile,
)
from app.services.planning_contract import (
    creative_bible_strategy_section_defects,
    mechanic_innovation_defects,
)
from app.v7.quality.market_snapshot import (
    MARKET_SNAPSHOT_SOURCE_ID,
    market_snapshot_metadata,
    resolve_market_benchmark,
)
from app.v7.quality.webnovel_strategy import (
    KNOWLEDGE_SOURCE_REGISTRY,
    knowledge_source_metadata,
    resolve_webnovel_strategy,
)
from app.services.planning_contract import mechanic_families_for_idea


def test_local_research_snapshot_is_versioned_and_soft_only():
    snapshot = market_snapshot_metadata()

    assert snapshot["source"]["id"] == MARKET_SNAPSHOT_SOURCE_ID
    assert snapshot["source"]["snapshot_date"] == "2026-08-05"
    assert snapshot["coverage"]["total_books"] == 967
    assert snapshot["coverage"]["with_text"] == 511
    assert snapshot["source"]["byte_size"] == 18860955
    assert snapshot["source"]["sha256"] == "321c432d444a7a344645c1f0966e6cea408155ce8886f73aecf8bdcea0db6b18"
    assert snapshot["coverage"]["golden_finger_matrix_filled_count"] == 74
    assert snapshot["coverage"]["hook_matrix_filled_count"] == 13
    assert "golden_finger_tagged" not in snapshot["coverage"]
    assert snapshot["hard_gate"] is False
    assert "关键词疑似命中" in "；".join(snapshot["limitations"])


def test_market_benchmark_selects_platform_genre_and_mechanic_evidence():
    benchmark = resolve_market_benchmark(
        platform="番茄",
        genre="都市",
        mechanic_families=["simulator", "system"],
        chapter_number=1,
    )

    assert benchmark["platform"]["label"] == "番茄小说"
    assert benchmark["genre"]["label"] == "都市"
    assert benchmark["platform"]["books"] == 314
    assert benchmark["opening"]["setup_max_chars"] == 300
    assert set(benchmark["mechanic_evidence"]) == {"simulator", "system"}
    assert benchmark["hard_gate"] is False
    assert benchmark["opening_hints"]


def test_extended_mechanic_catalog_gets_strategy_and_empirical_evidence():
    ideas = {
        "长生苟道": "longevity",
        "吞噬爆装": "predation",
        "御兽分身": "summon",
        "神兵器灵": "artifact",
        "万界直播": "livestream",
        "规则怪谈副本": "rule_game",
        "神医鉴宝": "profession_skill",
        "隐藏豪门兵王": "identity_relation",
        "扮猪吃虎无敌开局": "invincible_opening",
        "金手指有严重代价": "anti_trope",
    }
    for idea, family in ideas.items():
        assert family in mechanic_families_for_idea(idea)
        strategy = resolve_webnovel_strategy(mechanic_families=[family])
        assert any(item["family"] == family for item in strategy["mechanic"]["family_rules"])
        assert family in strategy["mechanic"]["market_evidence"]


def test_quality_strategy_carries_methodology_and_empirical_provenance():
    strategy = resolve_webnovel_strategy(
        platform="fanqie",
        genre="urban",
        mechanic_families=["simulator"],
    )
    ids = set(strategy["knowledge_sources"])

    assert MARKET_SNAPSHOT_SOURCE_ID in ids
    assert "golden_finger_distillation_v1_20260805" in ids
    assert strategy["market_benchmark"]["source"]["sha256"]
    assert strategy["mechanic"]["market_evidence"]["simulator"]["variants"]["life_simulation"] == 4
    assert strategy["mechanic"]["design_axes"]["costs"]


def test_compiled_directive_uses_snapshot_as_soft_generation_guidance():
    profile = select_quality_profile(
        platform="番茄",
        genre="都市",
        subgenre="都市脑洞",
        mechanic_families=["simulator"],
    )
    directive = compile_quality_directive(profile, chapter_number=1)
    metadata = quality_profile_metadata(profile)

    assert "平台/题材实证软基线" in directive
    assert "不是平台官方规则" in directive
    assert "金手指四轴候选" in directive
    assert metadata["quality_strategy"]["market_snapshot"]["source_id"] == MARKET_SNAPSHOT_SOURCE_ID
    assert metadata["knowledge_provenance"]["empirical_snapshot"]["hard_gate"] is False


def test_new_plan_requires_strategy_sections_and_innovation_contract():
    assert creative_bible_strategy_section_defects("爽点阶梯。反馈轮换。金手指创新路径。") == []
    assert creative_bible_strategy_section_defects("只有黄金三章。")

    assert mechanic_innovation_defects({"enabled": True})
    assert mechanic_innovation_defects({
        "enabled": True,
        "innovation_contract": {
            "path": "cost",
            "novelty_hook": "收益会生成长期债务",
            "risk": "债务会暴露身份",
        },
    }) == []


def test_source_registry_keeps_all_distilled_skills_and_research_source():
    ids = {item["id"] for item in KNOWLEDGE_SOURCE_REGISTRY}
    provenance = knowledge_source_metadata()

    assert len(ids) >= 18
    assert "payoff_closed_loop" in ids
    assert "deai_eight_methods" in ids
    assert "golden_finger_distillation_v1_20260805" in ids
    assert "quality_failure_reports_20260805" in ids
    assert "quality_six_stage_roadmap_20260805" in ids
    assert "simulator_future_branch_design_20260805" in ids
    assert MARKET_SNAPSHOT_SOURCE_ID in ids
    assert provenance["source_status"] == "methodology_candidate_plus_empirical_snapshot"
    by_id = {item["id"]: item for item in provenance["sources"]}
    assert by_id["quality_failure_reports_20260805"]["source"] == "user-provided-analysis"
    assert by_id[MARKET_SNAPSHOT_SOURCE_ID]["runtime_mode"] == "soft_evidence_only"
