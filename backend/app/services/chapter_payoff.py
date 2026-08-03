"""Reader-facing chapter payoff contracts and evidence checks.

The contract is deliberately broader than "a fight every chapter".  A web
novel payoff can be a win, reveal, resource gain, relationship shift, escape or
rule exploit.  What matters is that the reader sees a choice, a consequence
and a new pressure, while the existing Novel Brain remains the only truth
store.
"""
from __future__ import annotations

from typing import Any


PAYOFF_SCHEMA_VERSION = "chapter-payoff-contract-v1"
PAYOFF_TYPES = {
    "status_reversal", "money_or_resource", "information_advantage", "relationship_shift",
    "career_progress", "industry_breakthrough", "opponent_reaction", "breakthrough",
    "combat_advantage", "resource_gain", "reveal", "survival", "hidden_strength",
    "rule_exploit", "system_reward", "ability_discovery", "sacrifice", "faction_shift",
    "family_survival", "reversal", "other",
}


def _text(value: Any, limit: int = 500) -> str:
    return str(value or "").strip()[:limit]


def _first(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _text(data.get(key))
        if value:
            return value
    return ""


def normalize_payoff_contract(value: Any, *, chapter_number: int | None = None) -> dict[str, Any]:
    """Normalize provider/outline aliases into one stable contract."""
    data = value if isinstance(value, dict) else {}
    raw_type = _first(data, "payoff_type", "type", "kind")
    payoff_type = raw_type if raw_type in PAYOFF_TYPES else ("other" if raw_type else "")
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
    if required and int(contract.get("chapter_number") or 0) <= int(policy.get("early_chapters_need_payoff") or 0):
        if contract.get("payoff_type") in {"", "other"}:
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
        if not anchor or anchor not in str(text or ""):
            invalid.append(f"evidence[{index}] 缺少正文中可定位的原文锚点")
            continue
        if not result:
            invalid.append(f"evidence[{index}] 缺少可见结果")
            continue
        checked.append({"type": _text(item.get("type") or item.get("payoff_type")) or "other", "anchor": anchor, "result": result})
    passed = bool(checked) and not invalid if required else not invalid
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
        has_payoff = bool(contract.get("visible_result")) and contract.get("payoff_type") not in {"", "other"}
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
