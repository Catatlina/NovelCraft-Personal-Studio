from app.services.quality_profiles import (
    compile_quality_directive,
    profile_from_context,
    quality_profile_metadata,
    select_quality_profile,
)


def test_default_profile_is_one_fanqie_urban_runtime_policy():
    profile = profile_from_context({})

    assert profile["profile_id"] == "fanqie:urban:urban"
    assert profile["payoff_policy"]["hook_required"] is True
    assert "时间线" in profile["ledgers"]
    assert "platform" in quality_profile_metadata(profile)


def test_xuanhuan_mortal_profile_keeps_ledgers_and_non_combat_payoffs():
    profile = select_quality_profile(platform="起点", genre="玄幻", subgenre="凡人流")

    assert profile["profile_id"] == "qidian:xuanhuan:xuanhuan_mortal"
    assert "资源库存" in profile["ledgers"]
    assert "information_advantage" in profile["payoff_types"]
    assert "天蚕土豆写作质量包" in profile["provenance"]


def test_quality_directive_is_bounded_and_does_not_ban_single_punctuation():
    profile = select_quality_profile(platform="番茄", genre="玄幻", subgenre="传统升级流")
    directive = compile_quality_directive(
        profile,
        chapter_number=1,
        payoff_contract={
            "reader_promise": "等主角在公开测试中给出反差",
            "pressure": "众人认定主角无法修炼",
            "active_choice": "主角主动接受复测",
            "visible_result": "测试石显示新的数值",
            "cost": "暴露一条能力限制",
            "next_pressure": "长老要求明日再测",
        },
    )

    assert len(directive) <= 5000
    assert "爽点契约" in directive
    assert "标点不设禁用清单" in directive
    assert "禁止所有标点" not in directive


def test_longlife_style_plugin_is_explicit_and_scoped_to_matching_xuanhuan_subgenres():
    profile = select_quality_profile(
        platform="起点",
        genre="玄幻",
        subgenre="苟道流",
        style_plugin="系统赋我长生",
    )

    assert profile["style_plugin"] == "xuanhuan_longlife"
    assert profile["style_plugin_status"] == "enabled"
    assert "资源库存" in profile["ledgers"]
    assert any("重复" in item for item in profile["chapter_rules"])
    assert "系统赋我长生_写作模板" in profile["provenance"]

    directive = compile_quality_directive(profile, chapter_number=1)
    assert "可选风格插件（已启用）" in directive
    assert "不机械凑数" in directive
    assert "连续重复句式" in directive


def test_longlife_style_plugin_does_not_leak_into_urban_profiles():
    profile = select_quality_profile(
        genre="都市",
        subgenre="都市神豪",
        style_plugin="长生苟道",
    )

    assert profile["style_plugin"] == ""
    assert profile["style_plugin_status"] == "incompatible"
    assert profile["style_plugin_directive"] == []
    assert "寿元/时间尺度" not in profile["ledgers"]


def test_profile_context_carries_the_selected_plugin_into_runtime_metadata():
    profile = profile_from_context({
        "genre": "仙侠",
        "subgenre": "系统流",
        "style_plugin": "xuanhuan_longlife",
    })

    metadata = quality_profile_metadata(profile)
    assert metadata["style_plugin"] == "xuanhuan_longlife"
    assert metadata["style_plugin_status"] == "enabled"
