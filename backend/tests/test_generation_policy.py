from app.services.content_policy import analyze_content_policy, content_generation_contract
from app.services.pov_quality import analyze_third_person_narrative, third_person_generation_contract
from app.services.quality_profiles import compile_quality_directive, select_quality_profile
from app.prompt_registry import PROMPT_SEEDS
from app.v7.engines.plot_engine import PlotEngine
from app.v7.integration.quality import evaluate_review


def test_first_person_is_allowed_only_inside_quoted_character_voice():
    text = (
        "周衡握住王建国的手，感觉到对方指腹上的硬茧。"
        "王建国笑了：‘小周，希望你能守住这家公司。’"
        "周衡掏出手机，给陈凯发消息。"
        "‘我会的。’"
    )

    report = analyze_third_person_narrative(text)

    assert report["passed"] is True
    assert report["first_person_count"] == 0
    assert report["excluded_quoted_chars"] > 0


def test_first_person_in_narrative_is_detected_before_deai_or_review():
    report = analyze_third_person_narrative(
        "握手时我感觉到他的硬茧。我掏出手机，盯着那条消息。"
    )

    assert report["passed"] is False
    assert report["first_person_count"] == 2
    assert "我" in report["first_person_tokens"]


def test_generation_directive_places_pov_and_urban_safety_before_writing():
    profile = select_quality_profile(genre="都市", subgenre="都市神豪")
    directive = compile_quality_directive(profile, chapter_number=1)

    assert directive.index("最高优先级：第三人称叙述硬约束") < directive.index("开篇阶段")
    assert "完全架空的现代社会" in directive
    assert "不得出现敏感、违法、色情、仇恨、极端或露骨暴力表达" in directive
    assert profile["narrative_pov"] == "third_person_narrative"
    assert "第三人称限知" in third_person_generation_contract()


def test_pre_generation_plot_prompt_inherits_the_same_contract():
    engine = PlotEngine.__new__(PlotEngine)
    engine.quality_profile = select_quality_profile(genre="都市", subgenre="都市神豪")

    prompt = engine._build_assess_prompt(
        chapter_number=1,
        outline="陆砚接手一只停摆的机械表，发现表内藏着即将发生的商业陷阱线索。",
        open_goals=[],
        overdue_goals=[],
        open_threads=[],
        perception={"state_total": 0, "pending_review": 0},
        previous_node=None,
    )

    assert "第三人称叙述硬约束" in prompt
    assert "完全架空的现代社会" in prompt
    assert "不得出现敏感、违法、色情、仇恨、极端或露骨暴力表达" in prompt


def test_legacy_editor_and_continuation_seeds_keep_the_generation_contract():
    seeds = {name: (version, template) for name, version, _model, template in PROMPT_SEEDS}

    for name in ("editor.continue", "editor.deai", "novel.continuation", "novel.polish"):
        version, template = seeds[name]
        assert version >= "3.1.0"
        assert "第三人称限知" in template
        assert "TMD 只能作为脱敏替代" in template


def test_urban_content_policy_rejects_known_real_entity_and_profanity_but_keeps_plant_grass():
    profile = select_quality_profile(genre="都市")

    blocked = analyze_content_policy("上海的公司骂了一句卧槽。", profile)
    allowed = analyze_content_policy("窗外是一片草地，TMD只是脱敏缩写。", profile)

    assert blocked["passed"] is False
    assert "上海" in blocked["real_world_entity_hits"]
    assert any(item["code"] == "profanity_or_insult" for item in blocked["failures"])
    assert allowed["passed"] is True


def test_quality_gate_rejects_pov_and_content_policy_even_with_high_scores():
    result = evaluate_review({
        "overall_score": 95,
        "dimension_scores": {
            "consistency": 95,
            "character_voice": 95,
            "plot_logic": 95,
            "pacing": 95,
            "writing_quality": 95,
            "constraint_compliance": 95,
        },
        "pov_metrics": {"passed": False, "first_person_count": 1},
        "content_policy": {
            "passed": False,
            "failures": [{"code": "profanity_or_insult", "message": "脏话"}],
        },
    })

    assert result["passed"] is False
    dimensions = {item["dimension"] for item in result["failures"]}
    assert "third_person_narrative" in dimensions
    assert "profanity_or_insult" in dimensions
