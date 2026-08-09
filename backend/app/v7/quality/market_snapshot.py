"""Compact empirical evidence distilled from the local web-novel research site.

The source HTML is a research artifact, not a production dependency.  This
module stores only the auditable aggregates and opening heuristics that are
safe to compile into prompts.  It deliberately does not copy book prose,
author voice, or individual title formulas.

The numbers are treated as a dated, non-official snapshot.  Callers must use
the returned opening rules as soft baselines and must preserve the limitations
when showing the evidence in a plan or audit.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


MARKET_SNAPSHOT_SCHEMA_VERSION = "novel-research-snapshot-v1"
MARKET_SNAPSHOT_SOURCE_ID = "novel_research_site_20260805"


_SOURCE = {
    "id": MARKET_SNAPSHOT_SOURCE_ID,
    "label": "网文全平台套路研究库",
    "source_type": "local_static_html",
    "source_locator": "Workbuddy/2026-08-05-18-53-29/novel-research/site/index.html",
    "snapshot_date": "2026-08-05",
    "byte_size": 18860955,
    "sha256": "321c432d444a7a344645c1f0966e6cea408155ce8886f73aecf8bdcea0db6b18",
    "official_platform_document": False,
    "sample_scope": "公开分类页与排行榜头部作品，不是全站普查",
    "limitations": [
        "排行榜反映抓取时的热度，不等于历史最佳，也不等于新书更容易成功",
        "金手指与开篇钩子主要是关键词疑似命中，重要判断仍需人工确认原文",
        "正文样本主要来自免费开篇，不能代表付费章节和中后期维护质量",
        "空白矩阵可能是样本偏差，不等于市场不存在该类型",
        "平台规则数字来自二手行业资料，不是官方硬规则",
    ],
}


_PLATFORM_STATS = {
    # The source exposes platform totals but not a reliable per-platform
    # breakdown for intro/catalog/text coverage. Keep only fields present in
    # the snapshot instead of inventing precision.
    "fanqie": {"label": "番茄小说", "books": 314},
    "qidian": {"label": "起点中文网", "books": 195},
    "qimao": {"label": "七猫小说", "books": 191},
    "zongheng": {"label": "纵横中文网", "books": 192},
    "17k": {"label": "17K小说网", "books": 75},
}

_GENRE_STATS = {
    "urban": {"label": "都市", "books": 156, "with_text": 78},
    "xuanhuan": {"label": "玄幻", "books": 71, "with_text": 31},
    "xianxia": {"label": "仙侠", "books": 38, "with_text": 14},
    "suspense": {"label": "悬疑", "books": 85, "with_text": 51},
    "history": {"label": "历史", "books": 75, "with_text": 28},
    "science_fiction": {"label": "科幻", "books": 69, "with_text": 29},
    "game": {"label": "游戏", "books": 41, "with_text": 19},
    "wuxia": {"label": "武侠", "books": 49, "with_text": 5},
    "military": {"label": "军事", "books": 33, "with_text": 4},
}


# These are deliberately soft targets.  They are used to shape the first
# three chapter prompt, never to reject a chapter solely for missing a number.
_PLATFORM_OPENING_SPECS = {
    "fanqie": {
        "label": "番茄小说",
        "model": "免费/算法留存",
        "first_chapter_chars": [1500, 2000],
        "setup_max_chars": 300,
        "conflict_by_chars": 500,
        "mechanic_reveal_by_chars": 1000,
        "soft_rules": ["前段尽快进入具体处境或冲突", "第一章给出可见反馈和下一步问题"],
    },
    "qidian": {
        "label": "起点中文网",
        "model": "付费/订阅成长",
        "first_chapter_chars": [2000, 3000],
        "setup_max_chars": 1000,
        "conflict_by_chars": None,
        "mechanic_reveal_by_chapter": 3,
        "soft_rules": ["前三章完成主角、核心设定和第一轮小高潮", "铺垫必须服务后续兑现"],
    },
    "qimao": {
        "label": "七猫小说",
        "model": "免费/算法与保底",
        "first_chapter_chars": [1000, 1500],
        "setup_max_chars": 200,
        "conflict_by_chars": 500,
        "mechanic_reveal_by_chars": 800,
        "soft_rules": ["前 500 字内出现可感知冲突", "移动端首屏先说人和事"],
    },
    "zongheng": {
        "label": "纵横中文网",
        "model": "付费/精品",
        "first_chapter_chars": [2000, 3000],
        "setup_max_chars": 800,
        "conflict_by_chars": None,
        "mechanic_reveal_by_chapter": 3,
        "soft_rules": ["第一章内出现核心冲突", "保留世界观完整度和长期成长空间"],
    },
    "17k": {
        "label": "17K小说网",
        "model": "付费/老牌",
        "first_chapter_chars": [1500, 2500],
        "setup_max_chars": 500,
        "conflict_by_chars": None,
        "mechanic_reveal_by_chapter": 3,
        "soft_rules": ["第一章内出现成长性和具体冲突", "标题与简介要先让读者知道主角处境"],
    },
}


# The matrix is evidence for design selection, not a popularity leaderboard.
# Counts are suspected subtype-hit counts from the snapshot; one book can hit
# multiple subtypes, so they are not a unique-book denominator.
_MECHANIC_EVIDENCE = {
    "system": {
        "parent": "GF01 系统流",
        "parent_sample_count": 72,
        "variants": {
            "task": 31,
            "draw": 22,
            "sign_in": 15,
            "shop": 2,
            "achievement": 1,
            "management": 1,
            "penalty": 0,
        },
    },
    "simulator": {
        "parent": "GF02 模拟器流",
        "parent_sample_count": 7,
        "variants": {"life_simulation": 4, "battle_or_sandbox": 2, "clone_or_dongtian": 1},
    },
    "rebirth": {
        "parent": "GF04 信息差流",
        "parent_sample_count": 618,
        "variants": {"rebirth_memory": 161, "plot_or_book": 63, "future_prediction": 33, "mind_reading": 17, "live_comments": 16, "transmigration": 328},
    },
    "space": {
        "parent": "GF07 空间流",
        "parent_sample_count": 56,
        "variants": {"portable_space": 4, "spirit_field_or_spring": 9, "secret_realm": 18, "base_or_fortress": 25},
    },
    "panel": {
        "parent": "GF06 属性/词条流",
        "parent_sample_count": 39,
        "variants": {"attribute_points": 20, "equipment_or_affix": 12, "talent_tree": 1, "stacking_buff": 6},
    },
    "inheritance": {
        "parent": "GF09/GF10 传承与血脉体质流",
        "parent_sample_count": 98,
        "variants": {"ring_or_spirit": 10, "ancient_inheritance": 7, "supreme_manual": 4, "master": 1, "special_body": 10, "pseudo_waste_reversal": 55, "innate_power_or_eyes": 8},
    },
    "time_loop": {
        "parent": "GF03 时间流",
        "parent_sample_count": 27,
        "variants": {"rewind": 10, "loop": 0, "acceleration": 3, "stop_or_slow": 6, "longevity": 4},
    },
    "longevity": {
        "parent": "GF03 时间/长生流",
        "parent_sample_count": 4,
        "variants": {"longevity": 4},
    },
    "ability": {
        "parent": "GF16 职业/技能流 + GF05 掠夺/吞噬流",
        "parent_sample_count": 261,
        "variants": {"medical": 79, "appraisal_or_clairvoyance": 19, "food": 31, "fengshui": 30, "technology": 31, "entertainment": 42, "swallowing": 40, "copy": 17, "sacrifice_or_trade": 63},
    },
    "commerce": {
        "parent": "GF13 交易/中介流",
        "parent_sample_count": 43,
        "variants": {"mysterious_shop": 18, "cross_world_trade": 6, "wish_or_contract": 19},
    },
    "predation": {
        "parent": "GF05 掠夺/吞噬流",
        "parent_sample_count": 155,
        "variants": {"swallowing": 40, "kill_or_drop": 23, "steal_fate_or_talent": 12, "copy": 17, "sacrifice_or_trade": 63},
    },
    "summon": {
        "parent": "GF08 召唤/分身流",
        "parent_sample_count": 38,
        "variants": {"hero_or_name": 1, "beast": 5, "corpse_or_undead": 8, "clone": 24},
    },
    "artifact": {
        "parent": "GF12 器物/法宝流",
        "parent_sample_count": 27,
        "variants": {"weapon": 8, "furnace": 7, "ancient_book": 5, "mirror_door_or_tower": 7},
    },
    "livestream": {
        "parent": "GF14 直播/曝光流",
        "parent_sample_count": 69,
        "variants": {"multiverse_live": 31, "modern_live": 21, "sky_or_video": 17},
    },
    "rule_game": {
        "parent": "GF15 规则/无限/诡异流",
        "parent_sample_count": 132,
        "variants": {"rule_survival": 15, "infinite_dungeon": 34, "uncanny_contamination": 83},
    },
    "profession_skill": {
        "parent": "GF16 职业/技能流",
        "parent_sample_count": 232,
        "variants": {"medical": 79, "appraisal_or_clairvoyance": 19, "food": 31, "fengshui": 30, "technology_or_industry": 31, "copycat_or_entertainment": 42},
    },
    "identity_relation": {
        "parent": "GF17 身份/关系反差流",
        "parent_sample_count": 341,
        "variants": {"hidden_rich": 108, "soldier": 103, "father_in_law": 38, "daughter_or_dad": 92},
    },
    "invincible_opening": {
        "parent": "GF11 无敌开局/扮猪吃虎流",
        "parent_sample_count": 85,
        "variants": {"peak_opening": 3, "pretend_pig_eat_tiger": 46, "sign_in_idle_years": 16, "family_or_apprentice_slap": 20},
    },
    "anti_trope": {
        "parent": "GF18 反套路/弱金手指流",
        "parent_sample_count": 86,
        "variants": {"no_cheat": 41, "bad_cheat": 11, "serious_cost": 34},
    },
}


_HOOK_EVIDENCE = {
    "desperation": 28,
    "humiliation_or_broken_engagement": 57,
    "system_arrival": 84,
    "transmigration_wakeup": 267,
    "rebirth": 112,
    "identity_reveal": 22,
    "uncanny_event": 177,
    "in_media_res": 109,
    "daily_contrast_break": 280,
    "inheritance_or_last_words": 47,
    "invincible_declaration": 4,
    "rule_or_mission": 14,
    "family_or_protection": 252,
    "delayed_mechanic": 0,
}


_DESIGN_AXES = {
    "acquisition": ["born_with", "transmigration_or_rebirth", "accident", "near_death", "inheritance", "trade", "drop", "gift"],
    "payoff_conversion": ["numeric_overmatch", "information_asymmetry", "resource_monopoly", "efficiency_gap", "identity_contrast", "rule_exemption", "emotional_compensation"],
    "growth_curve": ["linear", "step_change", "weak_then_explode", "peak_then_strip", "reset_loop", "snowball"],
    "costs": ["cooldown", "resource_spend", "lifespan_or_essence", "strict_trigger", "backlash", "limited_uses", "detection_or_exposure"],
}


_RULES = {
    "three_chapters": [
        "第一章先给具体问题、主角和章末钩子",
        "第二章用行动/台词立人设，明确目标并引入新障碍",
        "第三章亮出金手指或核心规则，并把压力升级到可选择的分叉",
    ],
    "five_traps": [
        "开篇大段讲世界观",
        "主角出场太晚",
        "金手指拖到读者没有盼头",
        "主角只受压不出现反击苗头",
        "章末没有可追读问题",
    ],
}


_PLATFORM_ALIASES = {
    "番茄": "fanqie", "番茄小说": "fanqie", "fanqie": "fanqie",
    "起点": "qidian", "起点中文网": "qidian", "qidian": "qidian",
    "七猫": "qimao", "七猫小说": "qimao", "qimao": "qimao",
    "纵横": "zongheng", "纵横中文网": "zongheng", "zongheng": "zongheng",
    "17k": "17k", "17K": "17k", "17k小说网": "17k",
}


def _platform_key(value: Any) -> str:
    raw = str(value or "fanqie").strip()
    return _PLATFORM_ALIASES.get(raw, raw.lower()) if raw else "fanqie"


def _genre_key(value: Any) -> str:
    raw = str(value or "urban").strip().lower()
    aliases = {
        "都市": "urban", "现代": "urban", "urban": "urban",
        "玄幻": "xuanhuan", "东方玄幻": "xuanhuan", "仙侠": "xianxia", "修仙": "xianxia", "xuanhuan": "xuanhuan",
        "悬疑": "suspense", "灵异": "suspense", "suspense": "suspense",
        "历史": "history", "history": "history", "科幻": "science_fiction", "science_fiction": "science_fiction",
        "游戏": "game", "武侠": "wuxia", "军事": "military",
    }
    return aliases.get(raw, raw)


def resolve_market_benchmark(
    *,
    platform: str = "fanqie",
    genre: str = "urban",
    mechanic_families: list[str] | None = None,
    chapter_number: int | None = None,
) -> dict[str, Any]:
    """Return the small evidence bundle appropriate for one generation.

    ``chapter_number`` only controls which opening hints are surfaced.  The
    benchmark remains advisory even for chapter one; fixed word gates belong
    in provider-independent audits, not in this research adapter.
    """
    platform_key = _platform_key(platform)
    genre_key = _genre_key(genre)
    platform_data = deepcopy(_PLATFORM_STATS.get(platform_key, _PLATFORM_STATS["fanqie"]))
    opening = deepcopy(_PLATFORM_OPENING_SPECS.get(platform_key, _PLATFORM_OPENING_SPECS["fanqie"]))
    genre_data = deepcopy(_GENRE_STATS.get(genre_key, {}))
    families = [str(item).strip() for item in mechanic_families or [] if str(item).strip()]
    family_evidence = {
        family: deepcopy(_MECHANIC_EVIDENCE[family])
        for family in families
        if family in _MECHANIC_EVIDENCE
    }
    chapter = int(chapter_number or 1)
    opening_hints = list(_RULES["three_chapters"] if chapter <= 3 else [])
    return {
        "schema_version": MARKET_SNAPSHOT_SCHEMA_VERSION,
        "source": deepcopy(_SOURCE),
        "platform": {"key": platform_key, **platform_data},
        "genre": {"key": genre_key, **genre_data} if genre_data else {"key": genre_key},
        "opening": opening,
        "opening_hints": opening_hints,
        "mechanic_evidence": family_evidence,
        "hook_evidence": deepcopy(_HOOK_EVIDENCE),
        "design_axes": deepcopy(_DESIGN_AXES),
        "design_rule": "从获取方式、爽点变现、成长曲线、代价四个轴各选一项；至少明确一项真实代价，避免只换名词不改变选择面。",
        "rules": deepcopy(_RULES),
        "chapter_number": chapter,
        "hard_gate": False,
        "limitations": list(_SOURCE["limitations"]),
    }


def market_snapshot_metadata() -> dict[str, Any]:
    """Return provenance and coverage without exposing the raw HTML."""
    return {
        "schema_version": MARKET_SNAPSHOT_SCHEMA_VERSION,
        "source": deepcopy(_SOURCE),
        "coverage": {
            "total_books": 967,
            "platforms": {key: deepcopy(value) for key, value in _PLATFORM_STATS.items()},
            "genres": {key: deepcopy(value) for key, value in _GENRE_STATS.items()},
            "with_intro": 773,
            "with_catalog": 649,
            "with_text": 511,
            "golden_finger_matrix_filled_count": 74,
            "golden_finger_matrix_filled": "74/77",
            "hook_matrix_filled_count": 13,
            "hook_matrix_filled": "13/14",
        },
        "opening_specs": deepcopy(_PLATFORM_OPENING_SPECS),
        "mechanic_evidence": deepcopy(_MECHANIC_EVIDENCE),
        "hook_evidence": deepcopy(_HOOK_EVIDENCE),
        "design_axes": deepcopy(_DESIGN_AXES),
        "rules": deepcopy(_RULES),
        "hard_gate": False,
        "limitations": list(_SOURCE["limitations"]),
    }


def market_benchmark_directive(benchmark: dict[str, Any] | None) -> str:
    """Render a bounded, anti-copy evidence note for prompts."""
    if not isinstance(benchmark, dict):
        return ""
    source = benchmark.get("source") or {}
    platform = benchmark.get("platform") or {}
    genre = benchmark.get("genre") or {}
    opening = benchmark.get("opening") or {}
    hints = benchmark.get("opening_hints") or []
    parts = [
        f"来源={source.get('label', '本地研究库')} {source.get('snapshot_date', '')}",
        f"平台样本={platform.get('label', '')}{platform.get('books', '未知')}本",
    ]
    if genre.get("books"):
        parts.append(f"题材样本={genre.get('label', '')}{genre.get('books')}本，正文样本{genre.get('with_text', 0)}本")
    if opening.get("first_chapter_chars"):
        lo, hi = opening["first_chapter_chars"]
        parts.append(f"首章长度软参考{lo}-{hi}字")
    if opening.get("setup_max_chars") is not None:
        parts.append(f"铺垫软参考不超过约{opening['setup_max_chars']}字")
    if opening.get("conflict_by_chars") is not None:
        parts.append(f"冲突软参考约在前{opening['conflict_by_chars']}字内")
    if opening.get("mechanic_reveal_by_chars") is not None:
        parts.append(f"金手指/核心规则软参考约在前{opening['mechanic_reveal_by_chars']}字内")
    if opening.get("mechanic_reveal_by_chapter") is not None:
        parts.append(f"金手指/核心规则软参考在第{opening['mechanic_reveal_by_chapter']}章前")
    if hints:
        parts.append("前三章方法=" + "；".join(str(item) for item in hints[:3]))
    if benchmark.get("design_rule"):
        parts.append(f"金手指四轴候选={benchmark['design_rule']}")
    evidence = benchmark.get("mechanic_evidence") or {}
    for family, item in list(evidence.items())[:2]:
        variants = item.get("variants") if isinstance(item, dict) else {}
        if isinstance(variants, dict) and variants:
            top = sorted(variants.items(), key=lambda pair: int(pair[1] or 0), reverse=True)[:3]
            parts.append(
                f"{family}样本变体="
                + ",".join(f"{name}:{count}" for name, count in top)
                + "（仅作观察，不按热度照抄）"
            )
    parts.append("仅作软基线，不是平台官方规则；不得复制样本句式、书名或作者风格")
    return "；".join(parts)
