"""Compiled web-novel quality strategy for the canonical V7 chain.

The user's distilled skills are methodology sources, not independent runtime
agents.  This module keeps their provenance and compiles the stable parts into
small, deterministic policy objects consumed by the existing quality profile,
planning contract and chapter payoff layers.

Keeping this registry separate from prose prompts is intentional: a source
document can be revised or fail pressure testing without silently changing the
production generation chain.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .market_snapshot import (
    MARKET_SNAPSHOT_SOURCE_ID,
    market_benchmark_directive,
    market_snapshot_metadata,
    resolve_market_benchmark,
)


WEBNOVEL_STRATEGY_SCHEMA_VERSION = "webnovel-quality-strategy-v1"


# The compendium is the canonical source for this integration.  The loose
# ``novel-test/skills`` directory is retained as a mirror/check only.  The
# source is still marked as a methodology candidate because its own pipeline
# is in pressure testing and has no per-skill production result files yet.
KNOWLEDGE_SOURCE_REGISTRY: tuple[dict[str, Any], ...] = (
    {
        "id": "payoff_closed_loop",
        "label": "爽点闭环四步法",
        "layer": "core",
        "runtime_targets": ["chapter_payoff", "pacing"],
    },
    {
        "id": "face_slap_four_steps",
        "label": "打脸四部曲",
        "layer": "core",
        "runtime_targets": ["payoff_strategy"],
    },
    {
        "id": "opening_dual_paradigm",
        "label": "开局设计双范式",
        "layer": "core",
        "runtime_targets": ["quality_profile", "planning"],
    },
    {
        "id": "pacing_framework",
        "label": "节奏控制框架",
        "layer": "core",
        "runtime_targets": ["pacing", "chapter_contract"],
    },
    {
        "id": "golden_finger_five_principles",
        "label": "金手指设计五原则",
        "layer": "core",
        "runtime_targets": ["planning_contract", "novel_brain"],
    },
    {
        "id": "character_three_layers",
        "label": "人物塑造三件套",
        "layer": "core",
        "runtime_targets": ["novel_brain", "truth_files"],
    },
    {
        "id": "deai_eight_methods",
        "label": "去AI味八法",
        "layer": "core",
        "runtime_targets": ["generation_prompt", "deai_pipeline"],
    },
    {
        "id": "platform_style_matrix",
        "label": "平台风格适配矩阵",
        "layer": "core",
        "runtime_targets": ["quality_profile"],
    },
    {
        "id": "cautious_path",
        "label": "苟道流写作法",
        "layer": "mechanic",
        "runtime_targets": ["mechanic_adapter", "payoff_strategy"],
    },
    {
        "id": "system_flow",
        "label": "系统流设计法",
        "layer": "mechanic",
        "runtime_targets": ["mechanic_adapter", "payoff_strategy"],
    },
    {
        "id": "longevity_flow",
        "label": "长生流写作法",
        "layer": "mechanic",
        "runtime_targets": ["mechanic_adapter", "payoff_strategy"],
    },
    {
        "id": "golden_finger_innovation",
        "label": "金手指创新三路径",
        "layer": "innovation",
        "runtime_targets": ["planning_contract", "creative_bible"],
    },
    {
        "id": "golden_finger_distillation_v1_20260805",
        "label": "网文金手指大全·精华长文",
        "layer": "distillation",
        "origin": "user-provided-distillation",
        "runtime_targets": ["quality_profile", "planning", "chapter_payoff"],
    },
    {
        "id": "quality_failure_reports_20260805",
        "label": "历轮生成质量分析与失败模式报告",
        "layer": "evidence",
        "origin": "user-provided-analysis",
        "runtime_targets": ["failure_patterns", "review_engine", "regression"],
    },
    {
        "id": "quality_six_stage_roadmap_20260805",
        "label": "爽文质量改造六阶段路线图",
        "layer": "process",
        "origin": "user-provided-analysis",
        "runtime_targets": ["pre_generation_contract", "quality_gate", "learning"],
    },
    {
        "id": "novel_reviewer_reference_20260805",
        "label": "novel-reviewer 全维度审查与 AI 味候选词库",
        "layer": "reference",
        "origin": "user-provided-review-skill",
        "runtime_targets": ["review_engine", "deai_metrics", "editorial_view"],
    },
    {
        "id": "webnovel_quality_packs_20260805",
        "label": "都市/玄幻/平台适配/作者蒸馏质量包",
        "layer": "methodology",
        "origin": "user-provided-quality-packs",
        "runtime_targets": ["quality_profile", "style_plugin", "payoff_strategy"],
    },
    {
        "id": "simulator_future_branch_design_20260805",
        "label": "模拟器全终局推演与收益回收设计",
        "layer": "mechanic",
        "origin": "user-provided-analysis",
        "runtime_targets": ["mechanic_adapter", "novel_brain", "state_writeback"],
    },
    {
        "id": MARKET_SNAPSHOT_SOURCE_ID,
        "label": "网文全平台套路研究库（967本实证快照）",
        "layer": "empirical",
        "runtime_targets": ["market_analysis", "quality_profile", "opening_benchmark"],
    },
)


_FEEDBACK_CHANNELS = (
    "attitude",       # 对手/旁观者态度变化
    "resource",       # 金钱、物资、功法、情报等资源变化
    "status",         # 身份、排名、权限、地位变化
    "relationship",   # 关系、信任、阵营变化
    "rule",           # 规则被验证、利用或改写
    "risk",           # 新追杀、暴露、债务或时间压力
)


# P2-6 质量整改：反馈强度分级与全场级反馈设计规则
_FEEDBACK_INTENSITY_RULES: dict[str, Any] = {
    "intensity_levels": {
        "small": {
            "label": "小反馈",
            "description": "局部、个人级别的反馈，影响范围小",
            "examples": [
                "对手脸色一变",
                "旁边几个人窃窃私语",
                "主角获得少量资源",
                "某个人对主角态度改变",
            ],
            "适用场景": "小爽点、日常情节、铺垫阶段",
        },
        "medium": {
            "label": "中反馈",
            "description": "房间/小队级别的反馈，影响范围中等",
            "examples": [
                "满屋子人都安静了",
                "整个小队都惊呆了",
                "主角获得重要资源",
                "一个组织对主角态度改变",
            ],
            "适用场景": "中型爽点、情节推进、小高潮",
        },
        "high": {
            "label": "大反馈",
            "description": "全场/全城级别的反馈，影响范围大",
            "examples": [
                "全场鸦雀无声",
                "众人都懵了",
                "全城都在议论主角",
                "一个大势力对主角刮目相看",
            ],
            "适用场景": "大爽点、大高潮、重要转折",
        },
        "peak": {
            "label": "全场级反馈",
            "description": "全场/全行业/全大陆级别的反馈，影响范围极大",
            "examples": [
                "全场一片死寂，落针可闻",
                "所有人都石化了，不敢相信自己的眼睛",
                "整个修炼界都震动了",
                "无数大佬坐不住了",
                "刷新了所有人的认知",
                "颠覆了整个行业的常识",
            ],
            "适用场景": "peak强度爽点、终极高潮、卷末大爽点",
        },
    },
    "matching_rule": {
        "description": "爽点强度必须和反馈强度匹配，高强度爽点必须配高强度反馈",
        "rules": [
            "small爽点 → small或medium反馈",
            "medium爽点 → medium或high反馈",
            "high爽点 → high或peak反馈",
            "peak爽点 → 必须配peak反馈（全场级）",
        ],
        "violation_penalty": "爽点强度高但反馈太弱，爽感会大打折扣，读者会觉得'就这？'",
    },
    "crowd_feedback_design": {
        "label": "全场级反馈设计原则",
        "description": "避免模板化的'众人震惊'，要写出层次感和真实感",
        "principles": [
            "分层反应：先前排，再中排，最后后排，不同位置的人反应不同",
            "身份差异：大佬的反应和小喽啰的反应不一样，内行和外行的反应不一样",
            "动作细节：不要只写'众人惊呆了'，要写具体的动作（手里的杯子掉了、筷子停在半空、倒吸凉气等）",
            "声音变化：从喧闹到安静的过程，先有人失声，然后越来越安静，最后鸦雀无声",
            "后续影响：反馈不能只停留在当场，还要有后续影响（消息传开、大佬关注、敌人忌惮等）",
        ],
        "anti_patterns": [
            "千篇一律的'众人哗然'（所有人反应都一样）",
            "只有旁白描述，没有具体动作和细节",
            "反馈停留在当场，没有后续影响",
            "小爽点配大反馈（比例失调）",
        ],
    },
}


_VILLAIN_DESIGN_RULES: dict[str, Any] = {
    "cross_level_face_slap": {
        "label": "越级打脸设计",
        "description": "爽文核心爽点之一，主角以弱胜强、越级挑战，打脸比自己强的对手。",
        "core_principle": "反派必须比主角强至少一个等级，打脸才有足够爽感。",
        "early_stage_rule": "前10章的反派必须比主角强1-2个大等级，让读者觉得'这怎么赢'，然后主角用金手指或智慧逆袭。",
        "escalation_rule": "反派强度随剧情逐步升级，打完小的来中的，打完中的来大的，打完大的来更大的。",
        "face_slap_structure": [
            "反派嚣张挑衅（让读者恨）",
            "众人不看好主角（压低预期）",
            "主角隐藏实力（蓄势）",
            "主角出手碾压（爆发）",
            "全场哗然/反派崩溃（反馈）",
            "更大的反派出现（新压力）",
        ],
        "villain_intensity_levels": {
            "small": "小喽啰/看门狗/路人反派",
            "medium": "小boss/门派弟子/富二代",
            "high": "大boss/长老/家族族长",
            "peak": "终极boss/宗主/皇帝/仙人",
        },
    },
    "villain_quality": {
        "label": "反派质量要求",
        "description": "好的反派能让爽点更爽，不能是弱智反派。",
        "intelligence_requirement": "反派必须有基本智商，不能犯低级错误，否则打脸没有成就感。",
        "motivation_requirement": "反派必须有明确的动机和利益诉求，不能为了坏而坏。",
        "strength_requirement": "反派必须有真实的实力背景，不能只是嘴上厉害，一触即溃。",
        "escalation_requirement": "每个阶段的反派都要比上一个阶段的更强、更聪明、更有背景。",
    },
}


_MECHANIC_RULES: dict[str, dict[str, Any]] = {
    "system": {
        "label": "系统/任务",
        # P0-5 质量整改：金手指爽感强度
        "payoff_intensity": "high",        # P0-5: 系统流爽感强
        "loop": "任务或触发→主角选择→执行→奖励落地→限制/失败代价→现实状态变化",
        "guard": "奖励不能替主角做判断；任务、冷却、失败和现实后果必须可追踪。",
    },
    "simulator": {
        "label": "人生模拟/未来推演",
        # P0-5 质量整改：金手指爽感强度
        "payoff_intensity": "high",        # P0-5: 模拟器爽感强
        "loop": "从当前状态推演到死亡或终局→比较分支→选择回收收益→现实写回→因果重算",
        "guard": "模拟结果不是现实事实；不能无条件全拿，也不能用预知代替现实行动。",
    },
    "rebirth": {
        "label": "重生/先知",
        # P0-5 质量整改：金手指爽感强度
        "payoff_intensity": "high",        # P0-5: 重生爽感强
        "loop": "记忆优势→主动改写→现实约束→蝴蝶效应→新收益与新风险",
        "guard": "未来知识会因改写而失真，不能把记忆当成无成本百科全书。",
    },
    "space": {
        "label": "空间/资源",
        # P0-5 质量整改：金手指爽感强度
        "payoff_intensity": "medium",      # P0-5: 空间爽感中等
        "loop": "取用或生产→资源选择→现实使用→库存/运输/暴露代价→竞争升级",
        "guard": "空间不是无限仓库；来源、库存、消耗和被发现的风险必须存在。",
    },
    "panel": {
        "label": "属性面板",
        # P0-5 质量整改：金手指爽感强度
        "payoff_intensity": "medium",      # P0-5: 面板爽感中等
        "loop": "获得点数→分配取舍→场景验证→能力提升→上限/身体/社会后果",
        "guard": "数字不能替代事件结果；提升必须有条件、验证和新风险。",
    },
    "inheritance": {
        "label": "传承/血脉/体质",
        # P0-5 质量整改：金手指爽感强度
        "payoff_intensity": "medium",      # P0-5: 传承爽感中等
        "loop": "觉醒条件→力量验证→身份与责任→反噬/争夺→阶段成长",
        "guard": "传承不能一次性替代成长；强血脉必须同时带来敌人、责任或失控。",
    },
    "time_loop": {
        "label": "时间循环/回溯",
        # P0-5 质量整改：金手指爽感强度
        "payoff_intensity": "high",        # P0-5: 时间循环爽感强
        "loop": "循环触发→保留信息→改变关键选择→分支偏差→不可逆损耗",
        "guard": "循环不能无限试错；记忆、身体、关系或因果必须留下成本。",
    },
    "longevity": {
        "label": "长生/苟道",
        # P0-5 质量整改：金手指爽感强度
        "payoff_intensity": "low",         # P0-5: 长生流慢热，爽感低
        "loop": "时间积累→资源与底蕴增长→暴露或时代变化→选择出手→身份/实力反馈→更高层压力",
        "guard": "活得久不等于自动无敌；时间必须带来关系代价、环境变化、资源消耗或更高层敌人。",
    },
    "predation": {
        "label": "掠夺/吞噬/爆装",
        # P0-5 质量整改：金手指爽感强度
        "payoff_intensity": "high",        # P0-5: 掠夺爽感强
        "loop": "击败目标→选择掠夺内容→兼容/转化→即时成长→污染/追查/容量压力→新的主动狩猎目标",
        "guard": "不能击杀即无限叠加；收益要有容量、冲突、污染、追查或选择成本。",
    },
    "summon": {
        "label": "召唤/契约/分身",
        # P0-5 质量整改：金手指爽感强度
        "payoff_intensity": "medium",      # P0-5: 召唤爽感中等
        "loop": "满足条件→召唤或分化→指挥与分工→行动反馈→资源/忠诚/损伤代价→召唤对象反过来改变主线",
        "guard": "召唤物不能替主角无条件代打；数量、忠诚、成长、死亡或失控必须可追踪。",
    },
    "artifact": {
        "label": "器物/法宝/古书",
        # P0-5 质量整改：金手指爽感强度
        "payoff_intensity": "medium",      # P0-5: 法宝爽感中等
        "loop": "发现或激活→理解规则→选择使用场景→功能兑现→修复/损耗/争夺→器物规则升级或改变选择",
        "guard": "器物不是万能道具；每次升级要改变解题方式，不得只增加数值。",
    },
    "livestream": {
        "label": "直播/曝光/弹幕",
        # P0-5 质量整改：金手指爽感强度
        "payoff_intensity": "medium",      # P0-5: 直播爽感中等
        "loop": "获得观众信息或曝光→筛选真假→采取行动→热度/资源/舆论反馈→暴露与误导风险→更大范围注视",
        "guard": "弹幕不是全知旁白；信息要有延迟、偏见、误导或隐私代价。",
    },
    "rule_game": {
        "label": "规则怪谈/副本",
        # P0-5 质量整改：金手指爽感强度
        "payoff_intensity": "medium",      # P0-5: 规则怪谈爽感中等
        "loop": "接触规则→验证禁忌→选择试探或绕行→获得局部生路→承担违规后果→破局并进入新规则",
        "guard": "规则必须能回溯验证；不能临场凭空加规则，也不能只靠解释而没有行动试错。",
    },
    "profession_skill": {
        "label": "职业/技能/文娱",
        # P0-5 质量整改：金手指爽感强度
        "payoff_intensity": "medium",      # P0-5: 职业技能爽感中等
        "loop": "展示专业能力→解决具体问题→结果被验证→名声/资源/舞台升级→行业竞争与误判代价→更大目标",
        "guard": "技能不能万能；结果必须经过事件验证，并受时间、资源、行业规则和对手影响。",
    },
    "identity_relation": {
        "label": "身份/关系反差",
        # P0-5 质量整改：金手指爽感强度
        "payoff_intensity": "high",        # P0-5: 身份反差爽感强
        "loop": "被低估或误解→选择隐藏/承认→采取行动→身份或关系反馈→信任/责任/暴露代价→关系重排",
        "guard": "身份不能只靠旁白揭晓；每次亮牌都要付出信任、暴露或责任代价。",
    },
    "invincible_opening": {
        "label": "无敌开局/扮猪吃虎",
        # P0-5 质量整改：金手指爽感强度
        "payoff_intensity": "peak",        # P0-5: 无敌开局爽感最强
        "loop": "隐藏底牌→制造误判→选择亮牌时机→局面反转→对手与旁观者反馈→暴露更高层压力",
        "guard": "不能连续靠隐藏实力重复同一种打脸；必须升级对手、场景和亮牌代价。",
        # P0-5 质量整改：开局碾压设计导向
        "opening_domination": True,        # P0-5: 开局碾压级优势
        "opening_showcase_chapter": 3,     # P0-5: 前3章必须展示一次碾压级优势
    },
    "anti_trope": {
        "label": "反套路/弱金手指",
        # P0-5 质量整改：金手指爽感强度
        "payoff_intensity": "low",         # P0-5: 弱金手指爽感低
        "loop": "识别能力限制→设计策略→承担失败风险→用判断与积累取得结果→形成可见进展→面对更高难题",
        "guard": "反套路不能退化成没有反馈；每个弱点都要转化为具体策略和可见进展。",
    },
    "ability": {
        "label": "异能/法宝/特殊能力",
        # P0-5 质量整改：金手指爽感强度
        "payoff_intensity": "medium",      # P0-5: 异能爽感中等
        "loop": "触发能力→选择使用方式→动作验证→收益→范围/冷却/暴露代价",
        "guard": "能力不能只靠旁白宣布；每次使用必须改变场面并留下后果。",
    },
    "commerce": {
        "label": "商城/交易",
        # P0-5 质量整改：金手指爽感强度
        "payoff_intensity": "medium",      # P0-5: 商城爽感中等
        "loop": "积累货币→兑换选择→即时收益→库存/价格/资源消耗→长期取舍",
        "guard": "商城不能无限补洞；资源来源、价格和消耗必须写回账本。",
    },
}


def _unique(values: list[Any] | tuple[Any, ...]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def knowledge_source_metadata() -> dict[str, Any]:
    """Return auditable source metadata without loading source prose at runtime."""
    snapshot = market_snapshot_metadata()
    return {
        "schema_version": WEBNOVEL_STRATEGY_SCHEMA_VERSION,
        "canonical_source": "webnovel-golden-finger-compendium",
        "mirror_source": "novel-test/skills",
        "distillation_source": "网文金手指大全·精华长文（用户提供，2026-08-05）",
        "source_status": "methodology_candidate_plus_empirical_snapshot",
        "pressure_test_status": "deterministic_regression_passed_provider_validation_pending",
        "sources": [
            (
                {
                    **deepcopy(source),
                    "source": "local-research-html",
                    "validated_for_runtime": True,
                    "runtime_mode": "soft_evidence_only",
                    "hard_gate": False,
                }
                if source["id"] == MARKET_SNAPSHOT_SOURCE_ID
                else {
                    **deepcopy(source),
                    "source": source.get("origin", "webnovel-golden-finger-compendium"),
                    "mirror": "novel-test/skills",
                    "validated_for_runtime": False,
                    "runtime_mode": "methodology_compilation",
                }
            )
            for source in KNOWLEDGE_SOURCE_REGISTRY
        ],
        "empirical_snapshot": {
            "source": snapshot["source"],
            "coverage": snapshot["coverage"],
            "hard_gate": False,
            "limitations": snapshot["limitations"],
        },
    }


def resolve_webnovel_strategy(
    *,
    platform: str = "fanqie",
    genre: str = "urban",
    subgenre: str = "",
    mechanic_families: list[str] | None = None,
    style_plugin: str = "",
) -> dict[str, Any]:
    """Compile the stable quality rules for one V7 generation context."""
    platform_key = str(platform or "fanqie").strip().lower()
    genre_key = str(genre or "urban").strip().lower()
    subgenre_key = str(subgenre or "").strip().lower()
    families = _unique(list(mechanic_families or []))
    if platform_key == "qidian":
        opening_mode = "golden_three"
        opening_directive = "前三章完成主角、核心规则和第一轮小高潮；先铺依据再兑现结果。"
    else:
        opening_mode = "fast_hook"
        opening_directive = "前 300 字进入具体处境或异常；第一章给出可见反馈和下一步问题。"

    family_rules = [
        {
            "family": family,
            **deepcopy(_MECHANIC_RULES[family]),
        }
        for family in families
        if family in _MECHANIC_RULES
    ]
    innovation_paths = {
        "combination": "把两个熟悉机制组合成新的选择面，不能只把名称拼在一起。",
        "cost": "把代价变成剧情资源或长期债务，让能力越强取舍越具体。",
        "reverse": "反转读者对能力用途、收益或限制的预期，但必须提前埋下可回溯依据。",
    }
    if not family_rules:
        innovation_paths = {
            "combination": innovation_paths["combination"],
            "cost": innovation_paths["cost"],
            "reverse": innovation_paths["reverse"],
        }

    market_benchmark = resolve_market_benchmark(
        platform=platform_key,
        genre=genre_key,
        mechanic_families=families,
    )

    return {
        "schema_version": WEBNOVEL_STRATEGY_SCHEMA_VERSION,
        "strategy_id": f"{platform_key}:{genre_key}:{subgenre_key or 'default'}",
        "platform": platform_key,
        "genre": genre_key,
        "subgenre": subgenre_key,
        "style_plugin": str(style_plugin or ""),
        "opening": {
            "mode": opening_mode,
            "directive": opening_directive,
            "hard_word_count": False,
        },
        "payoff": {
            "phases": ["pressure", "build", "burst", "feedback", "aftershock"],
            "feedback_channels": list(_FEEDBACK_CHANNELS),
            "feedback_no_repeat_window": 3,
            "rule": "每章至少有一个可见结果；反馈可以是态度、资源、身份、关系、规则或风险变化，不强制群众围观。",
            # P2-6 质量整改：反馈强度分级与全场级反馈设计规则
            "intensity_rules": deepcopy(_FEEDBACK_INTENSITY_RULES),
        },
        # P2-5 质量整改：反派设计与越级打脸规则
        "villain_design": deepcopy(_VILLAIN_DESIGN_RULES),
        "mechanic": {
            "families": families,
            "required_fields": [
                "trigger_and_loop", "capability_loop", "choice_surface",
                "visible_payoff", "limits_and_costs", "failure_and_risks",
                "state_writeback", "plot_coupling", "progression",
            ],
            "innovation_paths": innovation_paths,
            "family_rules": family_rules,
            "market_evidence": market_benchmark.get("mechanic_evidence") or {},
            "design_axes": market_benchmark.get("design_axes") or {},
            "design_rule": market_benchmark.get("design_rule") or "",
        },
        "market_benchmark": market_benchmark,
        "deai": {
            "pre_generation": [
                "减少整齐排比、模板化收束和连续同构句式，保留自然口语与人物差异。",
                "不禁用任何单个标点；只限制整章异常密度、连续重复和模板化堆叠。",
                "故意不完美只指自然停顿、视角差异和非对称节奏，不制造错别字、逻辑错误或强行口语。",
            ],
            "protected_zones": [
                "爽点动作与反转结果", "金手指收益和关键数字", "真相文件事实", "章末钩子",
            ],
        },
        "learning": {
            "candidate_after_min_observations": 3,
            "canary_rollout_percent": 25,
            "promote_after_successful_canaries": 3,
            "single_report_can_change_global_rule": False,
        },
        "knowledge_sources": [source["id"] for source in KNOWLEDGE_SOURCE_REGISTRY],
    }


def choose_feedback_channel(
    strategy: dict[str, Any] | None,
    *,
    payoff_type: str = "",
    recent_feedback_types: list[str] | None = None,
) -> str:
    """Choose a feedback channel while avoiding a repeated reaction template."""
    strategy = strategy if isinstance(strategy, dict) else {}
    payoff = strategy.get("payoff") if isinstance(strategy.get("payoff"), dict) else {}
    channels = [str(item) for item in payoff.get("feedback_channels") or _FEEDBACK_CHANNELS]
    recent = [str(item) for item in recent_feedback_types or [] if str(item)]
    preferred = {
        "money_or_resource": "resource",
        "resource_gain": "resource",
        "status_reversal": "status",
        "opponent_reaction": "attitude",
        "relationship_shift": "relationship",
        "rule_exploit": "rule",
        "survival": "risk",
        "reveal": "rule",
        "information_advantage": "rule",
    }.get(str(payoff_type or ""), "")
    ordered = ([preferred] if preferred in channels else []) + [item for item in channels if item != preferred]
    window = max(1, int(payoff.get("feedback_no_repeat_window") or 3))
    recent_tail = set(recent[-window:])
    return next((item for item in ordered if item not in recent_tail), ordered[0] if ordered else "status")


def strategy_metadata(strategy: dict[str, Any] | None) -> dict[str, Any]:
    """Return compact provenance and policy metadata for API/UI evidence."""
    strategy = strategy if isinstance(strategy, dict) else {}
    payoff = strategy.get("payoff") if isinstance(strategy.get("payoff"), dict) else {}
    mechanic = strategy.get("mechanic") if isinstance(strategy.get("mechanic"), dict) else {}
    market = strategy.get("market_benchmark") if isinstance(strategy.get("market_benchmark"), dict) else {}
    market_source = market.get("source") if isinstance(market.get("source"), dict) else {}
    market_platform = market.get("platform") if isinstance(market.get("platform"), dict) else {}
    market_genre = market.get("genre") if isinstance(market.get("genre"), dict) else {}
    return {
        "schema_version": strategy.get("schema_version", WEBNOVEL_STRATEGY_SCHEMA_VERSION),
        "strategy_id": strategy.get("strategy_id"),
        "opening_mode": (strategy.get("opening") or {}).get("mode"),
        "mechanic_families": list(mechanic.get("families") or []),
        "innovation_paths": list((mechanic.get("innovation_paths") or {}).keys()),
        "payoff_phases": list(payoff.get("phases") or []),
        "feedback_channels": list(payoff.get("feedback_channels") or []),
        "knowledge_sources": list(strategy.get("knowledge_sources") or []),
        "market_snapshot": {
            "source_id": market_source.get("id"),
            "snapshot_date": market_source.get("snapshot_date"),
            "platform": market_platform.get("label"),
            "platform_sample": market_platform.get("books"),
            "genre": market_genre.get("label"),
            "genre_sample": market_genre.get("books"),
            "with_text": market_genre.get("with_text"),
            "hard_gate": bool(market.get("hard_gate", False)),
        },
    }
