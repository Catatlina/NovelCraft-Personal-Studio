from app.v7.generation.generation_engine import GenerationEngine


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
