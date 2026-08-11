import asyncio
from contextlib import asynccontextmanager

import pytest

from app.prompt_registry import PROMPT_SEEDS, render_prompt
from app.services.quality_risks import build_quality_repair_contract
from app.v7.quality.deai_metrics import analyze_deai_patterns
from app.v7.generation.generation_engine import (
    AIGateway,
    AIGatewayError,
    DeAIPipeline,
    GenerationEngine,
    SceneDirector,
    ensure_unique_chapter_title,
    validate_tomato_chapter_title,
)
from app.v7.quality.opening_variation import (
    build_opening_history,
    inspect_opening,
    select_opening_plan,
)
from app.v7.quality.readability_contract import build_readability_plan, render_readability_plan


def test_repeated_chapter_title_gets_a_short_plot_hook():
    title = ensure_unique_chapter_title(
        "语音里的求救",
        previous_titles=["语音里的求救", "旧手机"],
        chapter_number=22,
        hints=["走廊尽头的钟声再次响起"],
    )

    assert title == "走廊尽头的钟声再次响起"
    assert title != "语音里的求救"

    compact = ensure_unique_chapter_title(
        "语音里的求救",
        previous_titles=["语音里的求救"],
        chapter_number=24,
        hints=["语音中传来一个陌生男人的声音"],
    )
    assert compact == "一个陌生男人"


def test_tomato_title_gate_rejects_summary_titles_and_accepts_reader_hooks():
    assert validate_tomato_chapter_title("江心岛迷雾·周衡在逃脱后，发现手机屏")[0] is False
    assert validate_tomato_chapter_title("密室现身")[0] is True


def test_opening_scheduler_is_global_and_does_not_default_to_body_sensation():
    first = select_opening_plan(1, previous_history=[])
    assert first["mode"] == "action"
    assert first["mode"] != "body_sensation"

    second = select_opening_plan(
        2,
        chapter_type="normal",
        previous_history=[{"chapter_number": 1, "mode": first["mode"]}],
    )
    assert second["mode"] != first["mode"]
    assert second["mode"] != "body_sensation"


def test_opening_history_prefers_persisted_observed_mode_over_legacy_classifier():
    history = build_opening_history([
        {
            "chapter_number": 11,
            "text": "门外传来警报，所有人同时回头。",
            "opening": {"observed_mode": "action"},
        }
    ])

    assert history[0]["mode"] == "action"


def test_explicit_repeated_opening_mode_is_replaced_by_safe_scheduler_choice():
    plan = select_opening_plan(
        12,
        previous_history=[
            {"chapter_number": 9, "mode": "action"},
            {"chapter_number": 10, "mode": "object"},
            {"chapter_number": 11, "mode": "dialogue"},
        ],
        plot_brief={"opening_mode": "action"},
    )

    assert plan["mode"] not in {"action", "object", "dialogue"}


def test_json_gateway_retries_truncated_output_with_compact_larger_budget():
    gateway = object.__new__(AIGateway)
    calls = []

    async def fake_generate(prompt, **kwargs):
        calls.append({"prompt": prompt, **kwargs})
        if len(calls) == 1:
            return {
                "text": '{"chapter_title":"截断',
                "tokens_input": 3,
                "tokens_output": 10,
                "cost": 0.01,
                "model": "test",
                "provider": "deepseek",
                "finish_reason": "length",
            }
        return {
            "text": '{"chapter_title":"完整计划"}',
            "tokens_input": 3,
            "tokens_output": 12,
            "cost": 0.01,
            "model": "test",
            "provider": "deepseek",
            "finish_reason": "stop",
        }

    gateway.generate = fake_generate
    result = asyncio.run(gateway.generate_json("输出计划", max_tokens=100))

    assert result["data"]["chapter_title"] == "完整计划"
    assert calls[1]["max_tokens"] == 150
    assert "完整 JSON" in calls[1]["prompt"]


def test_plain_gateway_never_returns_provider_truncated_prose(monkeypatch):
    from types import SimpleNamespace

    from app.v7.generation import generation_engine as generation_module

    gateway = object.__new__(AIGateway)
    gateway.provider = "deepseek"
    gateway.api_key = "configured-for-test"
    gateway.base_url = "https://example.invalid/v1"
    gateway.default_model = "deepseek-chat"
    gateway.timeout = 1
    gateway.max_retries = 2
    gateway.db = None
    gateway.novel_id = None
    gateway.project_id = None
    gateway.tracer = None
    gateway._route_resolved = False
    requested_limits = []

    class FakeGateway:
        def __init__(self, **_kwargs):
            pass

        async def complete_async(self, _prompt, **kwargs):
            requested_limits.append(kwargs["max_tokens"])
            if len(requested_limits) == 1:
                return SimpleNamespace(
                    content="正文在对白中途截断",
                    prompt_tokens=5,
                    completion_tokens=100,
                    finish_reason="length",
                )
            return SimpleNamespace(
                content="完整正文。",
                prompt_tokens=5,
                completion_tokens=20,
                finish_reason="stop",
            )

    monkeypatch.setattr(generation_module, "UnifiedAIGateway", FakeGateway)
    result = asyncio.run(gateway.generate("写一章正文", max_tokens=100))

    assert result["text"] == "完整正文。"
    assert requested_limits == [100, 700]


def test_provider_opening_repair_only_replaces_first_paragraph():
    class Gateway:
        async def generate_json(self, *_args, **_kwargs):
            return {
                "data": {"opening_text": "他抬手按住门把，门内立刻传来第二声敲击。"},
                "usage": {"tokens_input": 2, "tokens_output": 4, "cost": 0.01},
            }

    source = "警报声突然响起，所有人被迫转身。\n\n林越盯着门缝，没有松手。"
    result = asyncio.run(
        DeAIPipeline(Gateway()).repair_opening(
            source,
            chapter_number=12,
            opening_plan={"mode": "action", "forbidden_recent_modes": ["external_event"]},
        )
    )

    assert result["quality_gate"]["passed"] is True
    assert result["opening"]["observed_mode"] == "action"
    assert result["processed_text"].endswith("林越盯着门缝，没有松手。")


def test_opening_gate_rejects_the_repeated_body_sensation_template():
    text = "后脑勺的钝痛一浪一浪地顶上来，像有人攥着他的后脑勺往地上砸。"
    result = inspect_opening(
        text,
        requested_mode="action",
        chapter_number=1,
    )
    assert result["passed"] is False
    assert result["observed_mode"] == "body_sensation"
    assert {
        item["code"] for item in result["flags"]
    } >= {
        "opening_body_sensation_default",
        "opening_body_sensation_cliche",
        "opening_first_chapter_body_default",
    }


def test_readability_plan_is_deterministic_and_changes_delivery_texture():
    first = build_readability_plan(
        1,
        chapter_type="normal",
        plot_brief={
            "reader_promise": "看主角在公开场合反击",
            "emotional_target": "压迫 -> 爆发 -> 追杀",
            "hook": "对手拿出主角不该知道的证据",
        },
        opening_plan={"mode": "action", "label": "动作/选择开场"},
    )
    second = build_readability_plan(
        2,
        chapter_type="relationship",
        plot_brief={"reader_promise": "看两人的关系彻底撕开"},
        opening_plan={"mode": "dialogue", "label": "对白冲突开场"},
    )

    assert first["information_delivery"]["mode"] == "action_consequence"
    assert second["information_delivery"]["mode"] == "dialogue_subtext"
    rendered = render_readability_plan(first)
    assert "生成前可读性预案" in rendered
    assert "事件先发生" in rendered
    assert "避免把每个人的反应都写成整齐的震惊" in rendered


def test_opening_gate_blocks_recent_mode_reuse_but_allows_explicit_body_contract():
    repeated = inspect_opening(
        "他抬手按住门把，门内立刻传来第二声敲击。",
        requested_mode="action",
        chapter_number=4,
        recent_modes=["action", "dialogue", "action"],
    )
    assert repeated["passed"] is False
    assert any(item["code"] == "opening_mode_repetition" for item in repeated["flags"])

    explicit_body = inspect_opening(
        "胸口的刺痛逼得他弯下腰，血顺着衣襟滴到地上。",
        requested_mode="body_sensation",
        chapter_number=4,
    )
    assert explicit_body["passed"] is True


def test_legacy_prompt_templates_have_a_safe_global_opening_fallback():
    seeds = {name: template for name, _version, _model, template in PROMPT_SEEDS}
    for name in (
        "bootstrap.gen_chapter1",
        "narrative.gen_next_chapter",
        "bootstrap.write_chapter_draft",
    ):
        rendered = render_prompt(seeds[name], {})
        assert "$opening_contract" not in rendered
        assert "开场多样性硬约束" in rendered
        assert "身体部位+疼痛" in rendered


def test_opening_gate_is_a_blocking_quality_repair_category():
    contract = build_quality_repair_contract({
        "overall_score": 95,
        "dimensions": {"opening_quality": 95},
        "issues": [{
            "dimension": "opening_quality",
            "severity": "high",
            "description": "开场类型门禁未通过",
        }],
    })
    assert contract["passed"] is False
    assert "opening_quality" in contract["blocking_categories"]


def test_structural_ai_smell_triggers_semantic_rewrite_instead_of_remaining_advisory():
    text = "\n\n".join(
        [
            "沈夜看着门口的灯，缓缓地走向前方，心里明白事情不会如此简单。" * 2
            for _ in range(20)
        ]
    )
    metrics = analyze_deai_patterns(text, profile={"platform": "fanqie"})
    assert any(flag["code"] == "structural_ai_smell" for flag in metrics["flags"])
    assert "structural_ai_smell" in {
        flag["code"] for flag in metrics["flags"]
    }


def test_deterministic_opening_repair_preserves_paragraphs_and_reaches_target():
    paragraphs = [
        f"陆沉在第{i}次试剑时记住了一个细节，剑锋擦过石面，留下了一道新痕。"
        for i in range(18)
    ] + [
        "周长老站在廊下，没有打断这场练习。",
        "晨雾散开时，远处的钟声敲了三下。",
    ]
    source = "\n\n".join(paragraphs)

    repaired, evidence = DeAIPipeline._deterministic_paragraph_opening_repair(
        source,
        "陆沉",
    )

    assert evidence["applied"] is True
    assert evidence["replaced_count"] == 13
    assert evidence["after_ratio"] < 0.30
    assert len(repaired.split("\n\n")) == len(paragraphs)
    assert repaired.count("陆沉") < source.count("陆沉")


def test_deai_opening_provider_failure_keeps_fallback_but_blocks_quality_gate():
    paragraphs = [
        f"陆沉在第{i}次试剑时记住了一个细节，剑锋擦过石面，留下了一道新痕。"
        for i in range(18)
    ] + [
        "周长老站在廊下，没有打断这场练习。",
        "晨雾散开时，远处的钟声敲了三下。",
    ]
    source = "\n\n".join(paragraphs)

    class Gateway:
        def __init__(self):
            self.calls = 0

        async def generate_json(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return {
                    "data": {
                        "humanized_text": source,
                        "changes": ["保留正文事实"],
                        "ai_patterns_removed": [],
                    },
                    "usage": {"tokens_input": 1, "tokens_output": 1, "cost": 0.0},
                }
            raise AIGatewayError("opening repair provider returned empty output")

    result = asyncio.run(DeAIPipeline(Gateway()).process(source))

    assert result["quality_gate"]["passed"] is False
    assert result["quality_gate"]["mode"] == "deterministic_fallback"
    assert result["quality_gate"]["code"] == "opening_repair_provider_failed"
    assert result["quality_gate"]["after_ratio"] < 0.30
    assert any(
        layer["layer"] == "deterministic_paragraph_opening_repair"
        and layer["applied"] is True
        for layer in result["layers_applied"]
    )


def test_scene_plan_contract_rejects_empty_or_incomplete_provider_plan():
    with pytest.raises(AIGatewayError, match="beats must contain 4-6"):
        SceneDirector.validate_scene_plan_contract(
            {"chapter_title": "门后是什么", "chapter_type": "suspense", "beats": []},
            target_word_count=3000,
        )


def test_scene_plan_repairs_semantically_incomplete_provider_plan():
    class Gateway:
        def __init__(self):
            self.calls = 0

        async def generate_json(self, _prompt, **_kwargs):
            self.calls += 1
            usage = {"tokens_input": 10, "tokens_output": 5, "cost": 0.01, "model": "test"}
            phases = ["pressure", "build", "burst", "feedback", "aftershock"]
            if self.calls == 1:
                return {
                    "data": {
                        "chapter_title": "旧门",
                        "chapter_type": "normal",
                        "beats": [
                            {"name": f"beat-{i}", "content": "继续推进", "target_words": 600, "payoff_phase": phase}
                            for i, phase in enumerate(phases[:-1])
                        ],
                    },
                    "usage": usage,
                }
            return {
                "data": {
                    "chapter_title": "旧门后的答案",
                    "chapter_type": "normal",
                    "beats": [
                        {"name": f"beat-{i}", "content": "继续推进", "target_words": 600, "payoff_phase": phase}
                        for i, phase in enumerate(phases)
                    ],
                },
                "usage": usage,
            }

    gateway = Gateway()
    result = asyncio.run(SceneDirector(None, gateway).plan_scene(
        1,
        {"rendered_context": ""},
        target_word_count=3000,
        quality_profile={},
    ))

    assert gateway.calls == 2
    assert result["chapter_title"] == "旧门后的答案"
    assert result["_usage"]["tokens_output"] == 10


def test_scene_plan_projects_explicit_payoff_arc_without_inventing_content():
    class Gateway:
        def __init__(self):
            self.calls = 0

        async def generate_json(self, *_args, **_kwargs):
            self.calls += 1
            return {
                "data": {
                    "chapter_title": "余波来了",
                    "chapter_type": "normal",
                    "beats": [
                        {"name": "压境", "content": "敌人封住退路", "target_words": 750, "payoff_phase": "pressure"},
                        {"name": "试探", "content": "主角试探规则", "target_words": 750, "payoff_phase": "build"},
                        {"name": "反击", "content": "主角兑现选择", "target_words": 750, "payoff_phase": "burst"},
                        {"name": "反馈", "content": "对手被迫退让", "target_words": 750, "payoff_phase": "feedback"},
                    ],
                    "payoff_contract": {
                        "visible_result": "对手当场退让",
                        "payoff_feedback": "旁观者确认局势变化",
                        "cost": "主角暴露一张底牌",
                        "next_pressure": "新的追兵立即出现",
                        "payoff_arc": ["pressure", "build", "burst", "feedback", "aftershock"],
                    },
                },
                "usage": {"tokens_input": 10, "tokens_output": 5, "cost": 0.01, "model": "test"},
            }

    gateway = Gateway()
    result = asyncio.run(SceneDirector(None, gateway).plan_scene(
        1,
        {"rendered_context": ""},
        target_word_count=3000,
        quality_profile={},
    ))

    assert gateway.calls == 1
    assert result["beats"][3]["content"] == "对手被迫退让"
    assert result["beats"][3]["payoff_phases"] == ["feedback", "aftershock"]
    assert result["payoff_phase_projection"]["applied"] == [
        {"phase": "aftershock", "beat_index": 3}
    ]


def test_incomplete_plot_brief_falls_through_to_repair_capable_scene_planner():
    class Gateway:
        def __init__(self):
            self.calls = 0

        async def generate_json(self, _prompt, **_kwargs):
            self.calls += 1
            phases = ["pressure", "build", "burst", "feedback", "aftershock"]
            return {
                "data": {
                    "chapter_title": "补上的余波",
                    "chapter_type": "normal",
                    "beats": [
                        {"name": f"beat-{i}", "content": "继续推进", "target_words": 600, "payoff_phase": phase}
                        for i, phase in enumerate(phases)
                    ],
                },
                "usage": {"tokens_input": 10, "tokens_output": 5, "cost": 0.01, "model": "test"},
            }

    gateway = Gateway()
    incomplete_brief = {
        "chapter_title_hint": "旧门",
        "suggested_beats": [
            {"name": "压境", "content": "有人逼近", "target_words": 600, "payoff_phase": "pressure"},
            {"name": "试探", "content": "主角试探", "target_words": 600, "payoff_phase": "build"},
            {"name": "反击", "content": "主角反击", "target_words": 600, "payoff_phase": "burst"},
            {"name": "反馈", "content": "对手退让", "target_words": 600, "payoff_phase": "feedback"},
        ],
    }

    result = asyncio.run(SceneDirector(None, gateway).plan_scene(
        1,
        {"rendered_context": ""},
        target_word_count=3000,
        plot_brief=incomplete_brief,
        quality_profile={},
    ))

    assert gateway.calls == 1
    assert result["chapter_title"] == "补上的余波"


def test_generation_prompt_carries_reader_promise_and_cross_chapter_hooks():
    prompt = GenerationEngine._build_generation_prompt(
        None,
        12,
        {"rendered_context": "上一章尾部：门内又响了三下。"},
        {
            "chapter_title": "门后的声音",
            "scene_goal": "确认门后的人是谁",
            "conflict": "开门会暴露位置",
            "pacing": "medium",
            "reader_promise": "揭开门后异常的一层真相",
            "emotional_target": "警惕 -> 逼近 -> 惊疑",
            "opening_anchor": "手仍按在门缝上",
            "hook": "门后传来主角自己的声音",
            "beats": [],
        },
        "保持现实背景",
        3000,
    )

    assert "揭开门后异常的一层真相" in prompt
    assert "手仍按在门缝上" in prompt
    assert "每约 800-1200 字" in prompt
    assert "章末必须把钩子落实" in prompt
    assert "压制→蓄力→爆发→反馈→余波" in prompt
    assert "反馈必须落到对手、组织、资源、规则或旁观者的可见变化" in prompt


def test_generation_prompt_carries_readability_contract_before_writing():
    plan = build_readability_plan(
        12,
        chapter_type="normal",
        plot_brief={"reader_promise": "看主角当场翻盘"},
        opening_plan={"mode": "object", "label": "物件异常开场"},
    )
    prompt = GenerationEngine._build_generation_prompt(
        None,
        12,
        {"rendered_context": "", "context_layers": {"readability_plan": plan}},
        {
            "chapter_title": "门后是什么",
            "reader_promise": "看主角当场翻盘",
            "beats": [],
            "readability_plan": plan,
        },
        None,
        3000,
    )

    assert "【生成前可读性预案：先执行，再写正文】" in prompt
    assert "用动作和立刻发生的后果交付信息" in prompt
    assert "不是事后润色" not in prompt


def test_plot_brief_preserves_payoff_phase_labels_for_the_writer():
    plan = SceneDirector._adopt_plot_brief(
        1,
        3000,
        {
            "chapter_title_hint": "旧印初鸣",
            "suggested_beats": [
                {
                    "name": "压境",
                    "content": "敌人封住退路",
                    "target_words": 600,
                    "payoff_phase": "pressure",
                },
                {
                    "name": "试印",
                    "content": "主角试探旧印并承担代价",
                    "target_words": 600,
                    "payoff_phases": ["build"],
                },
                {
                    "name": "反击",
                    "content": "主角用已知规则反击",
                    "target_words": 600,
                    "payoff_phase": "burst",
                },
                {
                    "name": "余波",
                    "content": "对手退让，新的追兵出现",
                    "target_words": 600,
                    "payoff_phases": ["feedback", "aftershock"],
                },
            ],
        },
    )

    assert plan is not None
    assert plan["beats"][0]["payoff_phase"] == "pressure"
    assert plan["beats"][1]["payoff_phases"] == ["build"]
    assert plan["beats"][3]["payoff_phases"] == ["feedback", "aftershock"]


def test_continuation_prompt_does_not_reset_chapter_context():
    prompt = GenerationEngine._build_continuation_prompt(
        "门内又响了三下。",
        {"hook": "门后传来主角自己的声音", "beats": []},
        1200,
    )

    assert "不要重新开场" in prompt
    assert "时间线、地点、人物状态和情绪" in prompt


def test_deai_skips_provider_for_rule_clean_text():
    result = asyncio.run(DeAIPipeline(None).process("他推开门。屋里没人。"))

    assert result["semantic_humanize"] is False
    assert result["quality_gate"] == {"passed": True, "mode": "deterministic_only"}
    assert result["processed_text"] == "他推开门。屋里没人。"


def test_deai_blocks_duplicate_paragraphs_without_semantic_rewrite():
    paragraph = (
        "沈夜推开门，看见院里的灯还亮着，便停在门口没有进去。屋里没有人回应，"
        "只有桌上的茶还冒着热气，像是有人刚刚离开。"
    )
    result = asyncio.run(DeAIPipeline(None).process(f"{paragraph}\n\n{paragraph}"))

    assert result["quality_gate"]["passed"] is False
    assert result["quality_gate"]["code"] == "duplicate_paragraph"
    assert result["semantic_humanize"] is False


def test_deai_provider_invalid_json_becomes_auditable_quality_failure():
    text = "\n\n".join(
        ["顾沉低头看了一眼门缝，手指没有离开锁扣。" for _ in range(8)]
        + [
            "林岚把灯光压低，示意他先别出声。",
            "陈姨站在门外，迟迟没有敲门。",
            "赵启明收起文件，转身走向电梯。",
            "雨水沿着窗框往下淌，屋里没人说话。",
        ]
    )

    class BrokenGateway:
        async def generate_json(self, *_args, **_kwargs):
            raise AIGatewayError("invalid provider JSON")

    result = asyncio.run(DeAIPipeline(BrokenGateway()).process(text))

    assert result["processed_text"]
    assert result["semantic_humanize"] is False
    assert result["quality_gate"]["passed"] is False
    assert result["quality_gate"]["code"] == "rewrite_candidate_rejected"
    assert any(
        flag["code"] == "rewrite_candidate_rejected"
        for flag in result["metrics"]["after"]["flags"]
    )


def test_deai_low_risk_repeated_phrase_keeps_auditable_rule_only_path():
    text = "\n\n".join(
        [
            "风从窗缝里进来，吹动桌上的纸。",
            "风从窗缝里进来，带着一点潮气。",
            "风从窗缝里进来，灯影跟着晃了晃。",
            "林岚收起钥匙，没有立刻说话。",
            "陈姨站在门边，望着楼道尽头。",
            "赵启明把文件压在掌下，等着回答。",
            "雨水沿着玻璃往下淌，屋里没人出声。",
        ]
    )

    class GatewayThatMustNotBeCalled:
        def __init__(self):
            self.calls = 0

        async def generate_json(self, *_args, **_kwargs):
            self.calls += 1
            raise AssertionError("low-risk repeated phrase must not call Provider")

    gateway = GatewayThatMustNotBeCalled()
    result = asyncio.run(DeAIPipeline(gateway).process(text))

    assert result["processed_text"]
    assert result["semantic_humanize"] is False
    assert result["quality_gate"]["passed"] is True
    assert result["quality_gate"]["mode"] == "deterministic_only"
    assert result["metrics"]["semantic_trigger_flags"] == []
    assert result["metrics"]["after"]["flags"] == [
        {
            "code": "repeated_phrase",
            "severity": "low",
            "message": "存在跨句重复短语，需要确认是否为刻意回环",
        }
    ]
    assert gateway.calls == 0


def test_deai_forced_local_repair_calls_provider_without_detector_flag():
    text = "沈砚推开门，风从窗缝里进来，桌上的纸被吹得轻轻发响。" * 3

    class Gateway:
        def __init__(self):
            self.calls = 0

        async def generate_json(self, *_args, **_kwargs):
            self.calls += 1
            return {
                "data": {
                    "humanized_text": text,
                    "changes": ["保留原文事实并修复表达层门禁"],
                    "ai_patterns_removed": [],
                },
                "usage": {"tokens_input": 1, "tokens_output": 1, "cost": 0.0},
            }

    gateway = Gateway()
    result = asyncio.run(DeAIPipeline(gateway).process(
        text,
        force_semantic_rewrite=True,
    ))

    assert result["semantic_humanize"] is True
    assert result["metrics"]["semantic_trigger_flags"] == ["forced_local_repair"]
    assert gateway.calls == 1


def test_generation_discards_duplicate_continuation_and_marks_draft_unusable():
    paragraph_a = "沈夜把手按在门上，听见门内传来三下敲击，便停住了呼吸。" * 3
    paragraph_b = "林薇没有催他，只把短棍横在身前，目光落向院墙外的黑暗。" * 3
    first_text = f"{paragraph_a}\n\n{paragraph_b}"

    class Step:
        def set_output(self, *_args, **_kwargs):
            pass

    class Tracer:
        @asynccontextmanager
        async def trace_step(self, *_args, **_kwargs):
            yield Step()

    class ContextAssembler:
        async def assemble_context(self, *_args, **_kwargs):
            return {
                "rendered_context": "",
                "rendered_chars": 0,
                "truncated": False,
                "previous_chapters": 0,
                "context_layers": {},
            }

    class SceneDirector:
        async def plan_scene(self, *_args, **_kwargs):
            return {
                "chapter_title": "门后的声音",
                "hook": "门内再次敲响",
                "beats": [],
                "_usage": {},
            }

    class Gateway:
        def __init__(self):
            self.calls = []
            self.call_kwargs = []

        async def generate(self, prompt, **_kwargs):
            self.calls.append(prompt)
            self.call_kwargs.append(_kwargs)
            text = first_text if len(self.calls) == 1 else first_text
            return {
                "text": text,
                "tokens_input": 0,
                "tokens_output": 0,
                "cost": 0.0,
                "model": "test",
            }

    class Deai:
        async def process(self, text, **_kwargs):
            return {
                "processed_text": text,
                "layers_applied": [],
                "total_changes": 0,
                "semantic_humanize": False,
                "humanize_changes": [],
                "ai_patterns_removed": [],
                "metrics": {},
                "quality_gate": {"passed": True},
                "usage": {},
            }

    class EventBus:
        async def publish(self, *_args, **_kwargs):
            pass

    engine = GenerationEngine.__new__(GenerationEngine)
    engine.tracer = Tracer()
    engine.context_assembler = ContextAssembler()
    engine.scene_director = SceneDirector()
    engine.ai_gateway = Gateway()
    engine.deai_pipeline = Deai()
    engine.event_bus = EventBus()

    result = asyncio.run(engine.generate_chapter(1, target_word_count=600))

    assert result["text"] == first_text
    assert len(engine.ai_gateway.calls) == 2
    assert engine.ai_gateway.call_kwargs[0]["max_tokens"] <= 900
    assert result["generation_quality"]["passed"] is False
    assert {item["code"] for item in result["generation_quality"]["failures"]} >= {
        "continuation_duplicate",
        "chapter_too_short",
    }
