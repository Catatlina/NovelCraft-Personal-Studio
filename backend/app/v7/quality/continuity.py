"""Deterministic cross-chapter continuity checks.

The LLM may propose facts, but chapter hand-off structure is checked by the
application before a result can be marked as publishable.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


_STATE_CATEGORIES = {
    "character_updates": "characters",
    "world_facts": "world",
    "plot_events": "causal_events",
    "foreshadowing": "foreshadowing",
    "timeline": "timeline",
    "resources": "resources",
    "resource_updates": "resources",
    "relationship_updates": "relationships",
}


def build_state_delta(memory_items: list[dict[str, Any]] | None) -> dict[str, list[dict[str, Any]]]:
    """Group extracted memory items into durable transition domains."""
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in memory_items or []:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "unknown")
        target = _STATE_CATEGORIES.get(category, "facts")
        key = str(item.get("key") or item.get("name") or "").strip()
        summary = str(item.get("summary") or item.get("description") or "").strip()
        if not key and not summary:
            continue
        grouped[target].append(
            {
                "key": key,
                "summary": summary,
                "category": category,
                "confidence": item.get("confidence"),
            }
        )
    return dict(grouped)


def validate_transition_contract(
    contract: dict[str, Any] | None,
    *,
    chapter_number: int,
    previous_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate the durable hand-off between adjacent chapters."""
    contract = contract or {}
    previous_contract = previous_contract or {}
    issues: list[dict[str, Any]] = []

    def issue(code: str, severity: str, message: str) -> None:
        issues.append({"code": code, "severity": severity, "message": message})

    if contract.get("schema_version") not in {"v1", "v2"}:
        issue("schema_version_missing", "high", "转场契约缺少受支持的 schema_version")

    if int(contract.get("chapter_number") or 0) != chapter_number:
        issue("chapter_number_mismatch", "high", "转场契约章节号与当前章节不一致")

    if chapter_number > 1:
        previous_number = int(previous_contract.get("chapter_number") or 0)
        if not previous_contract:
            issue("previous_contract_missing", "high", "非首章没有读取到上一章转场契约")
        elif previous_number != chapter_number - 1:
            issue(
                "previous_chapter_mismatch",
                "high",
                f"当前第{chapter_number}章承接的不是第{chapter_number - 1}章",
            )

    start_state = contract.get("start_state") or {}
    if chapter_number > 1 and not start_state.get("previous_transition_contract"):
        issue("start_state_missing", "high", "当前章没有保存上一章交接状态")

    end_state = contract.get("end_state") or {}
    if not str(end_state.get("last_tail") or "").strip():
        issue("end_tail_missing", "high", "当前章没有可供下一章承接的结尾文本")
    if not str(end_state.get("summary") or "").strip():
        issue("summary_missing", "medium", "当前章缺少结构化摘要")
    if not str(contract.get("next_chapter_bridge") or "").strip():
        issue("next_bridge_missing", "high", "当前章没有下一章入口桥接")

    if not isinstance(contract.get("state_delta"), dict):
        issue("state_delta_missing", "high", "当前章没有记录结构化状态变化")
    if not isinstance(contract.get("open_threads"), list):
        issue("open_threads_invalid", "medium", "未解决情节线不是列表")

    blocking = [item for item in issues if item["severity"] == "high"]
    return {
        "schema_version": "continuity-v1",
        "chapter_number": chapter_number,
        "passed": not blocking,
        "blocking_count": len(blocking),
        "issues": issues,
        "checked": [
            "chapter_number",
            "previous_contract",
            "start_state",
            "end_state",
            "next_chapter_bridge",
            "state_delta",
            "open_threads",
        ],
    }
