"""Deterministic cross-chapter continuity checks.

The LLM may propose facts, but chapter hand-off structure is checked by the
application before a result can be marked as publishable.
"""
from __future__ import annotations

from collections import defaultdict
import re
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


def _compact_text(value: Any) -> str:
    """Keep a stable comparison form for prose hand-off evidence."""
    return re.sub(r"[^0-9a-zA-Z\u3400-\u9fff]+", "", str(value or "")).lower()


def _title_base(value: Any) -> str:
    """Return the arc/base part of a chapter title."""
    title = str(value or "").lower()
    # Chapter headings often use ``书名·本章事件``.  The base is useful as a
    # signal, but it is never used without the opening-anchor check below.
    return _compact_text(re.split(r"[·•:：|｜/_-]", title, maxsplit=1)[0])


def _ngrams(value: Any, size: int = 2) -> set[str]:
    text = _compact_text(value)
    if len(text) < size:
        return {text} if text else set()
    return {text[index:index + size] for index in range(len(text) - size + 1)}


def _overlap_ratio(left: Any, right: Any) -> float:
    """Compare adjacent prose anchors without pretending paraphrase is exact."""
    left_grams = _ngrams(left)
    right_grams = _ngrams(right)
    if not left_grams or not right_grams:
        return 0.0
    return len(left_grams & right_grams) / max(1, min(len(left_grams), len(right_grams)))


def _contract_event_signatures(contract: dict[str, Any] | None) -> set[str]:
    contract = contract or {}
    signatures: set[str] = set()
    for event in contract.get("events") or []:
        if not isinstance(event, dict):
            continue
        key = _compact_text(event.get("key"))
        summary = _compact_text(event.get("summary"))
        if key:
            signatures.add(f"key:{key}")
        if summary:
            signatures.add(f"summary:{summary[:80]}")
    for group in (contract.get("state_delta") or {}).values():
        if not isinstance(group, list):
            continue
        for item in group:
            if not isinstance(item, dict):
                continue
            key = _compact_text(item.get("key"))
            summary = _compact_text(item.get("summary"))
            if key:
                signatures.add(f"key:{key}")
            if summary:
                signatures.add(f"summary:{summary[:80]}")
    return signatures


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
    state_conflicts: list[dict[str, Any]] | None = None,
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
        handoff = (
            start_state.get("previous_transition_contract")
            if isinstance(start_state, dict)
            else {}
        ) or {}
        if previous_contract and int(handoff.get("chapter_number") or 0) != previous_number:
            issue(
                "previous_transition_contract_mismatch",
                "high",
                "当前章保存的上一章契约与实际上一章契约不一致",
            )
        previous_tail = str((start_state or {}).get("previous_tail") or "").strip()
        previous_end_tail = str(
            (previous_contract.get("end_state") or {}).get("last_tail") or ""
        ).strip()
        if previous_tail and previous_end_tail and previous_tail != previous_end_tail:
            issue(
                "previous_tail_mismatch",
                "high",
                "当前章使用的上一章结尾与上一章已持久化结尾不一致",
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
    elif str(end_state.get("last_tail") or "").strip() and not str(
        end_state.get("last_tail")
    ).endswith(str(contract.get("next_chapter_bridge"))):
        issue("next_bridge_mismatch", "high", "下一章桥接文本不是当前章结尾的真实片段")

    if not isinstance(contract.get("state_delta"), dict):
        issue("state_delta_missing", "high", "当前章没有记录结构化状态变化")
    if not isinstance(contract.get("open_threads"), list):
        issue("open_threads_invalid", "medium", "未解决情节线不是列表")

    for conflict in state_conflicts or []:
        if not isinstance(conflict, dict):
            continue
        severity = str(conflict.get("severity") or "medium").lower()
        conflict_type = str(conflict.get("conflict_type") or "").lower()
        resolution_status = str(conflict.get("resolution_status") or "").lower()
        if (
            conflict_type in {"strategic_reveal", "plot_disruption"}
            and resolution_status == "resolved"
        ):
            # A resolved deception/reversal or an interrupted plan is story
            # movement. It remains visible in state_conflicts and event
            # evidence, but it must not be treated as a contradiction in the
            # durable hand-off.
            continue
        if severity == "high":
            issue(
                "state_conflict",
                "high",
                str(
                    conflict.get("description")
                    or conflict.get("message")
                    or f"故事状态冲突：{conflict.get('key') or '未命名'}"
                ),
            )

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


def validate_prose_continuity(
    *,
    chapter_number: int,
    current_text: str,
    current_title: str = "",
    previous_title: str = "",
    current_contract: dict[str, Any] | None = None,
    previous_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check semantic hand-off signals that a schema-only contract cannot see.

    This is deliberately conservative: an anchor mismatch alone is a warning
    because a writer can paraphrase a hand-off.  A repeated arc title combined
    with a missing opening anchor is a hard blocker because it is the exact
    signature of the parallel-version bug seen in blind review.
    """
    current_contract = current_contract or {}
    previous_contract = previous_contract or {}
    if chapter_number <= 1:
        return {
            "schema_version": "prose-continuity-v1",
            "passed": True,
            "status": "not_applicable",
            "blocking_count": 0,
            "issues": [],
            "evidence": {"chapter_number": chapter_number},
            "checked": ["chapter_number"],
        }

    issues: list[dict[str, Any]] = []

    def issue(code: str, severity: str, message: str) -> None:
        issues.append({"code": code, "severity": severity, "message": message})

    previous_end = previous_contract.get("end_state") or {}
    previous_anchor = str(
        previous_contract.get("next_chapter_bridge")
        or previous_end.get("last_tail")
        or ""
    )[-600:]
    current_opening = str(current_text or "")[:900]
    anchor_overlap = _overlap_ratio(previous_anchor, current_opening)
    current_base = _title_base(current_title)
    previous_base = _title_base(previous_title or previous_end.get("title"))
    same_base = bool(current_base and previous_base and current_base == previous_base)
    current_title_norm = _compact_text(current_title)
    previous_title_norm = _compact_text(previous_title or previous_end.get("title"))
    same_title = bool(current_title_norm and current_title_norm == previous_title_norm)
    shared_events = sorted(
        _contract_event_signatures(current_contract)
        & _contract_event_signatures(previous_contract)
    )

    # Identical/arc-repeated headings are not automatically wrong.  They are
    # blocking only when the new chapter does not visibly open from the prior
    # chapter's bridge.  This catches the report's ch10-ch14 parallel drafts
    # while allowing a genuine continuation to reuse an arc label.
    if (same_title or same_base) and anchor_overlap < 0.03:
        issue(
            "parallel_version_candidate",
            "high",
            "章节标题沿用上一章同一情节基名，但正文开头没有承接上一章结尾锚点，疑似平行版本或错接章节",
        )

    # Event/key reuse strengthens the finding and remains visible to the UI
    # even when a future title format does not expose a base name.
    if same_title and shared_events:
        issue(
            "repeated_transition_events",
            "high",
            "相邻章节标题相同且重复使用上一章事件键，疑似重复生成同一情节分支",
        )

    blocking = [item for item in issues if item["severity"] == "high"]
    return {
        "schema_version": "prose-continuity-v1",
        "passed": not blocking,
        "status": "continuous" if not blocking else "broken",
        "blocking_count": len(blocking),
        "issues": issues,
        "evidence": {
            "current_title": current_title,
            "previous_title": previous_title or previous_end.get("title") or "",
            "same_title": same_title,
            "same_title_base": same_base,
            "opening_anchor_overlap": round(anchor_overlap, 4),
            "shared_event_signatures": shared_events[:12],
        },
        "checked": [
            "previous_chapter_bridge",
            "current_opening_anchor",
            "title_reuse_signal",
            "transition_event_reuse",
        ],
    }
