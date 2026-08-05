"""Versioned failure-pattern catalog for the V7 writing chain.

Quality packages describe desired writing behavior.  Review reports describe
observed failures.  This module keeps the latter as bounded, auditable data:
the generation chain can consume only the short preventive instruction while
the full card remains available to audits and regression tests.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


FAILURE_PATTERN_SCHEMA_VERSION = "failure-pattern-catalog-v1"


def _confidence(
    *,
    report_count: int,
    cross_model: bool,
    human_confirmed: bool,
    program_detectable: bool,
    cross_genre: bool,
    repair_verified: bool,
    side_effects: str = "low",
) -> float:
    """Calculate confidence from evidence, not from a subjective label.

    The score is used for rollout/metadata.  P0 correctness gates still rely
    on their deterministic validators, so confidence can never weaken them.
    """
    score = min(max(report_count, 0), 5) / 5 * 0.25
    score += 0.18 if cross_model else 0.0
    score += 0.18 if human_confirmed else 0.0
    score += 0.18 if program_detectable else 0.0
    score += 0.12 if cross_genre else 0.0
    score += 0.07 if repair_verified else 0.0
    score += 0.02 if side_effects == "low" else 0.0
    return round(min(score, 1.0), 3)


def _card(
    pattern_id: str,
    name: str,
    severity: str,
    applies_to: list[str],
    constraint: str,
    metric: str,
    repair: str,
    sources: list[str],
    *,
    report_count: int,
    cross_model: bool = True,
    human_confirmed: bool = True,
    program_detectable: bool = True,
    cross_genre: bool = False,
    repair_verified: bool = False,
    side_effects: str = "low",
) -> dict[str, Any]:
    evidence = {
        "report_count": report_count,
        "cross_model": cross_model,
        "human_confirmed": human_confirmed,
        "program_detectable": program_detectable,
        "cross_genre": cross_genre,
        "repair_verified": repair_verified,
        "side_effects": side_effects,
    }
    return {
        "schema_version": FAILURE_PATTERN_SCHEMA_VERSION,
        "id": pattern_id,
        "name": name,
        "severity": severity,
        "applies_to": applies_to,
        "pre_generation_constraint": constraint,
        "audit_metric": metric,
        "repair_strategy": repair,
        "regression_samples": [],
        "sources": sources,
        "evidence": evidence,
        "confidence": _confidence(**evidence),
    }


FAILURE_PATTERNS: tuple[dict[str, Any], ...] = (
    _card(
        "F01", "段落重复", "P0", ["all"],
        "同一段落只输出一次；续写必须从上一段之后继续，不得复制已完成内容。",
        "完整段落指纹重复率必须为 0；相邻重复段落必须为 0。",
        "A类局部去重；无法确认安全时丢弃候选并回到上一版。",
        ["review.paragraph-duplication", "longrun.mirror-chapter"],
        report_count=5, cross_genre=True, repair_verified=True,
    ),
    _card(
        "F02", "章节镜像", "P0", ["all"],
        "本章必须新增事件、选择或后果，不得复述上一章或把同一章拼接两次。",
        "章节归一化指纹相似度不得达到镜像阈值；新增事件覆盖率必须大于 0。",
        "C类重规划；保留事实和契约，重新生成缺失的事件链。",
        ["review.chapter-mirror", "longrun.mirror-chapter"],
        report_count=3, cross_genre=True, repair_verified=False,
    ),
    _card(
        "F03", "第一人称叙述泄漏", "P0", ["all"],
        "叙述统一使用第三人称限知；第一人称只允许出现在对白、短信或原文引用中。",
        "叙述区第一人称命中数必须为 0。",
        "A类定点改写；无法判断叙述/对白边界时阻断并要求重生成。",
        ["review.first-person-leakage", "product.third-person-contract"],
        report_count=4, cross_genre=True, repair_verified=True,
    ),
    _card(
        "F04", "AI味标点异常", "P1", ["all"],
        "标点按语境使用；只避免整章高密度、连续重复或模板化堆叠，不禁用单个符号。",
        "破折号、省略号及连续同符号按整章异常密度和连续序列审计。",
        "A类局部调整；保护对白、爽点爆发和章末钩子。",
        ["review.ai-punctuation", "deai.metrics"],
        report_count=4, cross_genre=True, repair_verified=True,
    ),
    _card(
        "F05", "爽点不足", "P1", ["fanqie", "payoff"],
        "生成前明确读者期待、主角行动、可见结果和下一压力；不以‘旁白宣布很爽’替代结果。",
        "期待兑现、主角主动性、结果可见性和反馈有效性均有证据。",
        "C类重规划或局部补写；先补行动链，不直接堆感叹词。",
        ["review.payoff-flat", "distilled.fanqie-payoff"],
        report_count=5, program_detectable=False, repair_verified=False,
    ),
    _card(
        "F06", "章节水化", "P1", ["all"],
        "每个场景完成目标、阻碍、选择、结果中的至少一轮；不要为了字数重复解释。",
        "章节状态变化、有效事件和新压力必须存在；长度不是质量证明。",
        "C类重排节拍；删除重复说明后补充具体动作或后果。",
        ["review.pacing-flat", "review.filler"],
        report_count=4, program_detectable=False, repair_verified=False,
    ),
    _card(
        "F07", "跨章连续性断裂", "P1", ["all", "continuity"],
        "本章开头承接上一章的时间、地点、人物状态和未决压力；跳转必须有过渡。",
        "transition contract、时间线、人物状态和首段承接证据必须完整。",
        "B类依据 Novel Brain 真相状态定点修复；无法确定归属时标记待审。",
        ["review.continuity-gap", "review.cross-chapter"],
        report_count=5, program_detectable=True, cross_genre=True, repair_verified=True,
    ),
    _card(
        "F08", "数字/时间线/资源错误", "P0", ["all"],
        "新数字、时间、资源和能力必须有来源、消耗或后果，不得凭空改变账本。",
        "真相文件与章节正文的数值、时间、资源变化必须可回放。",
        "B类查账本定点修复；账本冲突未解决时不得标记完成。",
        ["review.number-ledger", "review.timeline-drift"],
        report_count=4, program_detectable=True, cross_genre=True, repair_verified=False,
    ),
    _card(
        "F09", "简介复制灵感", "P1", ["packaging"],
        "简介必须说明人物、核心冲突、能力/机会和追读悬念，不得原样复述灵感笔记。",
        "简介与灵感的相似度只能保留事实核心，不能保留笔记结构、批注和方案清单。",
        "A类重新生成简介；正文事实和书名不变。",
        ["review.synopsis-is-inspiration", "product.synopsis-feedback"],
        report_count=3, program_detectable=True, repair_verified=False,
    ),
    _card(
        "F10", "审核分数口径不一致", "P0", ["audit"],
        "所有评分必须来自同一 V7 审计契约，并记录模型、Prompt 版本、来源和时间。",
        "同一输入的评分来源、维度和证据快照必须一致或明确标注不同审计轮次。",
        "停止发布状态，重新跑统一 V7 审计，不用一个分数覆盖另一个分数。",
        ["review.ai-vs-realtime-score", "product.audit-evidence"],
        report_count=4, program_detectable=True, cross_genre=True, repair_verified=False,
    ),
    _card(
        "F11", "审计空数据", "P0", ["audit"],
        "没有真实证据就显示‘未检查/数据不足’，不得显示已完成或虚构分数。",
        "连续性、33维、时间线、人物弧线必须有对应返回字段和证据数量。",
        "状态回退为未检查或失败；补齐 V7 数据链路后重审。",
        ["product.audit-empty-data", "review.audit-evidence"],
        report_count=4, program_detectable=True, cross_genre=True, repair_verified=False,
    ),
    _card(
        "F12", "生成失败状态错误", "P0", ["runtime"],
        "Provider、审计或写回失败时不得进入已完成/已入库状态；状态必须保留真实错误。",
        "任务状态与正文、审计、写回证据一致；失败不能有成功完成时间。",
        "终态状态机回退为 failed/needs_review，支持安全重试，不伪造成功。",
        ["review.generation-failure-state", "product.runtime-smoke"],
        report_count=4, program_detectable=True, cross_genre=True, repair_verified=True,
    ),
)


def list_failure_patterns(*, severity: str | None = None) -> list[dict[str, Any]]:
    items = [deepcopy(item) for item in FAILURE_PATTERNS]
    if severity:
        items = [item for item in items if item["severity"] == severity]
    return items


def get_failure_pattern(pattern_id: str) -> dict[str, Any] | None:
    for item in FAILURE_PATTERNS:
        if item["id"] == str(pattern_id or "").strip():
            return deepcopy(item)
    return None


def failure_pattern_metadata(*, pattern_ids: list[str] | None = None) -> dict[str, Any]:
    selected = list_failure_patterns()
    if pattern_ids:
        wanted = set(pattern_ids)
        selected = [item for item in selected if item["id"] in wanted]
    return {
        "schema_version": FAILURE_PATTERN_SCHEMA_VERSION,
        "count": len(selected),
        "patterns": [
            {
                "id": item["id"],
                "severity": item["severity"],
                "confidence": item["confidence"],
                "sources": item["sources"],
            }
            for item in selected
        ],
    }


def generation_constraints(
    *,
    profile: dict[str, Any] | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Return bounded preventive rules applicable to one generation.

    Correctness patterns are always included.  Style/payoff patterns are
    included only when the selected profile explicitly supports them.
    """
    profile = profile if isinstance(profile, dict) else {}
    platform = str(profile.get("platform") or "")
    strategy = str((profile.get("payoff_strategy") or {}).get("strategy_id") or "")
    allowed = {"all", platform, "runtime", "continuity"}
    if strategy:
        allowed.add("payoff")
    result: list[dict[str, Any]] = []
    for item in FAILURE_PATTERNS:
        applies = set(item.get("applies_to") or [])
        if not (applies & allowed):
            continue
        if item["severity"] == "P0" or item["id"] in {"F04", "F05", "F06", "F07"}:
            result.append({
                "id": item["id"],
                "severity": item["severity"],
                "constraint": item["pre_generation_constraint"],
                "confidence": item["confidence"],
            })
        if len(result) >= max(1, limit):
            break
    return result
