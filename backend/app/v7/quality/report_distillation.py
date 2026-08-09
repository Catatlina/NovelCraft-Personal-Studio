"""Structured runtime rules distilled from the user's web-novel report.

The source report contains prose samples, aggregate statistics, and genre
notes. Only stable, explainable parts are compiled here. Raw excerpts,
titles, website noise, and author imitation are intentionally excluded.
Numeric observations are soft metrics and never become a publish gate alone.
"""
from __future__ import annotations

import re
from copy import deepcopy
from statistics import mean, median
from typing import Any


REPORT_RULES_SCHEMA_VERSION = "webnovel-report-distilled-v1"
REPORT_SOURCE_ID = "webnovel-distillation-report-20260808"

REPORT_SOURCE_METADATA: dict[str, Any] = {
    "id": REPORT_SOURCE_ID,
    "snapshot_date": "2026-08-08",
    "source_label": "网文蒸馏报告",
    "source_paths": ["概览.md", "深度质量包/*.md", "知识库/*.md"],
    "sample_scope": {
        "books_with_features": 26335,
        "full_corpus_books": 39580,
        "deep_quality_genres": 5,
        "platforms": ["fanqie", "qidian"],
    },
    "runtime_mode": "compiled_methodology_and_soft_evidence",
    "hard_gate": False,
    "excluded_from_runtime": [
        "R段原文",
        "标题样本",
        "网站水印/域名广告",
        "作者或具体作品模仿",
        "未提供清洗与置信度的全量粗口统计",
    ],
}


def _pack(
    pack_id: str,
    label: str,
    *,
    directive: list[str],
    hard_contracts: list[str],
    ledger_rules: list[str],
    soft_metrics: dict[str, Any],
    anti_patterns: list[str],
    validator_targets: list[str],
    report_refs: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": REPORT_RULES_SCHEMA_VERSION,
        "pack_id": pack_id,
        "label": label,
        "directive": directive,
        "hard_contracts": hard_contracts,
        "ledger_rules": ledger_rules,
        "soft_metrics": soft_metrics,
        "anti_patterns": anti_patterns,
        "validator_targets": validator_targets,
        "report_refs": report_refs,
        "source_id": REPORT_SOURCE_ID,
        "hard_gate": False,
    }


# These are short semantic controls. They enrich the existing V7 profile
# instead of copying long report prose into every provider call.
_GENRE_PACKS: dict[str, dict[str, Any]] = {
    "urban": _pack(
        "genre-urban",
        "都市系统/爽文",
        directive=[
            "现实场景先落到具体需求、资源和风险，金手指只改变选择，不替主角自动通关。",
            "金钱、职位、项目和关系要通过行动产生可见变化，不能只用旁白宣布成功。",
        ],
        hard_contracts=[
            "每章至少有一处资源、身份、关系或风险的可见变化。",
            "系统奖励或能力收益必须在剧情中被使用、验证或产生代价。",
        ],
        ledger_rules=["资金/债务", "职业或行业事实", "系统任务与奖励", "现实后果"],
        soft_metrics={
            "chapter_chars_target": [1800, 2800],
            "paragraph_chars_target": [30, 70],
            "short_paragraph_ratio_target": [0.25, 0.50],
            "sentence_chars_target_max": 30,
            "long_paragraph_run_max": 2,
        },
        anti_patterns=["百科式说明", "只报资产数字", "系统面板替代事件", "章末无具体压力"],
        validator_targets=["chapter_payoff", "continuity", "deai_metrics"],
        report_refs=["深度质量包/quality-pack-都市系统.md", "知识库/kb-都市系统.md"],
    ),
    "xuanhuan": _pack(
        "genre-xuanhuan",
        "玄幻修仙",
        directive=[
            "升级要写清契机、代价、能力变化和实际验证；越级逆转必须有设定内依据。",
            "资源、战斗、势力和因果共同推进，不用境界播报或整段设定说明代替戏。",
        ],
        hard_contracts=[
            "境界突破或越级胜利必须能在本书事实账本中找到依据与代价。",
            "重要法宝、功法、伤势和资源变化必须有来源或消耗记录。",
        ],
        ledger_rules=["境界与能力边界", "功法/法器/资源消耗", "伤势与恢复", "势力关系", "伏笔与因果"],
        soft_metrics={
            "chapter_chars_target": [2000, 2700],
            "paragraph_chars_target": [30, 70],
            "short_paragraph_ratio_target": [0.25, 0.50],
            "sentence_chars_target_max": 30,
            "long_paragraph_run_max": 2,
        },
        anti_patterns=["万能境界", "见面秒杀", "连续两级突破", "围观反应模板化", "装饰性比喻"],
        validator_targets=["chapter_payoff", "continuity", "world_constraint", "deai_metrics"],
        report_refs=["深度质量包/quality-pack-玄幻修仙.md", "知识库/kb-玄幻修仙.md"],
    ),
    "suspense": _pack(
        "genre-suspense",
        "悬疑灵异",
        directive=[
            "恐怖来自未知、规则和选择后果，不靠血腥堆砌；先展示规则如何迫使人物选择。",
            "新线索必须能回溯到前文，推理过程要落在已获得的信息和可定位证据上。",
        ],
        hard_contracts=[
            "反转或推理结论必须能回溯到前文线索，禁止凭空想到。",
            "规则改变局面时必须同时写出限制、漏洞或代价。",
        ],
        ledger_rules=["线索与埋点", "规则版本", "信息掌握者", "推理证据", "安全区限制", "鬼怪/异常等级"],
        soft_metrics={
            "chapter_chars_target": [1800, 2700],
            "paragraph_chars_target": [30, 75],
            "short_paragraph_ratio_target": [0.25, 0.50],
            "sentence_chars_target_max": 30,
            "long_paragraph_run_max": 2,
        },
        anti_patterns=["突然想到式推理", "规则展览", "只靠血腥制造恐怖", "章末无疑问/威胁"],
        validator_targets=["continuity", "chapter_payoff", "deai_metrics"],
        report_refs=["深度质量包/quality-pack-悬疑灵异.md", "知识库/kb-悬疑灵异.md"],
    ),
    "history": _pack(
        "genre-history",
        "历史穿越",
        directive=[
            "制度、官职和称谓通过角色动作、利益和冲突呈现，不写百科式说明。",
            "现代知识必须落成具体方案、资源和阻力，同时允许历史信息差因蝴蝶效应失效。",
        ],
        hard_contracts=[
            "时代、地点、官职、称谓和关键物件必须与本书历史账本一致。",
            "现代知识或穿越优势必须经过行动验证，并产生资源、关系或风险变化。",
        ],
        ledger_rules=["年月日与时代", "官职/制度", "地理与军政", "经济与货币", "现代知识应用", "蝴蝶效应"],
        soft_metrics={
            "chapter_chars_target": [2100, 2900],
            "paragraph_chars_target": [35, 80],
            "short_paragraph_ratio_target": [0.20, 0.40],
            "sentence_chars_target_max": 30,
            "sensory_anchor_per_500_chars_target": 1,
            "long_paragraph_run_max": 2,
        },
        anti_patterns=["现代称谓错置", "制度百科", "现代物品无突兀感", "先知优势永久有效"],
        validator_targets=["continuity", "world_constraint", "chapter_payoff", "deai_metrics"],
        report_refs=["深度质量包/quality-pack-历史穿越.md", "知识库/kb-历史穿越.md"],
    ),
    "rebirth": _pack(
        "genre-rebirth",
        "重生逆袭",
        directive=[
            "前世记忆先服务当前选择，展示边界和蝴蝶效应，不把未来预知写成无条件答案。",
            "情感锚点必须落到具体重逢、动作和选择，逆袭按积累资本、小胜、暴露和大爆发递进。",
        ],
        hard_contracts=[
            "前世信息必须有来源，并允许在后续因蝴蝶效应失效或偏移。",
            "逆袭结果必须由当前行动造成，不能只靠前世记忆宣布成功。",
        ],
        ledger_rules=["年月日与年龄", "前世/今生时间线", "前世信息边界", "蝴蝶效应", "家庭关系", "资本积累"],
        soft_metrics={
            "chapter_chars_target": [1900, 2800],
            "paragraph_chars_target": [30, 65],
            "short_paragraph_ratio_target": [0.25, 0.50],
            "sentence_chars_target_max": 30,
            "long_paragraph_run_max": 2,
        },
        anti_patterns=["前世解释超过必要篇幅", "预知百分百准确", "逆袭无积累", "情感只靠旁白总结"],
        validator_targets=["continuity", "chapter_payoff", "deai_metrics"],
        report_refs=["深度质量包/quality-pack-重生逆袭.md", "知识库/kb-重生逆袭.md"],
    ),
    "science_fiction": _pack(
        "genre-science-fiction",
        "科幻末日",
        directive=[
            "资源稀缺、科技限制和人性选择共同驱动剧情；每次能力或科技升级要有代价。",
            "基地、进化和资源数量变化必须通过行动、取舍和后果落地。",
        ],
        hard_contracts=[
            "资源、科技和能力变化必须有来源、消耗或失败风险。",
            "升级不能绕过既定副作用、觉醒失败率或技术限制。",
        ],
        ledger_rules=["食物/水/药品/弹药", "基地设施", "进化等级与副作用", "科技等级", "幸存者关系"],
        soft_metrics={
            "chapter_chars_target": [2000, 3000],
            "paragraph_chars_target": [35, 80],
            "short_paragraph_ratio_target": [0.20, 0.45],
            "sentence_chars_target_max": 32,
            "long_paragraph_run_max": 2,
        },
        anti_patterns=["资源凭空刷新", "科技无代价", "设定讲解替代危机", "只写战斗不写生存"],
        validator_targets=["continuity", "chapter_payoff", "deai_metrics"],
        report_refs=["知识库/kb-科幻末日.md"],
    ),
    "game": _pack(
        "genre-game",
        "游戏电竞",
        directive=[
            "数值、装备和技能必须改变战术选择；比赛或副本要写出可理解的风险、判断和结果。",
            "成长通过装备、技能、排名或团队关系的可见变化体现，不只堆面板数字。",
        ],
        hard_contracts=[
            "等级、装备、技能和副本规则必须与本书游戏账本一致。",
            "关键胜利必须有战术、配合或规则依据，不能只用数值播报带过。",
        ],
        ledger_rules=["等级/属性", "技能冷却与限制", "装备品质", "副本规则", "排名/赛程", "战队关系"],
        soft_metrics={
            "chapter_chars_target": [2000, 3000],
            "paragraph_chars_target": [35, 80],
            "short_paragraph_ratio_target": [0.20, 0.45],
            "sentence_chars_target_max": 32,
            "long_paragraph_run_max": 2,
        },
        anti_patterns=["面板替代比赛", "数值无来源", "技能无冷却", "比赛结果无战术过程"],
        validator_targets=["continuity", "chapter_payoff", "deai_metrics"],
        report_refs=["知识库/kb-游戏电竞.md"],
    ),
    "fengshen": _pack(
        "genre-fengshen",
        "洪荒封神",
        directive=[
            "量劫、因果、法宝和阵营关系要通过事件逐步显露，不能把神话名词当作万能解释。",
            "死亡、复活、圣人能力和时间线必须服从本书既定世界观，关键因果要闭环。",
        ],
        hard_contracts=[
            "封神世界的境界、法宝、阵营和时间线必须服从本书世界观账本。",
            "已确认死亡的角色不得无因复活，圣人不得被写成全知全能。",
        ],
        ledger_rules=["洪荒时间线", "量劫征兆", "法宝归属", "阵营关系", "生死状态", "因果线"],
        soft_metrics={
            "chapter_chars_target": [2000, 3000],
            "paragraph_chars_target": [35, 80],
            "short_paragraph_ratio_target": [0.20, 0.45],
            "sentence_chars_target_max": 32,
            "long_paragraph_run_max": 2,
        },
        anti_patterns=["后世修真概念混入", "量劫无前兆", "角色无因复活", "圣人全知全能"],
        validator_targets=["world_constraint", "continuity", "chapter_payoff"],
        report_refs=["知识库/kb-洪荒封神.md"],
    ),
}


_SUBGENRE_PACKS = {
    "urban_system": "urban",
    "urban_rebirth": "rebirth",
    "xuanhuan_system": "xuanhuan",
}


_PLATFORM_PACKS: dict[str, dict[str, Any]] = {
    "fanqie": {
        "label": "番茄快节奏软基线",
        "directive": "移动端优先：尽快进入具体冲突，章末落到威胁、疑问或可见的新压力；不按固定字数硬塞爽点。",
        "soft_metrics": {
            "chapter_chars_target": [1800, 2700],
            "paragraph_chars_target": [30, 70],
            "short_paragraph_ratio_target": [0.25, 0.50],
        },
        "report_ref": "深度质量包/quality-pack-platform-番茄.md",
    },
    "qidian": {
        "label": "起点长线软基线",
        "directive": "长线沉浸优先：重要爽点先给依据、代价和余波，靠人物弧线与世界厚度追读；不把长段当硬目标。",
        "soft_metrics": {
            "chapter_chars_target": [2400, 3800],
            "paragraph_chars_target": [55, 110],
            "short_paragraph_ratio_target": [0.10, 0.30],
        },
        "report_ref": "深度质量包/quality-pack-platform-起点.md",
    },
}

_PLATFORM_ALIASES = {
    "番茄": "fanqie",
    "番茄小说": "fanqie",
    "fanqie": "fanqie",
    "起点": "qidian",
    "起点中文网": "qidian",
    "qidian": "qidian",
}

_GENRE_ALIASES = {
    "都市": "urban",
    "都市系统": "urban",
    "urban": "urban",
    "玄幻": "xuanhuan",
    "仙侠": "xuanhuan",
    "修仙": "xuanhuan",
    "xuanhuan": "xuanhuan",
    "悬疑": "suspense",
    "灵异": "suspense",
    "suspense": "suspense",
    "历史": "history",
    "历史穿越": "history",
    "history": "history",
    "科幻": "science_fiction",
    "末日": "science_fiction",
    "science_fiction": "science_fiction",
    "游戏": "game",
    "电竞": "game",
    "game": "game",
    "洪荒": "fengshen",
    "封神": "fengshen",
    "洪荒封神": "fengshen",
    "fengshen": "fengshen",
}


def _unique(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in result:
            result.append(item)
    return result


def _merge_metrics(genre_metrics: dict[str, Any], platform_metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "genre": deepcopy(genre_metrics),
        "platform": deepcopy(platform_metrics),
    }


def select_report_pack(platform: Any = "fanqie", genre: Any = "urban", subgenre: Any = "") -> dict[str, Any]:
    platform_raw = str(platform or "fanqie").strip().lower()
    genre_raw = str(genre or "urban").strip().lower()
    platform_key = _PLATFORM_ALIASES.get(platform_raw, platform_raw)
    genre_key = _GENRE_ALIASES.get(genre_raw, genre_raw)
    subgenre_key = str(subgenre or "").strip().lower()
    if "重生" in subgenre_key or subgenre_key in {"urban_rebirth", "rebirth"}:
        subgenre_key = "urban_rebirth"
    elif "系统" in subgenre_key or subgenre_key in {"urban_system", "xuanhuan_system"}:
        subgenre_key = "urban_system" if genre_key == "urban" else "xuanhuan_system"
    pack_key = _SUBGENRE_PACKS.get(subgenre_key, genre_key)
    genre_pack = deepcopy(_GENRE_PACKS.get(pack_key) or _GENRE_PACKS["urban"])
    platform_pack = deepcopy(_PLATFORM_PACKS.get(platform_key) or _PLATFORM_PACKS["fanqie"])
    genre_pack["pack_id"] = f"{genre_pack['pack_id']}:{platform_key}"
    genre_pack["platform"] = platform_key
    genre_pack["scope"] = {
        "platform": platform_key,
        "genre": genre_key,
        "subgenre": subgenre_key,
        "selected_genre_pack": pack_key,
    }
    genre_pack["directive"] = _unique(list(genre_pack.get("directive") or []) + [str(platform_pack.get("directive") or "")])
    genre_pack["soft_metrics"] = _merge_metrics(genre_pack.get("soft_metrics") or {}, platform_pack.get("soft_metrics") or {})
    genre_pack["report_refs"] = _unique(list(genre_pack.get("report_refs") or []) + [str(platform_pack.get("report_ref") or "")])
    return genre_pack


def render_report_directive(report_pack: dict[str, Any] | None) -> str:
    if not isinstance(report_pack, dict):
        return ""
    hard_contracts = [str(item) for item in report_pack.get("hard_contracts") or [] if str(item).strip()]
    ledgers = [str(item) for item in report_pack.get("ledger_rules") or [] if str(item).strip()]
    anti_patterns = [str(item) for item in report_pack.get("anti_patterns") or [] if str(item).strip()]
    directives = [str(item) for item in report_pack.get("directive") or [] if str(item).strip()]
    lines = [f"报告蒸馏规则（{report_pack.get('label') or '当前品类'}，只约束当前品类，不覆盖本书事实账本）："]
    if directives:
        lines.append("执行：" + "；".join(directives[:3]))
    if hard_contracts:
        lines.append("契约：" + "；".join(hard_contracts[:3]))
    if ledgers:
        lines.append("账本：" + "、".join(ledgers[:8]))
    if anti_patterns:
        lines.append("避免：" + "；".join(anti_patterns[:4]))
    lines.append("报告统计仅作软基线，原文样本、标题样本和网站噪声不得复用。")
    return "\n".join(lines)[:1800]


def report_pack_metadata(report_pack: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(report_pack, dict):
        return {}
    return {
        "schema_version": report_pack.get("schema_version", REPORT_RULES_SCHEMA_VERSION),
        "pack_id": report_pack.get("pack_id"),
        "label": report_pack.get("label"),
        "scope": deepcopy(report_pack.get("scope") or {}),
        "hard_contracts": list(report_pack.get("hard_contracts") or []),
        "ledger_rules": list(report_pack.get("ledger_rules") or []),
        "soft_metrics": deepcopy(report_pack.get("soft_metrics") or {}),
        "validator_targets": list(report_pack.get("validator_targets") or []),
        "report_refs": list(report_pack.get("report_refs") or []),
        "source_id": report_pack.get("source_id", REPORT_SOURCE_ID),
        "source_metadata": deepcopy(REPORT_SOURCE_METADATA),
        "hard_gate": False,
    }


def _empty_metrics() -> dict[str, Any]:
    return {
        "schema_version": "report-metrics-v1",
        "enabled": False,
        "soft_only": True,
        "chapter_chars": 0,
        "paragraph_count": 0,
        "paragraph_chars_mean": 0.0,
        "paragraph_chars_median": 0.0,
        "short_paragraph_ratio": 0.0,
        "long_paragraph_run_max": 0,
        "sentence_chars_mean": 0.0,
        "sensory_anchor_per_500_chars": 0.0,
        "warnings": [],
    }


def analyze_report_metrics(text: str, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Measure report-style observations without making them a hard gate."""
    report_pack = (profile or {}).get("report_pack") if isinstance(profile, dict) else None
    if not isinstance(report_pack, dict):
        return _empty_metrics()
    compact = re.sub(r"\s+", "", str(text or ""))
    if not compact:
        return _empty_metrics()
    paragraphs = [item.strip() for item in re.split(r"\n{2,}|\n", str(text)) if item.strip()]
    paragraph_lengths = [len(re.sub(r"\s+", "", item)) for item in paragraphs]
    sentences = [item for item in re.split(r"[。！？!?\n]", str(text)) if item.strip()]
    sentence_lengths = [len(re.sub(r"\s+", "", item)) for item in sentences]
    short_count = sum(1 for size in paragraph_lengths if size <= 30)
    long_run = 0
    current_run = 0
    for size in paragraph_lengths:
        if size > 80:
            current_run += 1
            long_run = max(long_run, current_run)
        else:
            current_run = 0
    sensory_terms = "看听闻嗅触摸抓握冰冷滚烫血腥气味声音脚步目光"
    sensory_hits = sum(compact.count(term) for term in sensory_terms)
    metrics = {
        "schema_version": "report-metrics-v1",
        "enabled": True,
        "soft_only": True,
        "pack_id": report_pack.get("pack_id"),
        "chapter_chars": len(compact),
        "paragraph_count": len(paragraphs),
        "paragraph_chars_mean": round(mean(paragraph_lengths), 2) if paragraph_lengths else 0.0,
        "paragraph_chars_median": round(float(median(paragraph_lengths)), 2) if paragraph_lengths else 0.0,
        "short_paragraph_ratio": round(short_count / max(1, len(paragraph_lengths)), 4),
        "long_paragraph_run_max": long_run,
        "sentence_chars_mean": round(mean(sentence_lengths), 2) if sentence_lengths else 0.0,
        "sensory_anchor_per_500_chars": round(sensory_hits / max(1, len(compact)) * 500, 3),
        "warnings": [],
    }
    targets = (report_pack.get("soft_metrics") or {}).get("genre") or {}
    platform_targets = (report_pack.get("soft_metrics") or {}).get("platform") or {}
    for name, value, target in (
        ("paragraph_chars_median", metrics["paragraph_chars_median"], targets.get("paragraph_chars_target")),
        ("short_paragraph_ratio", metrics["short_paragraph_ratio"], targets.get("short_paragraph_ratio_target")),
    ):
        if isinstance(target, list) and len(target) == 2 and not (float(target[0]) <= value <= float(target[1])):
            metrics["warnings"].append({"code": f"{name}_outside_genre_baseline", "value": value, "target": target, "severity": "low"})
    if metrics["long_paragraph_run_max"] > int(targets.get("long_paragraph_run_max") or 2):
        metrics["warnings"].append({
            "code": "long_paragraph_run",
            "value": metrics["long_paragraph_run_max"],
            "target": targets.get("long_paragraph_run_max") or 2,
            "severity": "low",
        })
    if isinstance(platform_targets.get("chapter_chars_target"), list):
        low, high = platform_targets["chapter_chars_target"]
        if not (float(low) <= metrics["chapter_chars"] <= float(high)):
            metrics["warnings"].append({
                "code": "chapter_chars_outside_platform_baseline",
                "value": metrics["chapter_chars"],
                "target": platform_targets["chapter_chars_target"],
                "severity": "low",
            })
    return metrics


def empty_report_metrics() -> dict[str, Any]:
    return _empty_metrics()
