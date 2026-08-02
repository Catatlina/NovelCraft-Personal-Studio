"""The internal 33-dimension novel audit contract.

The product still exposes the existing seven macro scores.  These smaller
checks are evidence fields used by the reviewer and repair router; they are
not 33 separate agents and they do not all block a chapter by themselves.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class AuditDimension:
    key: str
    group: str
    label: str
    description: str
    hard_gate: bool = False


AUDIT_DIMENSIONS: tuple[AuditDimension, ...] = (
    # Plot and causal movement (9)
    AuditDimension("chapter_goal", "plot", "章节目标", "本章是否完成了明确的叙事任务"),
    AuditDimension("conflict", "plot", "核心冲突", "冲突是否具体、持续并逼迫角色行动", True),
    AuditDimension("causality", "plot", "因果链", "触发、选择、阻碍、代价与结果是否相连", True),
    AuditDimension("logic_exposition", "plot", "逻辑说明", "必要信息是否以可理解的方式给出，是否存在解释断层", True),
    AuditDimension("choice_consequence", "plot", "选择与后果", "角色选择是否带来可见后果，而不是剧情自动推进"),
    AuditDimension("stakes", "plot", "风险与代价", "读者能否感知失败成本和局势升级"),
    AuditDimension("plot_progress", "plot", "情节推进", "本章是否改变了故事状态，而非原地重复"),
    AuditDimension("arc_progress", "plot", "故事弧推进", "本章对当前故事弧是否有有效推进"),
    AuditDimension("ending_hook", "plot", "章末钩子", "结尾是否落到具体动作、发现、决定或新问题"),
    # Character (8)
    AuditDimension("personality_consistency", "character", "性格一致", "行为是否符合已建立的性格"),
    AuditDimension("motivation_consistency", "character", "动机一致", "人物行动是否有可信动机"),
    AuditDimension("knowledge_boundary", "character", "认知边界", "人物是否知道不该知道的信息", True),
    AuditDimension("capability_consistency", "character", "能力一致", "能力、经验和限制是否前后一致", True),
    AuditDimension("character_voice", "character", "人物声音", "对白和叙述是否有稳定的人物口吻"),
    AuditDimension("relationship_change", "character", "关系变化", "人物关系是否发生了可追踪的变化"),
    AuditDimension("character_arc_progress", "character", "人物弧推进", "人物是否经历了新的选择或心理变化"),
    AuditDimension("behavior_credibility", "character", "行为可信", "行为是否受到情境、情绪和利益约束"),
    # World and continuity facts (8)
    AuditDimension("world_rules", "world", "世界规则", "世界观硬规则是否被遵守", True),
    AuditDimension("timeline", "world", "时间线", "时间顺序、时长和同时性是否成立", True),
    AuditDimension("space_location", "world", "空间位置", "人物、物品和行动地点是否连续", True),
    AuditDimension("resource_ledger", "world", "资源账本", "金钱、物品、伤势和消耗是否有来源与去向", True),
    AuditDimension("ability_system", "world", "能力体系", "能力边界、代价和可用条件是否稳定", True),
    AuditDimension("terminology", "world", "术语一致", "人物名、地名、称谓和专有名词是否统一"),
    AuditDimension("information_boundary", "world", "信息边界", "叙事是否泄露角色或读者尚不应获得的信息", True),
    AuditDimension("foreshadowing_state", "world", "伏笔状态", "伏笔是否新增、推进、回收或保持可追踪"),
    # Reader experience (5)
    AuditDimension("opening_pull", "reader", "开篇牵引", "开头是否快速给出动作、异常或问题"),
    AuditDimension("expectation", "reader", "预期建立", "章节承诺是否清楚且值得等待"),
    AuditDimension("payoff", "reader", "阶段兑现", "铺垫是否获得阶段性回应，而不是只吊胃口"),
    AuditDimension("emotion_shift", "reader", "情绪变化", "读者情绪是否发生了可感知的变化"),
    AuditDimension("continuation_intent", "reader", "追读意愿", "章末是否留下继续阅读的具体理由"),
    # Style / de-AI risk (3)
    AuditDimension("sentence_rhythm", "style", "句式节奏", "长短句、段落和信息密度是否过于整齐", False),
    AuditDimension("punctuation_anomaly", "style", "标点异常", "符号是否异常高密度或形成固定模板", False),
    AuditDimension("ai_pattern_risk", "style", "AI腔风险", "是否出现套话、解释腔、同构句和过度总结", False),
)

assert len(AUDIT_DIMENSIONS) == 33, "the internal audit contract must remain 33-dimensional"

AUDIT_DIMENSION_GROUPS: dict[str, tuple[str, ...]] = {
    group: tuple(item.key for item in AUDIT_DIMENSIONS if item.group == group)
    for group in ("plot", "character", "world", "reader", "style")
}


def _score(value: Any) -> int | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return max(0, min(100, int(round(float(value)))))


def _raw_items(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        if isinstance(raw.get("items"), dict):
            return raw["items"]
        return raw
    if isinstance(raw, list):
        result: dict[str, Any] = {}
        for item in raw:
            if isinstance(item, dict) and item.get("key"):
                result[str(item["key"])] = item
        return result
    return {}


def _projected_score(
    item: AuditDimension,
    macro_scores: dict[str, Any],
    reader_experience: dict[str, Any],
) -> int | None:
    """Return a transparent macro projection for old reviewer payloads."""
    def first(*values: Any) -> int | None:
        for value in values:
            score = _score(value)
            if score is not None:
                return score
        return None

    if item.group == "plot":
        return first(macro_scores.get("plot_logic"), macro_scores.get("pacing"))
    if item.group == "character":
        return first(macro_scores.get("character_voice"), macro_scores.get("consistency"))
    if item.group == "world":
        return first(macro_scores.get("consistency"), macro_scores.get("constraint_compliance"))
    reader_map = {
        "opening_pull": "expectation",
        "expectation": "expectation",
        "payoff": "payoff",
        "emotion_shift": "emotion_shift",
        "continuation_intent": "worth_continuing",
    }
    if item.group == "reader":
        return _score(reader_experience.get(reader_map[item.key]))
    return first(macro_scores.get("writing_quality"))


def normalize_audit_report(
    raw: Any,
    *,
    macro_scores: dict[str, Any] | None = None,
    reader_experience: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize provider output without hiding incomplete evidence.

    Older providers may only return the seven macro scores.  Their values are
    projected into the 33 slots with ``source=macro_projection``.  This keeps
    the runtime backward compatible while exposing ``complete=False`` so the
    product cannot mistake compatibility data for a true 33-item audit.
    """
    macro_scores = macro_scores or {}
    reader_experience = reader_experience or {}
    source_items = _raw_items(raw)
    items: dict[str, dict[str, Any]] = {}
    llm_scored = 0

    for definition in AUDIT_DIMENSIONS:
        supplied = source_items.get(definition.key)
        score = None
        evidence = ""
        repair = ""
        source = "macro_projection"
        if isinstance(supplied, dict):
            score = _score(supplied.get("score"))
            evidence = str(supplied.get("evidence") or supplied.get("description") or "").strip()
            repair = str(supplied.get("repair") or supplied.get("repair_action") or "").strip()
            if score is not None:
                source = "llm"
        else:
            score = _score(supplied)
            if score is not None:
                source = "llm"

        if source == "llm":
            llm_scored += 1
        if score is None:
            score = _projected_score(definition, macro_scores, reader_experience)
            status = "projected" if score is not None else "not_scored"
        else:
            status = "scored"

        items[definition.key] = {
            "key": definition.key,
            "group": definition.group,
            "label": definition.label,
            "score": score,
            "evidence": evidence,
            "repair": repair,
            "source": source,
            "status": status,
            "hard_gate": definition.hard_gate,
        }

    return {
        "schema_version": "33d-v1",
        "count": len(AUDIT_DIMENSIONS),
        "scored_count": sum(1 for item in items.values() if item["score"] is not None),
        "llm_scored_count": llm_scored,
        "coverage": round(llm_scored / len(AUDIT_DIMENSIONS), 3),
        "complete": llm_scored == len(AUDIT_DIMENSIONS),
        "source": "llm" if llm_scored == len(AUDIT_DIMENSIONS) else "macro_projection",
        "groups": {group: list(keys) for group, keys in AUDIT_DIMENSION_GROUPS.items()},
        "items": items,
    }


def format_audit_dimensions() -> str:
    """Render the contract for a reviewer prompt."""
    return "\n".join(
        f"- {item.key}（{item.group}）：{item.label}。{item.description}"
        for item in AUDIT_DIMENSIONS
    )
