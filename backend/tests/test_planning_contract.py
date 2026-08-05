from app.services.planning_contract import (
    validate_longform_contract,
    validate_simulator_contract,
    validate_volume_plan_contract,
)


def _longform_contract(target: int = 1_500_000) -> dict:
    return {
        "target_words": target,
        "volume_count": 2,
        "volume_word_targets": [750_000, 750_000],
        "chapter_word_target": 3000,
        "chapter_count": 500,
        "route_milestones": [
            {"label": "前期", "start_words": 0, "end_words": 750_000, "goal": "建立冲突"},
            {"label": "后期", "start_words": 750_000, "end_words": target, "goal": "完成主线"},
        ],
    }


def _bible(target: int = 1_500_000) -> str:
    return (
        f"核心设定。黄金三章。能力边界与代价。长篇路线：阶段一 0-75万字，阶段二 75-150万字。"
        f"篇幅与内容配比：目标总字数：{target}字。人物关系。持续校验清单。"
        + "具体执行规则。" * 500
    )


def test_longform_contract_rejects_route_beyond_target():
    output = {
        "creative_bible": _bible(),
        "longform_contract": {
            **_longform_contract(),
            "route_milestones": [
                {"label": "前期", "start_words": 0, "end_words": 1_500_000, "goal": "建立冲突"},
                {"label": "错误路线", "start_words": 1_500_000, "end_words": 6_000_000, "goal": "越界"},
            ],
        },
    }
    defects = validate_longform_contract(output, idea="玄幻长篇", target_words=1_500_000)
    assert any("不能超过" in item or "超过项目目标" in item for item in defects)


def test_simulator_contract_requires_terminal_future_and_harvest_choice():
    defects = validate_simulator_contract(
        {
            "enabled": True,
            "horizon": "模拟未来三天",
            "terminal_condition": "看到一次危险",
            "branches": ["一条"],
            "observable_state": ["状态"],
            "harvestable_rewards": ["金币"],
            "selection_rules": ["选择"],
            "costs_and_risks": "消耗一次机会",
            "reality_writeback": "写回现实",
        },
        required=True,
    )
    assert any("死亡或终局" in item for item in defects)
    assert any("机缘、修为、功法" in item for item in defects)


def test_complete_longform_contract_is_accepted():
    output = {
        "creative_bible": _bible(),
        "longform_contract": _longform_contract(),
        "simulator_contract": {"enabled": False},
    }
    assert validate_longform_contract(
        output,
        idea="玄幻长篇",
        target_words=1_500_000,
    ) == []


def test_volume_plan_requires_exact_word_ledger_and_contiguous_chapters():
    output = {
        "total_word_target": 1_500_000,
        "volumes": [
            {"start_chapter": 1, "end_chapter": 100, "word_target": 700_000},
            {"start_chapter": 102, "end_chapter": 200, "word_target": 700_000},
        ],
    }
    defects = validate_volume_plan_contract(output, target_words=1_500_000)
    assert any("合计" in item for item in defects)
    assert any("连续" in item for item in defects)


def test_volume_plan_requires_declared_total_word_target():
    defects = validate_volume_plan_contract(
        {
            "volumes": [
                {"start_chapter": 1, "end_chapter": 100, "word_target": 1_500_000},
            ],
        },
        target_words=1_500_000,
    )
    assert any("total_word_target" in item for item in defects)
