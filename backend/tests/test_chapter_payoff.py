from app.services.chapter_payoff import (
    build_payoff_contract,
    evaluate_payoff_schedule,
    normalize_payoff_contract,
    validate_payoff_contract,
    validate_payoff_evidence,
)
from app.services.quality_profiles import select_quality_profile


def _contract(chapter_number: int = 1) -> dict:
    return {
        "chapter_number": chapter_number,
        "reader_promise": "等主角在众人面前证明自己",
        "pressure": "公开测试失败会被逐出队伍",
        "active_choice": "主角主动要求再测一次",
        "payoff_type": "status_reversal",
        "visible_result": "石碑显示出新的数值",
        "witness_reaction": "嘲笑声停了",
        "cost": "能力暴露出冷却限制",
        "next_pressure": "长老要求第二天复核",
        "setup_refs": ["前三章的旧玉佩"],
    }


def test_payoff_contract_requires_choice_result_and_next_pressure():
    profile = select_quality_profile(genre="玄幻", subgenre="传统升级流")
    result = validate_payoff_contract(_contract(), profile=profile, required=True)

    assert result["passed"] is True
    assert result["missing"] == []

    incomplete = validate_payoff_contract(
        {"chapter_number": 1, "reader_promise": "有事发生"},
        profile=profile,
        required=True,
    )
    assert incomplete["passed"] is False
    assert "active_choice" in incomplete["missing"]


def test_payoff_evidence_must_be_locatable_in_actual_text():
    text = "石碑显示出新的数值。台下的嘲笑声停了。"
    good = validate_payoff_evidence(
        text,
        [{"type": "status_reversal", "anchor": "石碑显示出新的数值", "result": "数值发生变化"}],
        required=True,
    )
    bad = validate_payoff_evidence(
        text,
        [{"type": "status_reversal", "anchor": "主角击败了长老", "result": "赢了"}],
        required=True,
    )

    assert good["passed"] is True
    assert bad["passed"] is False

    partial = validate_payoff_evidence(
        text,
        [
            {"type": "status_reversal", "anchor": "石碑显示出新的数值", "result": "数值发生变化"},
            {"type": "status_reversal", "anchor": "主角击败了长老", "result": "赢了"},
        ],
        required=True,
    )
    assert partial["passed"] is True
    assert len(partial["invalid"]) == 1

    punctuation_only_difference = validate_payoff_evidence(
        "她说：“我宣布，从今天起，公司进入内部审计程序。所有支出重新核查。”",
        [{
            "type": "status_reversal",
            "anchor": "“我宣布，从今天起，公司进入内部审计程序。”",
            "result": "主角宣布审计",
        }],
        required=True,
    )
    assert punctuation_only_difference["passed"] is True
    assert punctuation_only_difference["checked"][0]["match_mode"] == "punctuation_normalized"


def test_provider_facing_chinese_payoff_labels_map_to_canonical_types():
    contract = normalize_payoff_contract({"chapter_number": 1, "payoff_type": "身份反转"})
    assert contract["payoff_type"] == "status_reversal"

    contract = normalize_payoff_contract({
        "chapter_number": 2,
        "payoff_type": "other",
        "active_choice": "主角选择当场解雇财务总监",
        "visible_result": "财务总监被保安带走，员工重新评估主角",
    })
    assert contract["payoff_type"] == "status_reversal"

    contract = normalize_payoff_contract({
        "chapter_number": 1,
        "payoff_type": "other",
        "reader_promise": "主角用年终奖买下公司，实现身份逆转",
        "visible_result": "主角成为公司最大股东，原CEO被解职",
    })
    assert contract["payoff_type"] == "status_reversal"

    contract = normalize_payoff_contract({
        "chapter_number": 3,
        "payoff_type": "other",
        "payoff_evidence": [{"type": "权力确立", "result": "对手被迫退场"}],
    })
    assert contract["payoff_type"] == "status_reversal"

    contract = normalize_payoff_contract({"chapter_number": 1, "type": "突破"})
    assert contract["payoff_type"] == "breakthrough"

    contract = normalize_payoff_contract({"chapter_number": 1, "kind": "资源获取"})
    assert contract["payoff_type"] == "resource_gain"

    contract = normalize_payoff_contract({
        "chapter_number": 1,
        "payoff_type": "other",
        "reader_promise": "完成身份反转",
        "visible_result": "主角成为公司新老板",
    })
    assert contract["payoff_type"] == "status_reversal"


def test_low_payoff_schedule_is_a_soft_reader_gate_not_a_word_count_gate():
    profile = select_quality_profile(platform="番茄", genre="都市", subgenre="都市神豪")
    chapters = [
        {"payoff_contract": build_payoff_contract(_contract(i), chapter_number=i, profile=profile)}
        for i in range(1, 4)
    ]
    chapters[1]["payoff_contract"]["visible_result"] = ""
    chapters[1]["payoff_contract"]["payoff_type"] = ""

    result = evaluate_payoff_schedule(chapters, profile=profile)
    assert result["passed"] is True
    assert result["max_low_payoff_streak"] == 2
