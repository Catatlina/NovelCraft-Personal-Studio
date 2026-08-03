"""Versioned, compact quality profiles for commercial Chinese web fiction.

The supplied writing packs are methodology sources, not runtime personas.  This
module converts their stable, reader-facing ideas into a small policy object:
platform expectations, genre/subgenre techniques, state ledgers and de-AI
checks.  It intentionally does not contain author names, quotations or copied
phrasing, and it keeps volatile platform claims out of hard gates.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


QUALITY_PROFILE_SCHEMA_VERSION = "webnovel-quality-profile-v1"

_PLATFORM_ALIASES = {
    "fanqie": "fanqie",
    "番茄": "fanqie",
    "番茄小说": "fanqie",
    "qidian": "qidian",
    "起点": "qidian",
    "起点中文网": "qidian",
}

_GENRE_ALIASES = {
    "都市": "urban",
    "现代": "urban",
    "都市小说": "urban",
    "urban": "urban",
    "玄幻": "xuanhuan",
    "东方玄幻": "xuanhuan",
    "仙侠": "xuanhuan",
    "修仙": "xuanhuan",
    "xuanhuan": "xuanhuan",
    "悬疑": "suspense",
    "灵异": "suspense",
    "科幻": "science_fiction",
    "历史": "history",
}

_SUBGENRE_ALIASES = {
    "神豪": "urban_shenhao",
    "都市神豪": "urban_shenhao",
    "商战": "urban_business",
    "都市商战": "urban_business",
    "重生": "urban_rebirth",
    "都市重生": "urban_rebirth",
    "年代": "urban_rebirth",
    "年代文": "urban_rebirth",
    "异能": "urban_ability",
    "都市异能": "urban_ability",
    "高武": "urban_high_martial",
    "都市高武": "urban_high_martial",
    "脑洞": "urban_brainstorm",
    "系统": "urban_system",
    "都市脑洞": "urban_brainstorm",
    "传统升级流": "xuanhuan_upgrade",
    "升级流": "xuanhuan_upgrade",
    "传统玄幻": "xuanhuan_upgrade",
    "凡人流": "xuanhuan_mortal",
    "苟道": "xuanhuan_mortal",
    "苟道流": "xuanhuan_mortal",
    "史诗": "xuanhuan_epic",
    "史诗玄幻": "xuanhuan_epic",
    "宿命": "xuanhuan_destiny",
    "宿命流": "xuanhuan_destiny",
    "设定流": "xuanhuan_setting",
    "智斗": "xuanhuan_setting",
    "家族": "xuanhuan_family",
    "家族修仙": "xuanhuan_family",
    "系统流": "xuanhuan_system",
    "签到": "xuanhuan_system",
}


_PLATFORM_PROFILES: dict[str, dict[str, Any]] = {
    "fanqie": {
        "label": "番茄式高留存基线",
        "title_rules": ["标题直给核心处境或反差", "优先口语化和可点击的冲突，不堆 SEO 关键词"],
        "synopsis_rules": ["用处境/冲突→能力或机会→下一步悬念的三段压缩结构", "移动端首屏先说人和事，不先科普世界"],
        "opening_rules": ["前 300 字出现具体冲突、异常或强问题", "前三章分别完成身份锚定、核心能力/规则展示和第一次可见反馈"],
        "chapter_rules": ["每章必须有可见状态变化和章末钩子", "前期不允许连续两章只有铺垫而没有情绪或信息兑现"],
        "payoff_policy": {"max_low_payoff_streak": 2, "early_chapters_need_payoff": 3, "hook_required": True},
        "attention_beat_rules": ["前 300 字进入具体主题；章内用情绪/信息/行动节点维持追读，不按固定字数硬塞爽点"],
        "reader_priority": "即时冲突、情绪反馈、清晰的下一步期待",
    },
    "qidian": {
        "label": "起点式连载基线",
        "title_rules": ["标题短而有辨识度，保留核心概念或人物状态", "避免短视频式感叹堆叠，形成全书统一标题风格"],
        "synopsis_rules": ["用具体人物困境承载世界格局和长期悬念", "少剧透结果，多给可验证的成长方向"],
        "opening_rules": ["前三章完成主角、核心设定、第一轮小高潮", "重要爽点先铺垫再兑现，结果必须有代价或余波"],
        "chapter_rules": ["每章推进目标、状态或关系，并留下可追读问题", "小冲突递进到阶段高潮，不用每章重复同一种打脸"],
        "payoff_policy": {"max_low_payoff_streak": 3, "early_chapters_need_payoff": 3, "hook_required": True},
        "attention_beat_rules": ["前三章完成主角、核心设定和第一轮小高潮；爽点要有铺垫、依据、代价和余波"],
        "reader_priority": "设定可信、成长有代价、伏笔与长期回报",
    },
}


_GENRE_PROFILES: dict[str, dict[str, Any]] = {
    "urban": {
        "label": "都市通用",
        "dialogue_mode": "对白推进目标和关系，叙述落到生活摩擦",
        "ledgers": ["时间线", "资金/债务", "人物关系", "职业或行业事实", "主角能力边界"],
        "payoff_types": ["status_reversal", "money_or_resource", "information_advantage", "relationship_shift", "career_progress"],
        "style_rules": ["用具体场景和行业动作替代空泛成功学", "重要配角有自己的目标、利益和反应", "主角必须主动做选择而不是只接收事件"],
        "anti_ai_rules": ["减少解释式总结和整齐排比", "保留自然口语、停顿和人物差异", "标点按语境使用，只限制整章异常密度"],
    },
    "xuanhuan": {
        "label": "玄幻仙侠通用",
        "dialogue_mode": "战斗、资源和关系选择共同推进，不用设定说明代替戏",
        "ledgers": ["境界与能力边界", "功法/法器/资源消耗", "伤势与恢复", "势力关系", "伏笔与因果", "时间地点"],
        "payoff_types": ["breakthrough", "combat_advantage", "resource_gain", "status_reversal", "reveal", "relationship_shift"],
        "style_rules": ["每次升级写清契机、代价、能力变化和验证", "越阶或逆转必须有设定内依据", "大世界通过事件和人物逐层显露，不整段科普"],
        "anti_ai_rules": ["减少万能境界、战斗过程和围观反应的重复模板", "爽点要有压制、选择、爆发、旁观反应和余波", "不因去 AI 味抹掉必要术语或专有名词"],
    },
}


_SUBGENRE_PROFILES: dict[str, dict[str, Any]] = {
    "urban_shenhao": {
        "label": "都市神豪/商战",
        "opening_rules": ["把现实需求、可用资金/机会和风险同时落到一个具体场景", "金手指必须有规则、冷却或代价"],
        "payoff_types": ["money_or_resource", "status_reversal", "opponent_reaction", "industry_breakthrough"],
        "ledgers": ["资金来源与余额", "项目现金流", "对手与合作方", "合同/风险", "时间节点"],
        "style_rules": ["钱的数字服务选择和节奏，不能只报资产规模", "对手要有资源和合理判断，主角的赢来自眼光、执行或信息差"],
    },
    "urban_business": {
        "label": "都市商战",
        "opening_rules": ["先给订单、裁员、债务、合同或行业规则造成的现实压力"],
        "payoff_types": ["industry_breakthrough", "information_advantage", "status_reversal", "relationship_shift"],
        "ledgers": ["现金流", "项目阶段", "合同责任", "竞争方动作", "行业事实"],
    },
    "urban_rebirth": {
        "label": "都市重生/年代",
        "opening_rules": ["先给具体年代处境和无法回避的选择，再露出信息差", "未来记忆必须有边界，并产生蝴蝶效应"],
        "payoff_types": ["information_advantage", "money_or_resource", "relationship_shift", "status_reversal"],
        "ledgers": ["年月日与年龄", "时代物件/制度", "资金与信息来源", "蝴蝶效应", "家庭关系"],
    },
    "urban_ability": {
        "label": "都市异能",
        "opening_rules": ["能力先在现实场景中解决一个小问题，同时展示限制或副作用"],
        "payoff_types": ["ability_discovery", "combat_advantage", "status_reversal", "reveal"],
        "ledgers": ["能力等级", "冷却/副作用", "普通人认知边界", "现代地点与时间"],
    },
    "urban_high_martial": {
        "label": "都市高武",
        "opening_rules": ["现代生活和异常力量必须同场出现，先让读者感到熟悉与危险的反差"],
        "payoff_types": ["combat_advantage", "ability_discovery", "status_reversal", "reveal"],
        "ledgers": ["现代社会规则", "战力阶梯", "能力代价", "阵营关系", "普通人信息边界"],
    },
    "urban_brainstorm": {
        "label": "都市脑洞",
        "opening_rules": ["用一个可理解的异常规则制造即时问题，不先解释规则全集"],
        "payoff_types": ["rule_exploit", "information_advantage", "status_reversal", "reveal"],
        "style_rules": ["规则每次出现都必须改变选择，不做规则展览"],
    },
    "urban_system": {
        "label": "都市系统",
        "opening_rules": ["系统奖励必须绑定任务、风险或消耗，不能凭空发福利"],
        "payoff_types": ["system_reward", "money_or_resource", "status_reversal", "ability_discovery"],
        "ledgers": ["任务与奖励", "系统限制", "资源余额", "现实后果"],
    },
    "xuanhuan_upgrade": {
        "label": "传统玄幻升级",
        "opening_rules": ["前三章给出明确压制、能力入口和第一次验证，不把升级写成一句状态播报"],
        "payoff_types": ["breakthrough", "combat_advantage", "status_reversal", "resource_gain"],
        "style_rules": ["境界梯度清晰，小境界快、大境界有仪式和代价", "敌人越强，胜利依据越具体"],
    },
    "xuanhuan_mortal": {
        "label": "凡人/苟道",
        "opening_rules": ["先处理生存、资源或信息风险，再暴露底牌", "苟不是停滞，至少要有资源、信息或关系的积累"],
        "payoff_types": ["resource_gain", "information_advantage", "survival", "hidden_strength", "breakthrough"],
        "ledgers": ["资源库存", "风险暴露", "底牌", "人情债", "伤势与恢复"],
    },
    "xuanhuan_epic": {
        "label": "史诗玄幻",
        "opening_rules": ["大谜团必须落在当前人物能感知的具体事件里", "每次扩张世界前先回收或推进一个近景问题"],
        "payoff_types": ["reveal", "status_reversal", "sacrifice", "breakthrough", "faction_shift"],
        "ledgers": ["时代/历史", "势力与战争", "伏笔状态", "关键人物命运", "力量上限"],
    },
    "xuanhuan_destiny": {
        "label": "宿命/仙侠",
        "opening_rules": ["情感执念必须在行动和代价里出现，不用抽象抒情替代选择"],
        "payoff_types": ["relationship_shift", "reveal", "sacrifice", "breakthrough", "reversal"],
        "style_rules": ["意境服务人物和冲突，不能让氛围描写把事件停住"],
    },
    "xuanhuan_setting": {
        "label": "设定/智斗",
        "opening_rules": ["先展示一条规则如何迫使角色选择，再逐步补充规则边界"],
        "payoff_types": ["rule_exploit", "reveal", "information_advantage", "status_reversal"],
        "ledgers": ["规则版本", "信息掌握者", "推理证据", "反转前置线索"],
    },
    "xuanhuan_family": {
        "label": "家族修仙",
        "opening_rules": ["先让家族面对资源/存续压力，人物关系和经营选择同时推进"],
        "payoff_types": ["resource_gain", "faction_shift", "relationship_shift", "breakthrough", "family_survival"],
        "ledgers": ["家族成员与代际", "资源与产业", "盟友/仇敌", "血脉/传承", "家族时间线"],
    },
    "xuanhuan_system": {
        "label": "系统/签到",
        "opening_rules": ["奖励频率服务剧情，系统不能替代主角做选择", "奖励必须带来新问题、消耗或暴露风险"],
        "payoff_types": ["system_reward", "breakthrough", "resource_gain", "status_reversal"],
        "ledgers": ["任务/签到", "奖励与限制", "资源余额", "能力验证", "暴露风险"],
    },
}


_SOURCE_PACKS = (
    "都市神豪写作质量包",
    "都市通用写作质量包",
    "玄幻仙侠写作质量包",
    "天蚕土豆写作质量包",
    "网文平台适配质量包",
    "urban-novel-writing-master",
    "xianxia-xuanhuan-writing-master",
    "novel-platform-style-master",
)


def normalize_platform(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return _PLATFORM_ALIASES.get(raw, "fanqie")


def normalize_genre(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in _GENRE_ALIASES:
        return _GENRE_ALIASES[raw]
    if any(token in raw for token in ("都市", "现代", "商战", "重生")):
        return "urban"
    if any(token in raw for token in ("玄幻", "仙侠", "修仙", "高武")):
        return "xuanhuan"
    return "urban" if not raw else raw


def normalize_subgenre(value: Any, genre: str = "") -> str:
    raw = str(value or "").strip().lower()
    if raw in _SUBGENRE_ALIASES:
        return _SUBGENRE_ALIASES[raw]
    for alias, key in _SUBGENRE_ALIASES.items():
        if alias in raw:
            return key
    return "xuanhuan_upgrade" if normalize_genre(genre) == "xuanhuan" else "urban"


def _unique(items: list[Any]) -> list[str]:
    result: list[str] = []
    for item in items:
        value = str(item or "").strip()
        if value and value not in result:
            result.append(value)
    return result


def select_quality_profile(
    *,
    platform: Any = "",
    genre: Any = "",
    subgenre: Any = "",
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic merged platform + genre + subgenre profile."""
    overrides = overrides if isinstance(overrides, dict) else {}
    platform_key = normalize_platform(overrides.get("platform") or platform)
    genre_key = normalize_genre(overrides.get("genre") or genre)
    subgenre_key = normalize_subgenre(overrides.get("subgenre") or subgenre, genre_key)
    platform_data = deepcopy(_PLATFORM_PROFILES.get(platform_key, _PLATFORM_PROFILES["fanqie"]))
    genre_data = deepcopy(_GENRE_PROFILES.get(genre_key, _GENRE_PROFILES["urban"]))
    subgenre_data = deepcopy(_SUBGENRE_PROFILES.get(subgenre_key, {}))

    merged: dict[str, Any] = {
        "schema_version": QUALITY_PROFILE_SCHEMA_VERSION,
        "profile_id": f"{platform_key}:{genre_key}:{subgenre_key}",
        "platform": platform_key,
        "genre": genre_key,
        "subgenre": subgenre_key,
        "label": f"{platform_data.get('label')} / {subgenre_data.get('label') or genre_data.get('label')}",
        "reader_priority": platform_data.get("reader_priority", ""),
        "title_rules": _unique(platform_data.get("title_rules", []) + subgenre_data.get("title_rules", [])),
        "synopsis_rules": _unique(platform_data.get("synopsis_rules", [])),
        "opening_rules": _unique(
            platform_data.get("opening_rules", [])
            + genre_data.get("opening_rules", [])
            + subgenre_data.get("opening_rules", [])
        ),
        "chapter_rules": _unique(platform_data.get("chapter_rules", [])),
        "style_rules": _unique(genre_data.get("style_rules", []) + subgenre_data.get("style_rules", [])),
        "anti_ai_rules": _unique(genre_data.get("anti_ai_rules", [])),
        "attention_beat_rules": _unique(
            platform_data.get("attention_beat_rules", [])
            + subgenre_data.get("attention_beat_rules", [])
        ),
        "dialogue_mode": subgenre_data.get("dialogue_mode") or genre_data.get("dialogue_mode", ""),
        "ledgers": _unique(genre_data.get("ledgers", []) + subgenre_data.get("ledgers", [])),
        "payoff_types": _unique(genre_data.get("payoff_types", []) + subgenre_data.get("payoff_types", [])),
        "payoff_policy": deepcopy(platform_data.get("payoff_policy", {})),
        "provenance": list(_SOURCE_PACKS),
    }
    # Project-level explicit settings are additive, never a replacement for
    # the built-in safety contract.
    for key in ("opening_rules", "chapter_rules", "style_rules", "anti_ai_rules", "ledgers", "payoff_types", "attention_beat_rules"):
        if isinstance(overrides.get(key), list):
            merged[key] = _unique(merged[key] + overrides[key])
    if isinstance(overrides.get("payoff_policy"), dict):
        merged["payoff_policy"].update({k: v for k, v in overrides["payoff_policy"].items() if k in {"max_low_payoff_streak", "early_chapters_need_payoff", "hook_required"}})
    merged["attention_beat_policy"] = {
        "soft": True,
        "description": "以读者注意力节点为软基线，不按固定字数硬切段或硬塞爽点",
        "max_low_payoff_streak": merged["payoff_policy"].get("max_low_payoff_streak", 2),
    }
    return merged


def profile_from_context(context: dict[str, Any] | None) -> dict[str, Any]:
    context = context if isinstance(context, dict) else {}
    raw = context.get("quality_profile")
    return select_quality_profile(
        platform=context.get("platform") or context.get("platform_key") or context.get("publish_platform"),
        genre=context.get("genre") or context.get("category") or context.get("main_category"),
        subgenre=context.get("subgenre") or context.get("sub_category") or context.get("theme"),
        overrides=raw if isinstance(raw, dict) else None,
    )


def compile_quality_directive(
    profile: dict[str, Any] | None,
    *,
    chapter_number: int | None = None,
    chapter_function: dict[str, Any] | None = None,
    payoff_contract: dict[str, Any] | None = None,
    active_rules: list[Any] | None = None,
) -> str:
    """Compile only the relevant rules into a bounded Writer directive."""
    profile = profile if isinstance(profile, dict) else select_quality_profile()
    seq = int(chapter_number or 1)
    lines = [
        f"质量策略 {profile.get('profile_id', QUALITY_PROFILE_SCHEMA_VERSION)}：以网络小说读者继续阅读为第一目标。",
        f"平台重点：{profile.get('reader_priority') or '冲突清楚、反馈具体、下一步明确'}。",
    ]
    package_rules = _unique(
        [*(profile.get("title_rules") or [])[:2], *(profile.get("synopsis_rules") or [])[:2]]
    )
    if package_rules:
        lines.append("书名/简介包装：" + "；".join(package_rules) + "。")
    if seq <= 3:
        lines.append("开篇阶段：本章必须尽快落到具体处境/冲突，完成可见反馈，并把下一章问题落到动作或发现。")
    for label, key, limit in (
        ("本章规则", "opening_rules", 3),
        ("章节节奏", "chapter_rules", 3),
        ("题材要求", "style_rules", 4),
        ("去 AI 味", "anti_ai_rules", 3),
    ):
        values = [str(item) for item in (profile.get(key) or [])[:limit] if str(item).strip()]
        if values:
            lines.append(f"{label}：" + "；".join(values) + "。")
    attention_rules = [str(item) for item in (profile.get("attention_beat_rules") or [])[:2] if str(item).strip()]
    if attention_rules:
        lines.append("读者注意力基线（软规则）：「" + "；".join(attention_rules) + "」。")
    learned_rules = [str(item).strip() for item in (active_rules or []) if str(item).strip()]
    if learned_rules:
        lines.append("来自已通过章节的学习规则（仅作定向提示，不覆盖事实和本章契约）：" + "；".join(learned_rules[:4]) + "。")
    ledgers = "、".join(str(item) for item in (profile.get("ledgers") or [])[:6])
    if ledgers:
        lines.append(f"状态账本：{ledgers}；任何新增事实、能力、资源和关系都要在正文中有来源、消耗或后果。")
    if isinstance(chapter_function, dict):
        goal = str(chapter_function.get("chapter_goal") or "").strip()
        expectation = str(chapter_function.get("reader_expectation") or "").strip()
        if goal or expectation:
            lines.append(f"本章功能：目标={goal or '推进主线'}；读者期待={expectation or '留下具体追读理由'}。")
    if isinstance(payoff_contract, dict):
        fields = (
            ("承诺", "reader_promise"),
            ("压力", "pressure"),
            ("主动选择", "active_choice"),
            ("可见结果", "visible_result"),
            ("代价/余波", "cost"),
            ("下一压力", "next_pressure"),
        )
        contract_text = "；".join(f"{label}={payoff_contract.get(key)}" for label, key in fields if payoff_contract.get(key))
        if contract_text:
            lines.append("本章爽点契约：" + contract_text + "。结果必须由角色行动造成，不能只在旁白里宣布。")
    lines.append("标点不设禁用清单；只处理整章高密度、连续重复或模板化使用，保留自然对白和人物习惯。")
    return "\n".join(lines)[:5000]


def quality_profile_metadata(profile: dict[str, Any] | None) -> dict[str, Any]:
    profile = profile if isinstance(profile, dict) else select_quality_profile()
    return {
        "schema_version": profile.get("schema_version", QUALITY_PROFILE_SCHEMA_VERSION),
        "profile_id": profile.get("profile_id"),
        "platform": profile.get("platform"),
        "genre": profile.get("genre"),
        "subgenre": profile.get("subgenre"),
        "payoff_policy": deepcopy(profile.get("payoff_policy") or {}),
        "ledgers": list(profile.get("ledgers") or []),
        "provenance": list(profile.get("provenance") or []),
    }
