"""Plot Engine - Sprint 2.

Real plot structure engine. It works in two modes:

* ``assess``  — run BEFORE a chapter is written. Evaluates whether the story is
  ready for chapter N: which goals are due, which threads are open, what the
  chapter must accomplish, and how confident we are that auto-generation is
  safe. This confidence feeds the Story Director's decision gate.
* ``analyze`` — run AFTER a chapter exists. Measures pacing with Chinese word
  counting, dialogue ratio and scene rhythm, and asks the model for a
  structural critique.

Both modes write real rows into ``v7_plot_nodes``; there is no placeholder
branch and no fabricated confidence.
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from .base import BaseEngine, EngineCapability, EngineResult
from ..generation.generation_engine import (
    AIGateway,
    AIGatewayError,
    chinese_word_count,
)
from ..repositories.plot import PlotNodeRepository
from ...services.quality_profiles import compile_quality_directive, quality_profile_metadata
from ..quality.readability_contract import build_readability_plan, render_readability_plan

MODE_ASSESS = "assess"
MODE_ANALYZE = "analyze"

# Confidence can never be reported as certainty — the model is not an oracle.
MAX_CONFIDENCE = 0.95
MIN_CONFIDENCE = 0.05

DIALOGUE_PATTERN = re.compile(r"[「“\"']([^」”\"']{1,400})[」”\"']")


def _clamp(value: float, low: float = MIN_CONFIDENCE, high: float = MAX_CONFIDENCE) -> float:
    return round(max(low, min(high, value)), 3)


class PlotEngine(BaseEngine):
    """Manages plot structure, pacing and story beats against real brain data."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.ai_gateway = AIGateway(
            self.tracer,
            db=self.db,
            novel_id=self.novel_id,
            project_id=self.project_id,
            provider_config=self.provider_config,
        )
        self.plot_repo = PlotNodeRepository(self.db)

    @property
    def capability(self) -> EngineCapability:
        return EngineCapability(
            engine_name="plot_engine",
            engine_type="plot",
            version="1.0.0",
            description=(
                "Assesses plot readiness before generation and analyses "
                "structure/pacing after generation; persists the plot tree"
            ),
            input_types=["chapter_outline", "chapter_text", "scene_plan"],
            output_types=["plot_assessment", "pacing_report", "plot_nodes"],
        )

    # ── Phase 1: analyze ────────────────────────────────────────────────
    async def analyze(self, input_data: dict[str, Any]) -> EngineResult:
        chapter_number = int(input_data.get("chapter_number") or 0)
        if chapter_number <= 0:
            return EngineResult(
                success=False,
                reason="chapter_number is required",
                confidence=0.0,
            )

        chapter_text = (input_data.get("chapter_text") or "").strip()
        mode = input_data.get("mode") or (MODE_ANALYZE if chapter_text else MODE_ASSESS)

        if mode == MODE_ANALYZE:
            return await self._analyze_written_chapter(chapter_number, chapter_text)
        return await self._assess_upcoming_chapter(chapter_number, input_data)

    # ── assess mode ─────────────────────────────────────────────────────
    async def _assess_upcoming_chapter(
        self, chapter_number: int, input_data: dict[str, Any]
    ) -> EngineResult:
        outline = (input_data.get("outline") or "").strip()
        perception = input_data.get("perception") or {}

        goals = await self.brain.goals.list_goals(limit=100)
        open_goals = [
            g for g in goals if g.get("status") in ("pending", "in_progress")
        ]
        due_goals = [
            g for g in open_goals
            if g.get("target_chapter") and g["target_chapter"] <= chapter_number
        ]
        overdue_goals = [
            g for g in due_goals if (g.get("progress") or 0.0) < 1.0
        ]

        plot_states = await self.brain.state.list_states("plot", limit=100)
        open_threads = [
            s for s in plot_states
            if isinstance(s.get("value"), dict)
            and s["value"].get("status") in ("open", "active", "pending")
        ]

        existing_node = await self.plot_repo.get_chapter_node(
            self.novel_id, chapter_number
        )
        previous_node = (
            await self.plot_repo.get_chapter_node(self.novel_id, chapter_number - 1)
            if chapter_number > 1 else None
        )

        # ── deterministic readiness signals (no AI needed, cannot be faked) ──
        signals: list[str] = []
        blockers: list[str] = []

        if chapter_number > 1 and not perception.get("has_previous_chapter"):
            blockers.append(
                f"chapter {chapter_number - 1} text is missing from brain state"
            )
        if chapter_number > 1 and previous_node is None:
            signals.append(f"no plot node recorded for chapter {chapter_number - 1}")
        if not outline:
            signals.append("no outline supplied for this chapter")
        if int(perception.get("pending_review") or 0) > 0:
            signals.append(
                f"{perception['pending_review']} state(s) awaiting human review"
            )
        # A freshly bootstrapped novel has not necessarily materialised goal
        # rows yet.  Treating that normal first-chapter state as a risk signal
        # lowered otherwise usable confidence and blocked the only prose
        # chain before writing.  Later chapters still surface an exhausted
        # goal tree for review.
        if not open_goals and chapter_number > 1:
            signals.append("no open story goals — the arc may be exhausted")
        if existing_node and existing_node.status == "completed":
            signals.append(
                f"chapter {chapter_number} already has a completed plot node "
                "(regeneration)"
            )

        # ── AI structural judgement on what this chapter must do ────────
        ai_payload: dict[str, Any] = {}
        ai_confidence: float | None = None
        warnings: list[str] = []

        prompt = self._build_assess_prompt(
            chapter_number, outline, open_goals, overdue_goals, open_threads,
            perception, previous_node,
        )
        try:
            ai = await self.ai_gateway.generate_json(
                prompt,
                system_prompt="你是一名中文长篇小说的结构编辑，只输出合法 JSON，不要输出任何解释。",
                max_tokens=2500,
                temperature=0.3,
                prompt_name="v7.plot.assess",
                # The assessment prompt now carries the same generation-first
                # POV, fictional-world, and safe-language contract as the
                # writer. Keep its provenance version distinct from the old
                # planning prompt so production traces cannot silently mix
                # pre-contract and post-contract decisions.
                prompt_version="1.3.0",
            )
            ai_payload = ai["data"] or {}
            self.record_usage(ai["usage"])
            raw_conf = ai_payload.get("confidence")
            if isinstance(raw_conf, (int, float)):
                ai_confidence = _clamp(float(raw_conf))
        except AIGatewayError as exc:
            return EngineResult(
                success=False,
                reason=f"plot assessment AI call failed: {exc}",
                confidence=0.0,
            )
        except (ValueError, KeyError) as exc:
            warnings.append(f"plot assessment JSON unusable: {exc}")

        if ai_confidence is None:
            return EngineResult(
                success=False,
                reason="plot assessment did not return a usable confidence value",
                confidence=0.0,
                warnings=warnings,
            )

        # Deterministic penalties applied on top of the model's own judgement.
        confidence = ai_confidence
        confidence -= 0.10 * len(blockers)
        confidence -= 0.05 * len(signals)
        confidence = _clamp(confidence)

        assessment = {
            "mode": MODE_ASSESS,
            "chapter_number": chapter_number,
            "must_accomplish": ai_payload.get("must_accomplish") or [],
            "tension_target": ai_payload.get("tension_target"),
            "pacing_advice": ai_payload.get("pacing_advice"),
            "reader_promise": ai_payload.get("reader_promise"),
            "reader_experience_plan": ai_payload.get("reader_experience_plan") or {},
            "prose_texture_plan": ai_payload.get("prose_texture_plan") or {},
            "payoff_contract": ai_payload.get("payoff_contract") or {},
            "emotional_target": ai_payload.get("emotional_target"),
            "opening_anchor": ai_payload.get("opening_anchor"),
            "hook": ai_payload.get("hook"),
            "risks": ai_payload.get("risks") or [],
            "suggested_beats": ai_payload.get("suggested_beats") or [],
            "chapter_title_hint": ai_payload.get("chapter_title"),
            "open_goals": [
                {"id": g["id"], "name": g["name"],
                 "target_chapter": g.get("target_chapter"),
                 "progress": g.get("progress")}
                for g in open_goals[:10]
            ],
            "overdue_goals": [g["name"] for g in overdue_goals],
            "open_threads": [s.get("key") for s in open_threads][:10],
            "signals": signals,
            "blockers": blockers,
            "ai_confidence": ai_confidence,
            "existing_node_status": existing_node.status if existing_node else None,
            "quality_profile": quality_profile_metadata(self.quality_profile) if self.quality_profile else {},
        }

        return EngineResult(
            success=not blockers,
            result=assessment,
            confidence=confidence,
            reason=(
                f"assessed chapter {chapter_number}: "
                f"{len(assessment['must_accomplish'])} objective(s), "
                f"{len(signals)} signal(s), {len(blockers)} blocker(s)"
            ),
            warnings=warnings,
        )

    def _build_assess_prompt(
        self,
        chapter_number: int,
        outline: str,
        open_goals: list[dict[str, Any]],
        overdue_goals: list[dict[str, Any]],
        open_threads: list[dict[str, Any]],
        perception: dict[str, Any],
        previous_node: Any,
    ) -> str:
        goal_lines = "\n".join(
            f"- {g['name']}（类型 {g['type']}，目标章 {g.get('target_chapter') or '未定'}，"
            f"进度 {round((g.get('progress') or 0.0) * 100)}%）：{g.get('description') or ''}"
            for g in open_goals[:12]
        ) or "（暂无未完成目标）"

        thread_lines = "\n".join(
            f"- {s.get('key')}：{(s.get('value') or {}).get('thread') or ''}"
            f"（状态 {(s.get('value') or {}).get('status')}）"
            for s in open_threads[:10]
        ) or "（暂无进行中的情节线）"

        prev_line = "（本章是第一章，没有前一章）"
        if previous_node is not None:
            prev_line = (
                f"上一章《{previous_node.node_name}》状态 {previous_node.status}，"
                f"实际字数 {previous_node.word_count_actual or '未知'}。"
                f"梗概：{(previous_node.description or '')[:300]}"
            )

        readability_plan = build_readability_plan(
            chapter_number,
            quality_profile=self.quality_profile or {},
        )
        quality_directive = compile_quality_directive(
            self.quality_profile or None,
            chapter_number=chapter_number,
            chapter_function={"reader_expectation": "本章读完仍想继续"},
            readability_plan=readability_plan,
        )

        return f"""你正在为一部中文长篇小说规划第 {chapter_number} 章的结构。

【本章大纲】
{(outline or "（作者未提供大纲，请根据目标与情节线自行推断本章应当承担什么）")[:12000]}

【未完成的故事目标】
{goal_lines}

【进行中的情节线】
{thread_lines}

【前情】
{prev_line}

【当前状态总数】{perception.get('state_total', 0)} 条，待人工复核 {perception.get('pending_review', 0)} 条。

【网文质量策略】
{quality_directive}

{render_readability_plan(readability_plan)}

请判断：这一章应该完成什么、张力应该推到什么位置、节奏如何安排、有什么风险，
并给出 4-6 个节拍建议。同时给出你对"现在就自动生成这一章是否安全"的置信度。

置信度评判标准（严格执行，不要一律给高分）：
- 0.85-0.95：目标清晰、前情完整、大纲明确，可放心自动生成
- 0.70-0.85：基本清楚，但有个别信息需要推断
- 0.50-0.70：关键信息缺失（如无大纲且目标模糊），建议人工确认
- 0.50 以下：前后矛盾或严重缺失，不应自动生成

只输出如下 JSON：
{{
  "chapter_title": "事件/意象短标题（2-12 字，不超过 20 字）",
  "must_accomplish": ["本章必须完成的事 1", "本章必须完成的事 2"],
  "tension_target": "本章张力目标的一句话描述",
  "pacing_advice": "节奏建议的一句话描述",
  "reader_promise": "本章给读者的情绪/信息承诺，以及读者为什么要继续追读",
  "emotional_target": "情绪曲线：开场情绪 -> 中段转折 -> 章末情绪",
  "reader_experience_plan": {{"reader_emotion":"读者在现场感受到什么","information_to_feel":"信息如何通过事件落地","scene_payoff":"本章兑现","avoid":["同构写法"]}},
  "prose_texture_plan": {{"information_delivery":"动作/对白/物件/反馈","rhythm":"句段节奏","voice_anchor":"人物声音抓手"}},
  "opening_anchor": "本章开头必须承接上一章尾部的具体动作、地点或未决问题",
  "hook": "章末必须落到具体动作、发现或选择的追读钩子",
  "payoff_contract": {{"reader_promise":"读者本章要等什么","pressure":"当前压力", "active_choice":"主角主动选择", "payoff_type":"兑现类型", "visible_result":"可见结果", "witness_reaction":"他人反应", "cost":"代价/余波", "next_pressure":"章末新增压力", "setup_refs":[]}},
  "risks": ["风险 1", "风险 2"],
  "suggested_beats": [
    {{"name": "节拍名", "content": "这一节拍发生什么", "target_words": 600,
      "emotion": "情绪", "importance": 0.6,
      "payoff_phase": "pressure|build|burst|feedback|aftershock"}}
  ],
  "confidence": 0.0
}}

每个 suggested_beats 必须显式标注 payoff_phase 或 payoff_phases，严格覆盖
pressure、build、burst、feedback、aftershock 五个阶段；至少一个节拍必须是
build，内容要有试探、准备、取舍或蓄力，不能把连续施压当作 build。
标题必须是读者会看到的短标题，不得写成剧情摘要或操作说明；禁止出现“第X章”、
“本章”、“主角在……发现……”、“读者将……”等元叙述模板。若与上一章标题相近，
改用本章具体事件、物件、冲突或情绪意象命名。"""

    # ── analyze mode ────────────────────────────────────────────────────
    async def _analyze_written_chapter(
        self, chapter_number: int, chapter_text: str
    ) -> EngineResult:
        word_count = chinese_word_count(chapter_text)
        paragraphs = [p for p in chapter_text.split("\n") if p.strip()]
        dialogues = DIALOGUE_PATTERN.findall(chapter_text)
        dialogue_chars = sum(chinese_word_count(d) for d in dialogues)
        dialogue_ratio = round(dialogue_chars / word_count, 3) if word_count else 0.0
        para_lengths = [chinese_word_count(p) for p in paragraphs]
        avg_para = round(sum(para_lengths) / len(para_lengths), 1) if para_lengths else 0.0

        structure_notes: list[str] = []
        if word_count < 2000:
            structure_notes.append("章节偏短，可能显得仓促")
        elif word_count > 6000:
            structure_notes.append("章节偏长，需检查节奏是否拖沓")
        if dialogue_ratio < 0.08:
            structure_notes.append("对白比例过低，画面偏静")
        elif dialogue_ratio > 0.55:
            structure_notes.append("对白比例过高，叙述支撑不足")
        if avg_para > 220:
            structure_notes.append("段落平均过长，阅读压力大")
        if len(paragraphs) < 8:
            structure_notes.append("段落数偏少，缺少呼吸节奏")

        analysis = {
            "mode": MODE_ANALYZE,
            "chapter_number": chapter_number,
            "word_count": word_count,
            "paragraph_count": len(paragraphs),
            "avg_paragraph_chars": avg_para,
            "dialogue_count": len(dialogues),
            "dialogue_ratio": dialogue_ratio,
            "estimated_reading_minutes": round(word_count / 500, 1),
            "structure_notes": structure_notes,
        }

        # Confidence reflects how well-formed the measured structure is.
        confidence = _clamp(0.9 - 0.08 * len(structure_notes))
        return EngineResult(
            success=True,
            result=analysis,
            confidence=confidence,
            reason=(
                f"chapter {chapter_number}: {word_count} chars, "
                f"{len(paragraphs)} paragraphs, dialogue {dialogue_ratio:.0%}"
            ),
            warnings=structure_notes,
        )

    # ── Phase 2: plan ───────────────────────────────────────────────────
    async def plan(self, analysis: EngineResult) -> EngineResult:
        if not analysis.success:
            return analysis

        data = analysis.result or {}
        chapter_number = int(data.get("chapter_number") or 0)
        mode = data.get("mode")

        if mode == MODE_ASSESS:
            beats = data.get("suggested_beats") or []
            node_plan = {
                "chapter_number": chapter_number,
                "node_name": data.get("chapter_title_hint") or f"第{chapter_number}章",
                "description": data.get("tension_target"),
                "status": "planned",
                "word_count_target": sum(
                    int(b.get("target_words") or 0) for b in beats
                ) or None,
                "importance": _clamp(
                    0.5 + 0.1 * len(data.get("overdue_goals") or []), 0.3, 0.95
                ),
                "node_data": {
                    "must_accomplish": data.get("must_accomplish"),
                    "pacing_advice": data.get("pacing_advice"),
                    "risks": data.get("risks"),
                    "open_threads": data.get("open_threads"),
                },
                "beats": beats,
            }
            actions = ["upsert_chapter_node"]
            if beats:
                actions.append("replace_beat_nodes")
        else:
            notes = data.get("structure_notes") or []
            node_plan = {
                "chapter_number": chapter_number,
                "node_name": f"第{chapter_number}章",
                "description": None,
                "status": "completed",
                "word_count_actual": data.get("word_count"),
                "importance": 0.5,
                "node_data": {
                    "pacing": {
                        "dialogue_ratio": data.get("dialogue_ratio"),
                        "avg_paragraph_chars": data.get("avg_paragraph_chars"),
                        "paragraph_count": data.get("paragraph_count"),
                    },
                    "structure_notes": notes,
                },
                "beats": [],
            }
            actions = ["upsert_chapter_node"]
            if notes:
                actions.append("flag_pacing_review")

        return EngineResult(
            success=True,
            result={"actions": actions, "node_plan": node_plan, "mode": mode},
            confidence=analysis.confidence,
            reason=f"planned {len(actions)} plot action(s) for chapter {chapter_number}",
        )

    # ── Phase 3: execute ────────────────────────────────────────────────
    async def execute(self, plan: EngineResult) -> EngineResult:
        if not plan.success:
            return plan

        data = plan.result or {}
        node_plan = data.get("node_plan") or {}
        chapter_number = int(node_plan.get("chapter_number") or 0)
        if chapter_number <= 0:
            return EngineResult(
                success=False,
                reason="plan is missing a chapter_number",
                confidence=0.0,
            )

        goal_id = None
        goals = await self.brain.goals.list_goals(limit=100)
        for g in goals:
            if (
                g.get("status") in ("pending", "in_progress")
                and g.get("target_chapter")
                and g["target_chapter"] >= chapter_number
            ):
                goal_id = uuid.UUID(g["id"])
                break

        node, action = await self.plot_repo.upsert_chapter_node(
            self.novel_id,
            chapter_number,
            str(node_plan.get("node_name") or f"第{chapter_number}章")[:200],
            description=node_plan.get("description"),
            status=str(node_plan.get("status") or "planned"),
            word_count_target=node_plan.get("word_count_target"),
            word_count_actual=node_plan.get("word_count_actual"),
            importance=float(node_plan.get("importance") or 0.5),
            confidence=float(plan.confidence or 0.8),
            node_data=node_plan.get("node_data") or {},
            goal_id=goal_id,
        )

        beats = node_plan.get("beats") or []
        beat_nodes = []
        if beats:
            beat_nodes = await self.plot_repo.create_beat_nodes(
                self.novel_id, node.id, chapter_number, beats
            )

        return EngineResult(
            success=True,
            result={
                "mode": data.get("mode"),
                "chapter_number": chapter_number,
                "chapter_node_id": str(node.id),
                "chapter_node_action": action,
                "chapter_node_status": node.status,
                "beat_nodes_created": len(beat_nodes),
                "executed_actions": data.get("actions") or [],
                "goal_id": str(goal_id) if goal_id else None,
            },
            confidence=plan.confidence,
            reason=(
                f"chapter node {action}, {len(beat_nodes)} beat node(s) written"
            ),
        )

    # ── Phase 4: validate ───────────────────────────────────────────────
    async def validate(self, output: EngineResult) -> EngineResult:
        if not output.success:
            return output

        data = output.result or {}
        chapter_number = int(data.get("chapter_number") or 0)
        issues: list[str] = []

        node = await self.plot_repo.get_chapter_node(self.novel_id, chapter_number)
        if node is None:
            issues.append(f"chapter node for chapter {chapter_number} was not persisted")
        else:
            if node.chapter_number != chapter_number:
                issues.append("persisted node has a mismatched chapter_number")
            if not (0.0 <= node.importance <= 1.0):
                issues.append(f"importance out of range: {node.importance}")
            if not (0.0 <= node.confidence <= 1.0):
                issues.append(f"confidence out of range: {node.confidence}")

        # Chapter nodes must not skip numbers — a gap means the plot tree lost a chapter.
        chapter_nodes = await self.plot_repo.list_nodes(
            self.novel_id, node_type="chapter", limit=500
        )
        numbers = sorted(n.chapter_number for n in chapter_nodes if n.chapter_number)
        gaps = [
            n for n in range(1, (numbers[-1] if numbers else 0) + 1)
            if n not in numbers
        ]
        if gaps:
            issues.append(f"plot tree has missing chapter nodes: {gaps[:10]}")

        return EngineResult(
            success=not issues,
            result={
                **data,
                "validation_passed": not issues,
                "validation_issues": issues,
                "chapter_nodes_total": len(chapter_nodes),
            },
            confidence=_clamp((output.confidence or 0.8) - 0.1 * len(issues)),
            reason=(
                "plot node validation passed"
                if not issues else f"{len(issues)} validation issue(s)"
            ),
            warnings=issues,
        )

    # ── Phase 5: update ─────────────────────────────────────────────────
    async def update(self, validated: EngineResult) -> EngineResult:
        if not validated.success:
            return validated

        data = validated.result or {}
        chapter_number = int(data.get("chapter_number") or 0)
        mode = data.get("mode")

        state_value: dict[str, Any] = {
            "chapter_number": chapter_number,
            "mode": mode,
            "chapter_node_id": data.get("chapter_node_id"),
            "chapter_node_status": data.get("chapter_node_status"),
            "beat_nodes": data.get("beat_nodes_created"),
            "chapter_nodes_total": data.get("chapter_nodes_total"),
        }
        state_result = await self.brain.state.update_state(
            "plot",
            "plot_tree_status",
            state_value,
            _clamp(validated.confidence or 0.8),
            source="plot_engine",
            reason=f"plot engine {mode} pass for chapter {chapter_number}",
        )

        return EngineResult(
            success=True,
            result={
                "brain_updated": state_result.get("action") in ("created", "updated"),
                "state_action": state_result.get("action"),
                "chapter_number": chapter_number,
            },
            confidence=validated.confidence,
            reason=f"plot state {state_result.get('action')}",
        )
