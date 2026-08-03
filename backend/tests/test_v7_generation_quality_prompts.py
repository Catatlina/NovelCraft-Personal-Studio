import asyncio
from contextlib import asynccontextmanager

from app.v7.generation.generation_engine import AIGatewayError, DeAIPipeline, GenerationEngine


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

        async def generate(self, prompt, **_kwargs):
            self.calls.append(prompt)
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
    assert result["generation_quality"]["passed"] is False
    assert {item["code"] for item in result["generation_quality"]["failures"]} >= {
        "continuation_duplicate",
        "chapter_too_short",
    }
