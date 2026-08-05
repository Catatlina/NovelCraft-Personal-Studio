import asyncio
from contextlib import asynccontextmanager

from app.v7.generation.generation_engine import (
    AIGatewayError,
    DeAIPipeline,
    GenerationEngine,
    ensure_unique_chapter_title,
)


def test_repeated_chapter_title_gets_an_existing_plot_event_suffix():
    title = ensure_unique_chapter_title(
        "语音里的求救",
        previous_titles=["语音里的求救", "旧手机"],
        chapter_number=22,
        hints=["走廊尽头的钟声再次响起"],
    )

    assert title == "语音里的求救·走廊尽头的钟声再次响起"
    assert title != "语音里的求救"

    compact = ensure_unique_chapter_title(
        "语音里的求救",
        previous_titles=["语音里的求救"],
        chapter_number=24,
        hints=["语音中传来一个陌生男人的声音"],
    )
    assert compact == "语音里的求救·一个陌生男人"


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
