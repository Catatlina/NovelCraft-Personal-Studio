from app.services.chapter_payoff import (
    build_payoff_contract,
    validate_payoff_contract,
    validate_payoff_variety,
    score_payoff_contract,
)
from app.services.quality_profiles import compile_quality_directive, select_quality_profile
from app.v7.quality.failure_patterns import (
    FAILURE_PATTERN_SCHEMA_VERSION,
    failure_pattern_metadata,
    get_failure_pattern,
    list_failure_patterns,
)
from app.v7.quality.payoff_strategy import choose_payoff_type, select_payoff_strategy
from app.v7.quality.audit_dimensions import AUDIT_DIMENSIONS
from app.v7.quality.review_evidence import validate_review_evidence
from app.v7.quality.rule_learning import QualityPatternLearningStore


def test_failure_catalog_keeps_report_evidence_and_confidence_auditable():
    patterns = list_failure_patterns()
    assert len(patterns) == 12
    assert all(item["schema_version"] == FAILURE_PATTERN_SCHEMA_VERSION for item in patterns)
    assert get_failure_pattern("F01")["severity"] == "P0"
    metadata = failure_pattern_metadata(pattern_ids=["F01", "F05"])
    assert metadata["count"] == 2
    assert all(item["sources"] for item in metadata["patterns"])


def test_profile_selects_strategy_by_platform_and_subgenre():
    fanqie = select_quality_profile(platform="番茄", genre="都市", subgenre="都市神豪")
    mortal = select_quality_profile(platform="起点", genre="玄幻", subgenre="凡人流")
    longlife = select_quality_profile(platform="起点", genre="玄幻", subgenre="长生流")
    cautious = select_quality_profile(platform="起点", genre="玄幻", subgenre="苟道流")

    assert fanqie["payoff_strategy"]["strategy_id"] == "urban_shenhao"
    assert mortal["payoff_strategy"]["strategy_id"] == "xuanhuan_mortal"
    assert longlife["payoff_strategy"]["strategy_id"] == "xuanhuan_longlife"
    assert cautious["payoff_strategy"]["strategy_id"] == "xuanhuan_cautious"
    assert fanqie["failure_pattern_constraints"]


def test_payoff_type_rotation_avoids_recent_types_when_alternatives_exist():
    strategy = select_payoff_strategy("fanqie", "urban", "urban_shenhao")
    selected = choose_payoff_type(
        strategy,
        chapter_number=4,
        allowed_types=["money_or_resource", "status_reversal", "industry_breakthrough"],
        recent_types=["money_or_resource", "status_reversal", "money_or_resource"],
    )
    assert selected == "industry_breakthrough"


def test_missing_payoff_type_uses_strategy_rotation_and_metadata():
    profile = select_quality_profile(platform="番茄", genre="都市", subgenre="都市神豪")
    contract = build_payoff_contract(
        {
            "chapter_number": 4,
            "reader_promise": "主角要拿下这笔订单",
            "pressure": "竞争对手已经锁定客户",
            "active_choice": "主角主动改变谈判条件",
            "visible_result": "客户改签主角的方案",
            "payoff_feedback": "竞争对手失去先手",
            "next_pressure": "对方开始追查资金来源",
        },
        chapter_number=4,
        profile=profile,
        recent_types=["money_or_resource", "status_reversal"],
    )
    assert contract["payoff_type"] == "industry_breakthrough"
    assert contract["payoff_type_source"] == "strategy_rotation"
    assert validate_payoff_contract(contract, profile=profile, required=True)["passed"] is True


def test_explicit_repeated_payoff_type_is_repaired_before_generation():
    profile = select_quality_profile(platform="番茄", genre="都市", subgenre="都市神豪")
    contract = build_payoff_contract(
        {
            "chapter_number": 8,
            "reader_promise": "主角拿回主动权",
            "pressure": "对手已经完成封锁",
            "active_choice": "主角主动切断旧渠道并启动备用方案",
            "payoff_type": "status_reversal",
            "visible_result": "对手的封锁出现缺口",
            "payoff_feedback": "客户转而支持主角",
            "next_pressure": "对手开始追查备用方案来源",
        },
        chapter_number=8,
        profile=profile,
        recent_types=["status_reversal", "status_reversal", "status_reversal"],
    )
    assert contract["payoff_type"] != "status_reversal"
    assert contract["payoff_type_source"] == "strategy_rotation_repair"
    assert contract["payoff_type_repaired_from"] == "status_reversal"
    assert validate_payoff_variety(
        contract["payoff_type"],
        ["status_reversal", "status_reversal", "status_reversal"],
        profile=profile,
    )["passed"] is True


def test_directive_exposes_strategy_and_report_failures_without_punctuation_ban():
    profile = select_quality_profile(platform="番茄", genre="玄幻", subgenre="传统升级流")
    directive = compile_quality_directive(profile, chapter_number=2)
    assert "爽点策略" in directive
    assert "历史报告失败模式" in directive
    assert "F01" in directive
    assert "标点不设禁用清单" in directive


def test_aftermath_chapter_can_兑现_previous_consequence_without_fake_active_choice():
    profile = select_quality_profile(platform="起点", genre="玄幻", subgenre="长生流")
    contract = build_payoff_contract(
        {
            "chapter_number": 6,
            "chapter_type": "aftermath",
            "reader_promise": "兑现上一章留下的身份风险",
            "pressure": "新的身份已经引起宗门注意",
            "visible_result": "主角被迫换掉公开身份",
            "payoff_feedback": "宗门名单出现新的追查记录",
            "next_pressure": "新的身份无法继续使用原有资源",
        },
        chapter_number=6,
        profile=profile,
        chapter_function={"chapter_type": "aftermath"},
    )
    result = validate_payoff_contract(
        contract,
        profile=profile,
        required=True,
        chapter_function={"chapter_type": "aftermath"},
    )
    assert result["active_choice_required"] is False
    assert result["passed"] is True


def test_payoff_variety_only_blocks_a_full_rotation_window():
    profile = select_quality_profile(platform="番茄", genre="都市", subgenre="都市神豪")
    warning = validate_payoff_variety(
        "status_reversal",
        ["status_reversal"],
        profile=profile,
    )
    blocked = validate_payoff_variety(
        "status_reversal",
        ["status_reversal", "status_reversal", "status_reversal"],
        profile=profile,
    )
    assert warning["passed"] is True
    assert warning["repeated"] is True
    assert blocked["passed"] is False


def test_payoff_score_is_explainable_and_does_not_claim_to_be_llm_quality():
    profile = select_quality_profile(platform="番茄", genre="都市", subgenre="都市神豪")
    contract = build_payoff_contract(
        {
            "chapter_number": 1,
            "reader_promise": "主角拿下订单",
            "pressure": "对手已经锁定客户",
            "active_choice": "主角主动改变报价",
            "payoff_type": "industry_breakthrough",
            "visible_result": "客户签下主角的方案",
            "payoff_feedback": "对手失去先手",
            "next_pressure": "对方开始追查资金来源",
            "payoff_intensity": "medium",
        },
        chapter_number=1,
        profile=profile,
    )
    scored = score_payoff_contract(
        contract,
        profile=profile,
        text="主角主动改变报价，客户签下主角的方案。对手失去先手。对方开始追查资金来源。",
    )
    assert scored["source"] == "deterministic_contract"
    assert scored["score"] >= 80
    assert scored["dimensions"]["protagonist_agency"] == 100
    assert set(scored["dimensions"]) == {
        "expectation_fulfillment",
        "protagonist_agency",
        "result_visibility",
        "feedback_effectiveness",
        "payoff_intensity",
        "hook_strength",
        "payoff_variety",
        "five_chapter_curve",
        "twenty_chapter_distribution",
    }
    assert scored["evidence"]["twenty_chapter_distribution"]["ready"] is False


def test_payoff_score_evaluates_five_and_twenty_chapter_history():
    profile = select_quality_profile(platform="番茄", genre="都市", subgenre="都市神豪")
    history = [
        {
            "chapter_number": index,
            "payoff_type": "money_or_resource" if index % 2 else "status_reversal",
            "payoff_intensity": "medium" if index % 3 else "high",
        }
        for index in range(1, 20)
    ]
    contract = build_payoff_contract(
        {
            "chapter_number": 20,
            "reader_promise": "主角拿回项目主动权",
            "pressure": "对手已经完成封锁",
            "active_choice": "主角主动切断旧渠道并启动备用方案",
            "payoff_type": "information_advantage",
            "visible_result": "备用方案拿到关键证据",
            "payoff_feedback": "对手的封锁出现缺口",
            "next_pressure": "对手准备反向追查",
            "payoff_intensity": "high",
        },
        chapter_number=20,
        profile=profile,
    )
    scored = score_payoff_contract(
        contract,
        profile=profile,
        text="主角主动切断旧渠道并启动备用方案，备用方案拿到关键证据。对手的封锁出现缺口。",
        recent_types=[item["payoff_type"] for item in history[-8:]],
        recent_history=history,
    )
    assert scored["evidence"]["five_chapter_curve"]["ready"] is True
    assert scored["evidence"]["twenty_chapter_distribution"]["ready"] is True
    assert scored["dimensions"]["twenty_chapter_distribution"] >= 60


def _review_evidence_fixture() -> dict:
    return {
        "canonical_engine": "v7",
        "dimension_scores": {
            "consistency": 90,
            "character_voice": 90,
            "pacing": 90,
            "plot_logic": 90,
            "writing_quality": 90,
            "emotional_impact": 90,
            "constraint_compliance": 90,
        },
        "reader_experience": {
            "expectation": 90,
            "conflict": 90,
            "payoff": 90,
            "emotion_shift": 90,
            "worth_continuing": 90,
        },
        "audit_report": {
            "schema_version": "33d-v1",
            "count": len(AUDIT_DIMENSIONS),
            "complete": True,
            "source": "llm",
            "coverage": 1.0,
            "items": {
                item.key: {
                    "key": item.key,
                    "score": 90,
                    "evidence": f"{item.label} 的原文证据",
                    "repair": "无需修复",
                    "source": "llm",
                }
                for item in AUDIT_DIMENSIONS
            },
        },
        "provenance": {
            "engine": "v7",
            "audit_source": "v7.review.33_dimension",
            "prompt_name": "v7.review.33_dimension",
            "prompt_version": "1.1.0",
            "model": "test-model",
            "text_hash": "abc123",
            "scored_at": "2026-08-05T00:00:00+00:00",
        },
    }


def test_review_evidence_rejects_compatibility_projection():
    review = _review_evidence_fixture()
    review["audit_report"] = {
        "schema_version": "33d-v1",
        "count": len(AUDIT_DIMENSIONS),
        "complete": False,
        "source": "macro_projection",
        "coverage": 0.0,
        "items": {
            item.key: {
                "key": item.key,
                "score": 90,
                "evidence": "兼容投影，不是逐项原文证据",
                "source": "macro_projection",
            }
            for item in AUDIT_DIMENSIONS
        },
    }
    result = validate_review_evidence(review)
    assert result["passed"] is False
    assert "audit_33" in result["missing"]


def test_review_evidence_requires_final_continuity_only_at_product_boundary():
    review = _review_evidence_fixture()
    review_time = validate_review_evidence(review, require_continuity=False)
    assert review_time["passed"] is True

    final_time = validate_review_evidence(review, require_continuity=True)
    assert final_time["passed"] is False
    assert "continuity" in final_time["missing"]

    review["continuity"] = {
        "status": "continuous",
        "checked": True,
        "narrative_flow": "上一章的门后异常在本章开头得到动作承接。",
        "deterministic_contract": {"passed": True},
    }
    final_time = validate_review_evidence(review, require_continuity=True)
    assert final_time["passed"] is True
    assert final_time["timeline"]["complete"] is True
    assert final_time["character_arcs"]["complete"] is True


def test_quality_learning_promotes_only_repeated_positive_samples():
    class FakeState:
        def __init__(self):
            self.values = {}

        async def get_state(self, _state_type, key):
            value = self.values.get(key)
            return {"value": value} if value is not None else None

        async def update_state(self, _state_type, key, value, *_args, **_kwargs):
            self.values[key] = value
            return {"action": "created" if key not in self.values else "updated"}

        async def list_states(self, _state_type, limit=20):
            return [{"key": key, "value": value} for key, value in list(self.values.items())[:limit]]

    store = QualityPatternLearningStore(FakeState())
    import asyncio

    for chapter in range(1, 4):
        result = asyncio.run(store.observe_sample(
            chapter_number=chapter,
            accepted=True,
            payoff_type="status_reversal",
            payoff_score=88,
            review_score=90,
            reader_payoff=84,
            continuity_passed=True,
        ))
        assert result[0]["status"] in {"candidate", "canary"}
    recommendations = asyncio.run(store.active_recommendations(chapter_number=4))
    assert recommendations and recommendations[0]["status"] == "canary"

    for chapter in range(4, 6):
        asyncio.run(store.observe_sample(
            chapter_number=chapter,
            accepted=True,
            payoff_type="status_reversal",
            payoff_score=88,
            review_score=90,
            reader_payoff=84,
            continuity_passed=True,
        ))
    recommendations = asyncio.run(store.active_recommendations(chapter_number=6))
    assert recommendations[0]["status"] == "active"
    assert recommendations[0]["sample_count"] == 5
