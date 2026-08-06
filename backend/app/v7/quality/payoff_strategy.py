"""Platform/genre payoff strategies used by the canonical V7 chain.

These are reader-experience strategies, not author personas.  They control
the curve and the variety of payoffs while leaving prose voice to the style
card and facts to Novel Brain.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


PAYOFF_STRATEGY_SCHEMA_VERSION = "payoff-strategy-v1"


_BASE_STRATEGIES: dict[str, dict[str, Any]] = {
    "fanqie_fast": {
        "label": "番茄快节奏",
        "strategy_id": "fanqie_fast",
        "opening_attention_chars": 300,
        "opening_attention_is_hard": False,
        # P0-3 质量整改：提高爽点强度默认值
        "default_intensity": "medium",        # P0-3: small → medium
        "early_min_intensity": "high",        # P0-3: medium → high
        "early_chapter_count": 3,
        "max_low_payoff_streak": 1,
        "feedback_required": True,
        "no_repeat_window": 3,
        # P0-3 质量整改：peak强度爽点间隔（每N章至少一次peak）
        "peak_intensity_interval": 5,
        "type_cycle": [
            "status_reversal", "money_or_resource", "information_advantage",
            "opponent_reaction", "career_progress", "reveal", "resource_gain",
        ],
        "chapter_modes": {
            "normal": {"active_choice_required": True, "visible_feedback_required": True},
            "aftermath": {"active_choice_required": False, "visible_feedback_required": True},
            "relationship": {"active_choice_required": False, "visible_feedback_required": True},
            "suspense": {"active_choice_required": False, "visible_feedback_required": True},
        },
        "directive": "快进入具体冲突；每章至少兑现一次读者期待，并把结果变成下一步压力。",
    },
    "qidian_depth": {
        "label": "起点长线升级",
        "strategy_id": "qidian_depth",
        "opening_attention_chars": 900,
        "opening_attention_is_hard": False,
        # P0-3 质量整改：提高爽点强度默认值
        "default_intensity": "medium",        # P0-3: small → medium
        "early_min_intensity": "medium",      # P0-3: 保持medium（起点慢热）
        "early_chapter_count": 3,
        "max_low_payoff_streak": 2,
        "feedback_required": False,
        "no_repeat_window": 4,
        # P0-3 质量整改：peak强度爽点间隔（每N章至少一次peak）
        "peak_intensity_interval": 7,
        "type_cycle": [
            "information_advantage", "resource_gain", "relationship_shift",
            "reveal", "breakthrough", "status_reversal", "sacrifice",
        ],
        "chapter_modes": {
            "normal": {"active_choice_required": True, "visible_feedback_required": True},
            "aftermath": {"active_choice_required": False, "visible_feedback_required": False},
            "relationship": {"active_choice_required": False, "visible_feedback_required": True},
            "suspense": {"active_choice_required": False, "visible_feedback_required": True},
        },
        "directive": "先铺垫依据再兑现结果；小冲突递进到阶段性高潮，不重复同一种打脸。",
    },
    "xuanhuan_upgrade": {
        "label": "传统玄幻升级",
        "strategy_id": "xuanhuan_upgrade",
        "opening_attention_chars": 500,
        "opening_attention_is_hard": False,
        # P0-3 质量整改：提高爽点强度默认值
        "default_intensity": "medium",        # P0-3: small → medium
        "early_min_intensity": "high",        # P0-3: medium → high
        "early_chapter_count": 3,
        "max_low_payoff_streak": 1,
        "feedback_required": True,
        "no_repeat_window": 3,
        # P0-3 质量整改：peak强度爽点间隔（每N章至少一次peak）
        "peak_intensity_interval": 7,
        "type_cycle": ["status_reversal", "breakthrough", "combat_advantage", "resource_gain", "reveal"],
        "chapter_modes": {"normal": {"active_choice_required": True, "visible_feedback_required": True}},
        "directive": "把境界差距、能力依据、实际验证和旁观反馈写成动作链，不用状态播报代替升级。",
    },
    "xuanhuan_mortal": {
        "label": "玄幻凡人/苟道",
        "strategy_id": "xuanhuan_mortal",
        "opening_attention_chars": 900,
        "opening_attention_is_hard": False,
        # P0-3 质量整改：苟道流保持慢热，default还是small
        "default_intensity": "small",         # P0-3: 保持small（苟道流慢热）
        "early_min_intensity": "medium",      # P0-3: 保持medium
        "early_chapter_count": 3,
        "max_low_payoff_streak": 2,
        "feedback_required": False,
        "no_repeat_window": 4,
        # P0-3 质量整改：peak强度爽点间隔（每N章至少一次peak）
        "peak_intensity_interval": 10,
        "type_cycle": ["resource_gain", "information_advantage", "survival", "hidden_strength", "reveal", "breakthrough"],
        "chapter_modes": {
            "normal": {"active_choice_required": True, "visible_feedback_required": True},
            "aftermath": {"active_choice_required": False, "visible_feedback_required": False},
        },
        "directive": "爽点来自资源、信息和风险判断的真实收益；苟可以克制，但不能停滞。",
    },
    "xuanhuan_cautious": {
        "label": "玄幻苟道流",
        "strategy_id": "xuanhuan_cautious",
        "opening_attention_chars": 1000,
        "opening_attention_is_hard": False,
        # P0-3 质量整改：苟道流保持慢热，default还是small
        "default_intensity": "small",         # P0-3: 保持small（苟道流慢热）
        "early_min_intensity": "medium",      # P0-3: 保持medium
        "early_chapter_count": 3,
        "max_low_payoff_streak": 2,
        "feedback_required": False,
        "no_repeat_window": 5,
        # P0-3 质量整改：peak强度爽点间隔（每N章至少一次peak）
        "peak_intensity_interval": 10,
        "type_cycle": [
            "survival", "resource_gain", "information_advantage",
            "hidden_strength", "rule_exploit", "relationship_shift", "reveal",
        ],
        "chapter_modes": {
            "normal": {"active_choice_required": True, "visible_feedback_required": True},
            "aftermath": {"active_choice_required": False, "visible_feedback_required": False},
            "suspense": {"active_choice_required": False, "visible_feedback_required": True},
        },
        "directive": "每次谨慎都必须换来可验证的生存、资源或信息收益；隐藏实力只在改变局面时揭示，不能把苟写成原地停滞。",
    },
    "xuanhuan_longlife": {
        "label": "玄幻长生流",
        "strategy_id": "xuanhuan_longlife",
        "opening_attention_chars": 900,
        "opening_attention_is_hard": False,
        # P0-3 质量整改：长生流保持慢热，default还是small
        "default_intensity": "small",         # P0-3: 保持small（长生流慢热）
        "early_min_intensity": "medium",      # P0-3: 保持medium
        "early_chapter_count": 3,
        "max_low_payoff_streak": 2,
        "feedback_required": False,
        "no_repeat_window": 5,
        # P0-3 质量整改：peak强度爽点间隔（每N章至少一次peak）
        "peak_intensity_interval": 10,
        "type_cycle": ["survival", "resource_gain", "hidden_strength", "relationship_shift", "reveal", "status_reversal"],
        "chapter_modes": {
            "normal": {"active_choice_required": True, "visible_feedback_required": True},
            "aftermath": {"active_choice_required": False, "visible_feedback_required": False},
        },
        "directive": "让寿元、时间和资源改变选择；系统提示只有在改变决策时出现，反差要靠后果而不是口号。",
    },
    "system": {
        "label": "系统/签到",
        "strategy_id": "system",
        "opening_attention_chars": 300,
        "opening_attention_is_hard": False,
        # P0-3 质量整改：提高爽点强度默认值
        "default_intensity": "medium",        # P0-3: small → medium
        "early_min_intensity": "high",        # P0-3: medium → high
        "early_chapter_count": 3,
        "max_low_payoff_streak": 1,
        "feedback_required": True,
        "no_repeat_window": 3,
        # P0-3 质量整改：peak强度爽点间隔（每N章至少一次peak）
        "peak_intensity_interval": 5,
        "type_cycle": ["system_reward", "ability_discovery", "resource_gain", "status_reversal", "reveal"],
        "chapter_modes": {"normal": {"active_choice_required": True, "visible_feedback_required": True}},
        "directive": "奖励必须改变主角选择并带来现实后果，不能连续用面板数字代替剧情。",
    },
    "urban_shenhao": {
        "label": "都市神豪",
        "strategy_id": "urban_shenhao",
        "opening_attention_chars": 500,
        "opening_attention_is_hard": False,
        # P0-3 质量整改：提高爽点强度默认值
        "default_intensity": "medium",        # P0-3: small → medium
        "early_min_intensity": "high",        # P0-3: medium → high
        "early_chapter_count": 3,
        "max_low_payoff_streak": 1,
        "feedback_required": True,
        "no_repeat_window": 3,
        # P0-3 质量整改：peak强度爽点间隔（每N章至少一次peak）
        "peak_intensity_interval": 5,
        "type_cycle": ["money_or_resource", "status_reversal", "industry_breakthrough", "opponent_reaction", "information_advantage"],
        "chapter_modes": {"normal": {"active_choice_required": True, "visible_feedback_required": True}},
        "directive": "金额、时间、资源和对手优势必须具体；爽点落到选择和结果，不只报资产数字。",
    },
    "urban_brainstorm": {
        "label": "都市脑洞",
        "strategy_id": "urban_brainstorm",
        "opening_attention_chars": 300,
        "opening_attention_is_hard": False,
        # P0-3 质量整改：提高爽点强度默认值
        "default_intensity": "medium",        # P0-3: small → medium
        "early_min_intensity": "high",        # P0-3: medium → high
        "early_chapter_count": 3,
        "max_low_payoff_streak": 1,
        "feedback_required": True,
        "no_repeat_window": 3,
        # P0-3 质量整改：peak强度爽点间隔（每N章至少一次peak）
        "peak_intensity_interval": 5,
        "type_cycle": ["rule_exploit", "reveal", "status_reversal", "information_advantage", "relationship_shift"],
        "chapter_modes": {"normal": {"active_choice_required": True, "visible_feedback_required": True}},
        "directive": "异常规则要迫使人物做选择；每次规则出现都要改变局面，不做规则展览。",
    },
}


def select_payoff_strategy(platform: str, genre: str, subgenre: str) -> dict[str, Any]:
    if subgenre == "urban_shenhao":
        key = "urban_shenhao"
    elif subgenre == "urban_brainstorm":
        key = "urban_brainstorm"
    elif subgenre in {"xuanhuan_longlife"}:
        key = "xuanhuan_longlife"
    elif subgenre in {"xuanhuan_cautious", "苟道流", "苟道"}:
        key = "xuanhuan_cautious"
    elif subgenre == "xuanhuan_mortal":
        key = "xuanhuan_mortal"
    elif subgenre == "xuanhuan_upgrade":
        key = "xuanhuan_upgrade"
    elif subgenre in {"xuanhuan_system", "urban_system"}:
        key = "system"
    elif platform == "qidian":
        key = "qidian_depth"
    else:
        key = "fanqie_fast"
    return deepcopy(_BASE_STRATEGIES[key])


def choose_payoff_type(
    strategy: dict[str, Any] | None,
    *,
    chapter_number: int = 1,
    allowed_types: list[str] | None = None,
    recent_types: list[str] | None = None,
) -> str:
    strategy = strategy if isinstance(strategy, dict) else _BASE_STRATEGIES["fanqie_fast"]
    allowed = [str(item) for item in (allowed_types or []) if str(item)]
    cycle = [str(item) for item in strategy.get("type_cycle") or [] if str(item)]
    pool = [item for item in cycle if not allowed or item in allowed]
    pool.extend(item for item in allowed if item not in pool)
    if not pool:
        pool = cycle or ["status_reversal"]
    recent = [str(item) for item in (recent_types or []) if str(item)]
    window = max(0, int(strategy.get("no_repeat_window") or 0))
    recent_window = recent[-window:] if window else []
    candidates = [item for item in pool if item not in recent_window]
    if not candidates:
        candidates = pool
    # History is the primary rotation signal.  Selecting the first available
    # item in the declared cycle makes the behavior explainable: a new chapter
    # takes the first payoff type not used in the configured window, rather
    # than jumping to a different type merely because the chapter number
    # changed.
    return candidates[0]


def strategy_metadata(strategy: dict[str, Any] | None) -> dict[str, Any]:
    strategy = strategy if isinstance(strategy, dict) else {}
    return {
        "schema_version": PAYOFF_STRATEGY_SCHEMA_VERSION,
        "strategy_id": strategy.get("strategy_id"),
        "label": strategy.get("label"),
        "opening_attention_chars": strategy.get("opening_attention_chars"),
        "opening_attention_is_hard": bool(strategy.get("opening_attention_is_hard")),
        "default_intensity": strategy.get("default_intensity"),
        "early_min_intensity": strategy.get("early_min_intensity"),
        "early_chapter_count": strategy.get("early_chapter_count"),
        "max_low_payoff_streak": strategy.get("max_low_payoff_streak"),
        "feedback_required": bool(strategy.get("feedback_required")),
        "no_repeat_window": strategy.get("no_repeat_window"),
        "type_cycle": list(strategy.get("type_cycle") or []),
    }
