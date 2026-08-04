"""Reader-facing chapter payoff contracts and evidence checks.

The contract is deliberately broader than "a fight every chapter".  A web
novel payoff can be a win, reveal, resource gain, relationship shift, escape or
rule exploit.  What matters is that the reader sees a choice, a consequence
and a new pressure, while the existing Novel Brain remains the only truth
store.
"""
from __future__ import annotations

import re
from typing import Any


PAYOFF_SCHEMA_VERSION = "chapter-payoff-contract-v1"
PAYOFF_TYPES = {
    "status_reversal", "money_or_resource", "information_advantage", "relationship_shift",
    "career_progress", "industry_breakthrough", "opponent_reaction", "breakthrough",
    "combat_advantage", "resource_gain", "reveal", "survival", "hidden_strength",
    "rule_exploit", "system_reward", "ability_discovery", "sacrifice", "faction_shift",
    "family_survival", "reversal", "other",
}

# Providers and outline prompts frequently return reader-facing Chinese labels
# instead of the canonical enum values above.  Treating every unfamiliar label
# as ``other`` makes a valid early-chapter payoff fail the hard contract (for
# example, ``身份反转`` was being downgraded to ``other``).  Keep the canonical
# enum as the storage contract, but normalize common genre/platform wording at
# the boundary.  This is an alias map, not a banned-word list: novel prose and
# punctuation remain unrestricted.
PAYOFF_TYPE_ALIASES = {
    "身份反转": "status_reversal",
    "地位反转": "status_reversal",
    "逆袭": "status_reversal",
    "打脸": "status_reversal",
    "身份逆转": "status_reversal",
    "权力确立": "status_reversal",
    "权威确立": "status_reversal",
    "正式掌权": "status_reversal",
    "职位反转": "status_reversal",
    "反转": "reversal",
    "财富增长": "money_or_resource",
    "金钱资源": "money_or_resource",
    "资源获取": "resource_gain",
    "资源获得": "resource_gain",
    "信息优势": "information_advantage",
    "信息揭示": "reveal",
    "真相揭示": "reveal",
    "揭示": "reveal",
    "关系变化": "relationship_shift",
    "关系转变": "relationship_shift",
    "事业进展": "career_progress",
    "职业进展": "career_progress",
    "行业突破": "industry_breakthrough",
    "突破": "breakthrough",
    "境界突破": "breakthrough",
    "战斗优势": "combat_advantage",
    "战力优势": "combat_advantage",
    "击退": "combat_advantage",
    "战胜": "combat_advantage",
    "生存": "survival",
    "逃生": "survival",
    "隐藏实力": "hidden_strength",
    "规则利用": "rule_exploit",
    "规则漏洞": "rule_exploit",
    "系统奖励": "system_reward",
    "能力发现": "ability_discovery",
    "牺牲": "sacrifice",
    "势力变化": "faction_shift",
    "家人存活": "family_survival",
    "能力展示": "status_reversal",
    "决策反馈": "status_reversal",
    "掌控力": "status_reversal",
    "权威建立": "status_reversal",
    "获得认可": "relationship_shift",
    "态度转变": "relationship_shift",
    "事业推进": "career_progress",
    "方案通过": "career_progress",
    "其他": "other",
}


def _text(value: Any, limit: int = 500) -> str:
    return str(value or "").strip()[:limit]


def _anchor_key(value: Any) -> str:
    """Compare evidence anchors without making punctuation a hard failure."""
    return re.sub(r"[\W_]+", "", str(value or ""), flags=re.UNICODE)


def _first(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _text(data.get(key))
        if value:
            return value
    return ""


def _normalize_payoff_type(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    if raw in PAYOFF_TYPES:
        return raw
    return PAYOFF_TYPE_ALIASES.get(raw, "other")


def _infer_payoff_type(data: dict[str, Any]) -> str:
    """Infer a canonical type from payoff evidence when the enum is ``other``.

    Providers sometimes put the useful reader-facing label in the promise or
    visible-result field and emit ``other`` in the enum field.  Inference is
    intentionally limited to explicit commercial-narrative signals; when no
    signal is present we keep ``other`` so a required contract still fails
    truthfully instead of inventing a payoff.
    """
    signal = " ".join(
        _text(data.get(key), 600)
        for key in (
            "reader_promise", "reader_expectation", "promise", "visible_result",
            "result", "outcome", "payoff", "witness_reaction", "reaction",
            "active_choice", "choice", "decision", "action",
        )
    )
    evidence = data.get("payoff_evidence")
    if isinstance(evidence, list):
        signal += " " + " ".join(
            " ".join(
                _text(item.get(key), 300)
                for key in ("type", "payoff_type", "result", "visible_result", "reaction")
            )
            for item in evidence
            if isinstance(item, dict)
        )
    if not signal:
        return ""
    if any(token in signal for token in (
        "身份反转", "地位反转", "逆袭", "打脸", "成为新老板", "当上老板",
        "正式掌权", "权力确立", "权威确立", "站稳脚跟", "解雇", "被保安带走",
        "员工重新评估", "掌权", "收购公司", "买下公司", "最大股东", "原CEO被解职",
        "新老板", "展现新老板", "完成交接", "宣布审计", "内部审计", "身份确立", "权威",
        "展现掌控力", "掌控局面", "控制局面", "会议通过", "通过提案", "提案通过",
        "董事会同意", "高管态度转变", "态度转变", "开始配合", "开始支持", "获得认可",
        "得到认可", "赢得认可", "立威", "威信", "接管公司", "接手公司", "掌舵",
        "获得授权", "同意试行", "试行改革", "占据主动",
    )):
        return "status_reversal"
    if any(token in signal for token in (
        "关系缓和", "建立信任", "成为盟友", "转为合作", "公开支持", "获得支持",
    )):
        return "relationship_shift"
    if any(token in signal for token in (
        "方案通过", "项目推进", "拿下项目", "签约成功", "合作达成", "客户同意",
        "获得授权", "负责人", "完成交接",
    )):
        return "career_progress"
    if any(token in signal for token in ("境界突破", "实力突破", "突破", "晋级", "升级")):
        return "breakthrough"
    if any(token in signal for token in ("资源获取", "资源获得", "获得资源", "拿到资源", "财富增长", "拿到钱")):
        return "resource_gain"
    if any(token in signal for token in (
        "真相揭示", "信息揭示", "揭开真相", "发现线索", "发现异常", "注意到",
        "看见", "看到", "听见", "得知", "线索", "证据", "秘密", "异常",
        "真相", "消息", "信息优势",
    )):
        return "reveal"
    if any(token in signal for token in ("关系变化", "关系转变", "获得认可", "收服")):
        return "relationship_shift"
    if any(token in signal for token in ("活下来", "逃出生天", "成功逃脱", "生存")):
        return "survival"
    if any(token in signal for token in ("规则利用", "利用规则", "规则漏洞")):
        return "rule_exploit"
    if any(token in signal for token in ("系统奖励", "获得奖励")):
        return "system_reward"
    if any(token in signal for token in ("隐藏实力", "暴露实力")):
        return "hidden_strength"
    return ""


def normalize_payoff_contract(value: Any, *, chapter_number: int | None = None) -> dict[str, Any]:
    """Normalize provider/outline aliases into one stable contract."""
    data = value if isinstance(value, dict) else {}
    raw_type = _first(data, "payoff_type", "type", "kind")
    payoff_type = _normalize_payoff_type(raw_type)
    if payoff_type in {"", "other"}:
        payoff_type = _infer_payoff_type(data) or payoff_type
    return {
        "schema_version": str(data.get("schema_version") or PAYOFF_SCHEMA_VERSION),
        "chapter_number": int(data.get("chapter_number") or chapter_number or 0),
        "reader_promise": _first(data, "reader_promise", "reader_expectation", "promise"),
        "pressure": _first(data, "pressure", "conflict", "tension_target", "stakes"),
        "active_choice": _first(data, "active_choice", "choice", "decision", "action"),
        "payoff_type": payoff_type,
        "visible_result": _first(data, "visible_result", "result", "outcome", "payoff"),
        "witness_reaction": _first(data, "witness_reaction", "reaction", "external_reaction"),
        "cost": _first(data, "cost", "cost_or_risk", "price", "consequence"),
        "next_pressure": _first(data, "next_pressure", "hook", "next_hook", "new_pressure"),
        "setup_refs": [
            _text(item, 240)
            for item in (data.get("setup_refs") or data.get("foreshadow_refs") or [])
            if _text(item, 240)
        ][:8],
        "text_anchor": _first(data, "text_anchor", "evidence_anchor", "anchor",),
        "level": _first(data, "level", "payoff_level") or "small",
        "source": _first(data, "source") or "chapter_plan",
    }


def build_payoff_contract(
    value: Any,
    *,
    chapter_number: int | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a contract from outline/plot fields without inventing facts."""
    data = value if isinstance(value, dict) else {}
    contract = normalize_payoff_contract(data, chapter_number=chapter_number)
    if not contract["payoff_type"]:
        genre = str((profile or {}).get("genre") or "")
        contract["payoff_type"] = "breakthrough" if genre == "xuanhuan" else "status_reversal"
    return contract


def validate_payoff_contract(
    value: Any,
    *,
    profile: dict[str, Any] | None = None,
    required: bool = False,
) -> dict[str, Any]:
    """Validate the minimum commercial-narrative contract.

    ``required=False`` is used for legacy V6 records.  New V7 generation passes
    ``required=True`` once a quality profile is attached, so old data remains
    readable while new chapters cannot silently omit the reader promise.
    """
    contract = normalize_payoff_contract(value)
    hard_fields = ("reader_promise", "pressure", "active_choice", "visible_result", "next_pressure")
    missing = [key for key in hard_fields if not contract.get(key)]
    soft_missing = [key for key in ("cost", "witness_reaction") if not contract.get(key)]
    policy = (profile or {}).get("payoff_policy") or {}
    raw_type = _first(
        value if isinstance(value, dict) else {},
        "payoff_type",
        "type",
        "kind",
    )
    explicit_other = raw_type.strip().lower() in {"other", "其他"}
    if required and int(contract.get("chapter_number") or 0) <= int(policy.get("early_chapters_need_payoff") or 0):
        # ``other`` is a real enum value, not a word ban. Accept it when the
        # provider explicitly selected it and the complete reader contract is
        # present. Missing/unknown labels still fail, while the inference path
        # above upgrades recognizable Chinese evidence.
        if contract.get("payoff_type") == "" or (
            contract.get("payoff_type") == "other" and not explicit_other
        ):
            missing.append("payoff_type")
    issues = [f"爽点契约缺少 {key}" for key in missing]
    warnings = [f"爽点契约建议补充 {key}" for key in soft_missing]
    return {
        "schema_version": PAYOFF_SCHEMA_VERSION,
        "passed": not missing if required else True,
        "required": required,
        "missing": missing,
        "warnings": warnings,
        "issues": issues,
        "contract": contract,
    }


def validate_payoff_evidence(
    text: str,
    evidence: Any,
    *,
    required: bool = False,
) -> dict[str, Any]:
    """Check reviewer-provided payoff evidence against the actual chapter."""
    items = evidence if isinstance(evidence, list) else []
    checked: list[dict[str, Any]] = []
    invalid: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            invalid.append(f"evidence[{index}] 不是对象")
            continue
        anchor = _text(item.get("anchor") or item.get("text_anchor"), 240)
        result = _text(item.get("result") or item.get("visible_result"), 300)
        exact_match = bool(anchor) and anchor in str(text or "")
        normalized_match = (
            not exact_match
            and len(_anchor_key(anchor)) >= 6
            and _anchor_key(anchor) in _anchor_key(text)
        )
        if not anchor or not (exact_match or normalized_match):
            invalid.append(f"evidence[{index}] 缺少正文中可定位的原文锚点")
            continue
        if not result:
            invalid.append(f"evidence[{index}] 缺少可见结果")
            continue
        checked.append({
            "type": _text(item.get("type") or item.get("payoff_type")) or "other",
            "anchor": anchor,
            "result": result,
            "match_mode": "exact" if exact_match else "punctuation_normalized",
        })
    # A provider may append a second illustrative evidence item whose anchor
    # is not verbatim, even though another item is exactly locatable.  Keep the
    # invalid items in the report for diagnosis, but require at least one real
    # anchor instead of rejecting an otherwise verifiable chapter wholesale.
    passed = bool(checked) if required else not invalid
    return {
        "schema_version": PAYOFF_SCHEMA_VERSION,
        "passed": passed,
        "required": required,
        "checked": checked,
        "invalid": invalid,
    }


def evaluate_payoff_schedule(
    chapters: list[dict[str, Any]] | None,
    *,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate consecutive low-payoff chapters without hard-coding char counts."""
    chapters = [item for item in (chapters or []) if isinstance(item, dict)]
    policy = (profile or {}).get("payoff_policy") or {}
    max_streak = max(1, int(policy.get("max_low_payoff_streak") or 2))
    streak = 0
    issues: list[str] = []
    for item in chapters:
        contract = normalize_payoff_contract(item.get("payoff_contract") or item)
        has_payoff = bool(contract.get("visible_result")) and contract.get("payoff_type") not in {""}
        streak = 0 if has_payoff else streak + 1
        if streak > max_streak:
            issues.append(f"第{contract.get('chapter_number') or '?'}章前后连续 {streak} 章缺少可见兑现")
    return {
        "schema_version": PAYOFF_SCHEMA_VERSION,
        "passed": not issues,
        "max_low_payoff_streak": max_streak,
        "issues": issues,
        "sampled": len(chapters),
    }
