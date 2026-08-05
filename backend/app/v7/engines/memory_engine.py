"""Memory Engine - Sprint 2.

Real AI extraction of story memory from generated chapters, written back into
the Novel Brain through the confidence gate (>=0.7 apply, 0.5-0.7 pending
review, <0.5 discarded). Every write produces a v7_state_changes row.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from .base import BaseEngine, EngineCapability, EngineResult
from ..generation.generation_engine import AIGateway, AIGatewayError, chinese_word_count

# AI-extracted memory is never fully trusted; cap it below the hard threshold
# used for human-confirmed facts.
MAX_AI_CONFIDENCE = 0.95

CATEGORY_TO_STATE_TYPE: dict[str, str] = {
    "character_updates": "character",
    "world_facts": "world",
    "plot_events": "plot",
    "foreshadowing": "plot",
}

_STRATEGIC_REVEAL_MARKERS = (
    "表面",
    "实际上",
    "实际",
    "假意",
    "故意",
    "利用",
    "诱导",
    "另有打算",
    "并非",
    "借此",
    "现揭示",
    "已揭示",
    "揭示为",
    "原来是",
    "真相是",
    "同一人",
    "一字之差",
)

_PLOT_DISRUPTION_PLAN_MARKERS = (
    "计划",
    "打算",
    "原定",
    "准备",
)
_PLOT_DISRUPTION_EVENT_MARKERS = (
    "受挫",
    "落空",
    "被迫",
    "打断",
    "提前",
    "意外",
    "未能",
    "失败",
    "挑战",
    "来袭",
    "阻止",
    "改线",
)
_PLOT_PRESSURE_ACTION_MARKERS = (
    "离开",
    "离宗",
    "启程",
    "出发",
    "决定",
    "选择",
    "寻找",
    "守护",
    "带走",
    "放弃",
)
_PLOT_PRESSURE_CONSEQUENCE_MARKERS = (
    "可能",
    "更快",
    "时间紧迫",
    "时限",
    "期限",
    "将启",
    "即将",
    "会裂",
    "会失控",
    "危机",
    "威胁",
    "风险",
    "后果",
    "代价",
)
_RESOURCE_COST_MARKERS = (
    "寿元",
    "寿命",
    "余量",
    "仅剩",
    "只剩",
    "削减",
    "减少",
    "损失",
    "消耗",
    "付出",
    "代价",
    "资源",
)
_RESOURCE_PRESSURE_MARKERS = (
    "目标",
    "长期",
    "生存",
    "活下去",
    "不足",
    "有限",
    "威胁",
    "风险",
    "压力",
    "危机",
    "困境",
    "冲突",
)
_RULE_EVOLUTION_MARKERS = (
    "因果偏移",
    "因果承受上限",
    "模拟器警告",
    "未来模拟",
    "不可预测",
    "严重偏离",
    "规则变化",
    "规则改变",
    "收益超出",
)
_HARD_CONFLICT_MARKERS = (
    "凭空",
    "再次出现",
    "已经消耗",
    "已经死亡",
    "却活着",
    "时间倒流",
    "设定冲突",
    "事实矛盾",
)


def normalize_memory_conflicts(
    conflicts: list[Any] | None,
) -> list[dict[str, Any]]:
    """Normalize model conflicts without erasing narrative reversals.

    A character's public instruction and concealed motive can intentionally
    diverge. That is a plot reveal, not a broken story fact, when the
    description itself records the reveal. Keep it in the evidence stream
    but downgrade it from a hard continuity blocker. Open threats and costs
    caused by a chapter decision are also plot pressure, even when the model
    omits the conflict type. Unclassified contradictions remain fail-closed.
    """
    normalized: list[dict[str, Any]] = []
    for conflict in conflicts or []:
        if not isinstance(conflict, dict):
            continue
        item = dict(conflict)
        description = str(item.get("description") or item.get("message") or "")
        conflict_type = str(item.get("conflict_type") or "").strip().lower()
        resolution_status = str(
            item.get("resolution_status") or item.get("status") or ""
        ).strip().lower()
        if not conflict_type and any(
            marker in description for marker in _STRATEGIC_REVEAL_MARKERS
        ):
            conflict_type = "strategic_reveal"
        if not resolution_status and conflict_type == "strategic_reveal":
            resolution_status = "resolved"
        # A planned action being interrupted by an event is a normal plot
        # turn, not a contradiction in the durable truth state.  Keep it in
        # evidence so the next chapter can inherit the changed goal, but do
        # not let a model's generic ``high`` label block the chapter.
        if (
            not conflict_type
            and any(marker in description for marker in _PLOT_DISRUPTION_PLAN_MARKERS)
            and any(marker in description for marker in _PLOT_DISRUPTION_EVENT_MARKERS)
        ):
            conflict_type = "plot_disruption"
            resolution_status = "resolved"
        if conflict_type == "unresolved_plot":
            # Older prompt versions used this label for an open story thread.
            # Normalize it to the canonical type without losing its status.
            conflict_type = "plot_disruption"
        if (
            not conflict_type
            and any(marker in description for marker in _PLOT_PRESSURE_ACTION_MARKERS)
            and any(
                marker in description
                for marker in _PLOT_PRESSURE_CONSEQUENCE_MARKERS
            )
            and not any(marker in description for marker in _HARD_CONFLICT_MARKERS)
        ):
            # A choice creates a new threat, cost, deadline, or risk. This is
            # precisely the open pressure that should bridge into the next
            # chapter, not a contradiction in the truth ledger.
            conflict_type = "plot_disruption"
        if (
            not conflict_type
            and any(marker in description for marker in _RESOURCE_COST_MARKERS)
            and any(marker in description for marker in _RESOURCE_PRESSURE_MARKERS)
            and not any(marker in description for marker in _HARD_CONFLICT_MARKERS)
        ):
            # A stated cost such as "寿元只剩四十七年，长期生存目标受到
            # 威胁" is an intentional consequence that the next chapter must
            # inherit, not an impossible duplicate in the resource ledger.
            # Keep it as a plot-pressure evidence item.  Explicit hard-fact
            # markers above still take precedence for real contradictions.
            conflict_type = "plot_disruption"
        if (
            conflict_type in {"", "hard_fact"}
            and any(marker in description for marker in _RULE_EVOLUTION_MARKERS)
            and not any(marker in description for marker in _HARD_CONFLICT_MARKERS)
        ):
            # A system warning such as causal drift making future simulations
            # unpredictable is an intentional rule evolution caused by the
            # protagonist's choice. It creates the next pressure point; it is
            # not proof that a previously consumed resource or dead character
            # has been restored. Reclassify even an LLM-provided hard_fact,
            # while keeping explicit impossible-state markers fail-closed.
            conflict_type = "plot_disruption"
        item["conflict_type"] = conflict_type or "hard_fact"
        item["resolution_status"] = resolution_status or "unresolved"
        item["original_severity"] = str(item.get("severity") or "medium").lower()
        if item["conflict_type"] == "plot_disruption":
            # An unresolved plot disruption is an open threat or changed goal,
            # not a contradiction. Keep it as evidence for the next chapter,
            # but never let the high label block a valid story hand-off.
            item["severity"] = "medium"
        elif (
            item["conflict_type"] == "strategic_reveal"
            and item["resolution_status"] == "resolved"
        ):
            item["severity"] = "medium"
        normalized.append(item)
    return normalized


class MemoryEngine(BaseEngine):
    """Extracts structured story memory with a real LLM call."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.ai_gateway = AIGateway(
            self.tracer,
            db=self.db,
            novel_id=self.novel_id,
            project_id=self.project_id,
            provider_config=self.provider_config,
        )

    @property
    def capability(self) -> EngineCapability:
        return EngineCapability(
            engine_name="memory_engine",
            engine_type="memory",
            version="1.0.0",
            description="AI extraction of story memory with confidence gating",
            input_types=["chapter_text", "scene_text", "dialogue"],
            output_types=["state_updates", "memory_items", "conflicts"],
        )

    # ── Phase 1: analyze ────────────────────────────────────────────────
    async def analyze(self, input_data: dict[str, Any]) -> EngineResult:
        chapter_text = input_data.get("chapter_text", "") or ""

        if not chapter_text.strip():
            return EngineResult(
                success=False,
                reason="No text provided for memory extraction",
                confidence=0.0,
            )

        existing_characters = await self.brain.state.list_states("character", limit=50)
        existing_world = await self.brain.state.list_states("world", limit=50)
        existing_plot = await self.brain.state.list_states("plot", limit=50)

        analysis = {
            "chapter_number": input_data.get("chapter_number"),
            "run_id": input_data.get("run_id"),
            "apply_updates": bool(input_data.get("apply_updates", True)),
            "text_length": chinese_word_count(chapter_text),
            "chapter_text": chapter_text,
            "existing_keys": {
                "character": [s["key"] for s in existing_characters],
                "world": [s["key"] for s in existing_world],
                "plot": [s["key"] for s in existing_plot],
            },
            "existing_snapshot": {
                s["key"]: s["value"] for s in (existing_characters + existing_world)[:30]
            },
        }

        return EngineResult(
            success=True,
            result=analysis,
            confidence=0.9,
            reason=(
                f"Ready to extract memory from {analysis['text_length']} chars "
                f"against {sum(len(v) for v in analysis['existing_keys'].values())} known states"
            ),
        )

    # ── Phase 2: plan ───────────────────────────────────────────────────
    async def plan(self, analysis: EngineResult) -> EngineResult:
        if not analysis.success:
            return analysis

        data = analysis.result or {}
        plan = {
            **data,
            "categories": list(CATEGORY_TO_STATE_TYPE.keys()),
            "confidence_threshold": 0.7,
            "discard_threshold": 0.5,
        }
        return EngineResult(
            success=True,
            result=plan,
            confidence=0.9,
            reason="Memory extraction plan created (4 categories, confidence gated)",
        )

    # ── Phase 3: execute (real AI) ──────────────────────────────────────
    async def execute(self, plan: EngineResult) -> EngineResult:
        if not plan.success:
            return plan

        data = plan.result or {}
        chapter_text = (data.get("chapter_text") or "")[:12000]
        existing = json.dumps(data.get("existing_snapshot", {}), ensure_ascii=False)

        prompt = (
            "从下面这章小说正文中抽取需要长期记住的故事信息。\n\n"
            f"【已知设定（用于判断是否是新信息 / 是否冲突）】\n{existing}\n\n"
            f"【正文】\n{chapter_text}\n\n"
            "只输出 JSON：\n"
            "{\n"
            '  "character_updates": [{"key":"角色名.属性","summary":"一句话事实",'
            '"detail":"细节","confidence":0.9,"evidence":"原文依据"}],\n'
            '  "world_facts": [{"key":"设定名","summary":"...","detail":"...",'
            '"confidence":0.8,"evidence":"..."}],\n'
            '  "plot_events": [{"key":"事件短标识","summary":"...","detail":"...",'
            '"confidence":0.85,"evidence":"..."}],\n'
            '  "foreshadowing": [{"key":"伏笔短标识","summary":"...","detail":"...",'
            '"confidence":0.6,"evidence":"..."}],\n'
            '  "conflicts": [{"key":"冲突的已知设定","description":"如何冲突的",'
            '"severity":"low|medium|high","conflict_type":"hard_fact|timeline|resource|knowledge|strategic_reveal|plot_disruption|unresolved_plot",'
            '"resolution_status":"resolved|unresolved","evidence":"正文中解决冲突的依据"}],\n'
            '  "chapter_summary": "本章 100 字以内梗概"\n'
            "}\n"
            "confidence 取 0-1：正文明确写出的取 0.85-0.95，需要推断的取 0.5-0.75，"
            "纯猜测取 0.3 以下。key 用简短稳定的标识符，同一事物多章之间必须用同一个 key。\n"
            "为保证 JSON 完整：每个数组最多输出 3 条；只保留会影响后续章节的事实；"
            "summary 不超过 30 字，detail 和 evidence 各不超过 60 字，chapter_summary 不超过 80 字；"
            "不要重复已知设定，不要输出额外字段、Markdown 或解释。"
            "人物的表面意图与真实意图不同，且正文已经揭示时，标记为 strategic_reveal/resolved，"
            "不要把它当作硬设定冲突；计划被事件打断、被迫改线、对手制造新阻力，或金手指因因果偏移出现新的限制，属于 plot_disruption，"
            "例如‘因果偏移加剧、未来模拟不可预测’是规则演化，不是事实矛盾；"
            "即使仍未解决也不要标记为 high；只有时间线、资源、人物已知信息或未解决事实矛盾才标记为 high。"
        )

        try:
            ai = await self.ai_gateway.generate_json(
                prompt,
                system_prompt="你是小说设定管理员，只输出合法 JSON。",
                max_tokens=1800,
                temperature=0.2,
                prompt_name="v7.memory.extract",
                prompt_version="1.5.0",
            )
        except AIGatewayError as exc:
            return EngineResult(
                success=False,
                reason=f"AI memory extraction failed: {exc}",
                confidence=0.0,
                warnings=["memory engine requires a working LLM; no heuristic fallback"],
            )

        self.record_usage(ai["usage"])
        raw = ai["data"]

        items: list[dict[str, Any]] = []
        for category, state_type in CATEGORY_TO_STATE_TYPE.items():
            for entry in raw.get(category) or []:
                if not isinstance(entry, dict):
                    continue
                key = str(entry.get("key") or "").strip()
                summary = str(entry.get("summary") or "").strip()
                if not key or not summary:
                    continue
                confidence = entry.get("confidence")
                confidence = (
                    float(confidence) if isinstance(confidence, (int, float)) else 0.5
                )
                confidence = max(0.0, min(MAX_AI_CONFIDENCE, confidence))
                items.append(
                    {
                        "category": category,
                        "state_type": state_type,
                        "key": key,
                        "summary": summary,
                        "detail": entry.get("detail"),
                        "evidence": entry.get("evidence"),
                        "confidence": confidence,
                    }
                )

        result = {
            "chapter_number": data.get("chapter_number"),
            "run_id": data.get("run_id"),
            # Preserve the director's dry-run intent through the AI phase.
            # The director extracts memory before the chapter is accepted,
            # then commits the validated items exactly once after every
            # quality gate passes.  Dropping this flag here made the generic
            # engine update phase write state prematurely and caused the
            # acceptance-time write to run a second time.
            "apply_updates": bool(data.get("apply_updates", True)),
            "extracted_items": items,
            "extracted_count": len(items),
            "conflicts": normalize_memory_conflicts(raw.get("conflicts") or []),
            "chapter_summary": raw.get("chapter_summary") or "",
            "model": ai["usage"].get("model"),
        }

        if not items:
            return EngineResult(
                success=True,
                result=result,
                confidence=0.4,
                reason="AI extraction returned no memory items",
                warnings=["no memory items extracted from this chapter"],
            )

        avg_conf = sum(i["confidence"] for i in items) / len(items)
        return EngineResult(
            success=True,
            result=result,
            confidence=round(avg_conf, 3),
            reason=f"Extracted {len(items)} memory item(s), avg confidence {avg_conf:.2f}",
            warnings=(
                [f"{len(result['conflicts'])} conflict(s) with existing setting"]
                if result["conflicts"]
                else []
            ),
        )

    # ── Phase 4: validate ───────────────────────────────────────────────
    async def validate(self, output: EngineResult) -> EngineResult:
        if not output.success:
            return output

        data = output.result or {}
        items = data.get("extracted_items", [])

        valid_items: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        for item in items:
            identity = (item["state_type"], item["key"])
            if identity in seen:
                rejected.append({**item, "reject_reason": "duplicate key in batch"})
                continue
            if item["confidence"] < 0.5:
                rejected.append(
                    {**item, "reject_reason": "confidence below discard threshold 0.5"}
                )
                continue
            if len(item["key"]) > 180:
                rejected.append({**item, "reject_reason": "key too long"})
                continue
            seen.add(identity)
            valid_items.append(item)

        # Conflicts flagged by the model lower the confidence of the affected items.
        conflict_keys = {
            str(c.get("key")) for c in data.get("conflicts", []) if isinstance(c, dict)
        }
        for item in valid_items:
            if item["key"] in conflict_keys:
                item["confidence"] = min(item["confidence"], 0.65)
                item["conflict_flagged"] = True

        validation = {
            **data,
            "valid_items": valid_items,
            "rejected_items": rejected,
            "validation_passed": True,
            "conflicts_found": len(data.get("conflicts", [])),
        }

        return EngineResult(
            success=True,
            result=validation,
            confidence=output.confidence,
            reason=(
                f"{len(valid_items)} item(s) passed validation, "
                f"{len(rejected)} rejected, {validation['conflicts_found']} conflict(s)"
            ),
            warnings=output.warnings,
        )

    async def apply_validated_items(self, data: dict[str, Any]) -> EngineResult:
        """Commit extracted memory only after the chapter quality gate passes."""
        chapter_number = data.get("chapter_number")
        run_id = data.get("run_id")
        if isinstance(run_id, str):
            try:
                run_id = uuid.UUID(run_id)
            except ValueError:
                run_id = None

        applied = 0
        pending = 0
        discarded = 0
        actions: list[dict[str, Any]] = []

        for item in data.get("valid_items", []):
            outcome = await self.brain.state.update_state(
                item["state_type"],
                item["key"],
                {
                    "summary": item["summary"],
                    "detail": item.get("detail"),
                    "evidence": item.get("evidence"),
                    "category": item["category"],
                    "chapter_number": chapter_number,
                },
                item["confidence"],
                source="memory_engine",
                source_run_id=run_id,
                reason=f"extracted from accepted chapter {chapter_number}",
            )
            action = outcome.get("action")
            if action in ("updated", "created"):
                applied += 1
            elif action == "pending_review":
                pending += 1
            else:
                discarded += 1
            actions.append(
                {
                    "key": item["key"],
                    "state_type": item["state_type"],
                    "confidence": item["confidence"],
                    "action": action,
                }
            )

        for conflict in data.get("conflicts", []):
            if not isinstance(conflict, dict):
                continue
            await self.event_bus.publish(
                "memory_conflict_detected",
                f"Memory conflict: {conflict.get('key')}",
                "memory",
                source="memory_engine",
                severity="warning",
                event_data={
                    "chapter_number": chapter_number,
                    "key": conflict.get("key"),
                    "description": conflict.get("description"),
                    "severity": conflict.get("severity"),
                },
            )

        await self.brain.state.update_state(
            "global",
            "last_memory_extraction",
            {
                "chapter_number": chapter_number,
                "extracted_count": data.get("extracted_count", 0),
                "applied": applied,
                "pending_review": pending,
                "discarded": discarded,
                "conflicts_found": data.get("conflicts_found", 0),
            },
            0.9,
            source="memory_engine",
            source_run_id=run_id,
            reason="accepted chapter memory extraction summary",
        )

        return EngineResult(
            success=True,
            result={
                "brain_updated": True,
                "chapter_number": chapter_number,
                "states_applied": applied,
                "states_pending_review": pending,
                "states_discarded": discarded,
                "conflicts_found": data.get("conflicts_found", 0),
                "chapter_summary": data.get("chapter_summary", ""),
                "actions": actions,
                "rejected_items": [
                    {"key": r["key"], "reason": r["reject_reason"]}
                    for r in data.get("rejected_items", [])
                ],
            },
            confidence=float(data.get("confidence") or 0.9),
            reason=(
                f"Applied {applied}, pending {pending}, discarded {discarded} "
                f"state update(s) through the confidence gate"
            ),
        )

    # ── Phase 5: update (confidence gated writes) ───────────────────────
    async def update(self, validated: EngineResult) -> EngineResult:
        if not validated.success:
            return validated

        data = validated.result or {}
        if not data.get("apply_updates", True):
            # The Story Director uses this dry-run mode while the chapter is
            # still being reviewed.  A rejected draft must not become truth
            # state for the next chapter.
            return EngineResult(
                success=True,
                result={
                    "brain_updated": False,
                    "deferred": True,
                    "chapter_number": data.get("chapter_number"),
                    "run_id": data.get("run_id"),
                    "valid_items": data.get("valid_items", []),
                    "extracted_items": data.get("valid_items", []),
                    "rejected_items": data.get("rejected_items", []),
                    "conflicts": data.get("conflicts", []),
                    "conflicts_found": data.get("conflicts_found", 0),
                    "extracted_count": data.get("extracted_count", 0),
                    "chapter_summary": data.get("chapter_summary", ""),
                    "states_applied": 0,
                    "states_pending_review": 0,
                    "states_discarded": len(data.get("rejected_items", [])),
                },
                confidence=validated.confidence,
                reason="Memory extraction deferred until chapter quality acceptance",
                warnings=validated.warnings,
            )

        return await self.apply_validated_items(data)
