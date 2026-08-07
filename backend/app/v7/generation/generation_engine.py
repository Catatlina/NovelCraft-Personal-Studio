"""Generation Engine - Sprint 2.

Real generation pipeline:
  context assembly -> scene planning (AI) -> AI generation -> de-AI pipeline

No mocks, no placeholder text. Failures raise instead of returning fake success.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from typing import Any

import httpx
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from ..brain.novel_brain import NovelBrain
from ..trace.tracer import ExecutionTracer
from ..events.event_bus import EventBus
from ...services.ai_runtime import (
    execution_key as build_execution_key,
    normalise_prompt_version,
    prompt_hash,
    record_async_execution,
)
from ...services.unified_gateway import UnifiedAIGateway
from ...services.text_quality import (
    chapter_mirror_stats,
    deduplicate_full_paragraphs,
    duplicate_paragraph_stats,
    normalize_and_validate_rewrite,
)
from ...services.chapter_payoff import (
    build_payoff_contract,
    repair_payoff_beat_structure,
    validate_payoff_contract,
    validate_payoff_variety,
    score_payoff_contract,
)
from ...services.content_policy import analyze_content_policy, content_generation_contract
from ...services.quality_profiles import (
    compile_quality_directive,
    quality_profile_metadata,
    select_quality_profile,
)
from ..quality.deai_metrics import analyze_deai_patterns
from ..quality.novel_reviewer_reference import render_ai_flavor_guidance
from ...services.pov_quality import analyze_third_person_narrative, third_person_generation_contract

# P1-3 质量整改：导入质量门控灰度开关
from ..integration.quality import CHAPTER_MIRROR_HARD_GATE, PAYOFF_VARIETY_HARD_GATE

logger = logging.getLogger(__name__)

CHAPTER_STATE_TYPE = "chapter"


def chinese_word_count(text: str) -> int:
    """Count characters the way Chinese novel platforms do (whitespace ignored)."""
    if not text:
        return 0
    return len(re.sub(r"\s+", "", text))


def chapter_state_key(chapter_number: int) -> str:
    return f"chapter_{chapter_number:04d}"


def _chapter_title_key(value: Any) -> str:
    """Normalize a chapter title for duplicate detection."""
    text = re.sub(r"第\s*\d+\s*章", "", str(value or ""))
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


def _title_hint_fragment(value: Any) -> str:
    """Extract a short event-shaped title suffix from a plot hint."""
    text = str(value or "").strip()
    text = re.sub(r"^(?:本章|章末|钩子|结果)\s*[：:]?", "", text)
    text = re.split(r"[。！？；\n]", text, maxsplit=1)[0]
    text = re.sub(r"[“”\"'「」《》]", "", text)
    text = re.sub(r"^(?:主角)?(?:发现|收到|看见|听见|进入|遭遇|面对)\s*", "", text)
    text = re.sub(r"^(?:语音|消息|短信)(?:中|里)?(?:传来|出现|提示)\s*", "", text)
    text = re.sub(r"(?:的)?(?:声音|消息|警告)$", "", text)
    text = text.strip(" ：:，,、—-")
    text = text[:12].rstrip("的了着在与和或从向")
    return text.strip(" ：:，,、—-")


def ensure_unique_chapter_title(
    title: Any,
    *,
    previous_titles: list[Any] | None = None,
    chapter_number: int = 0,
    hints: list[Any] | None = None,
) -> str:
    """Keep provider chapter titles readable and unique within the novel.

    The plot model remains responsible for creative naming. This guard only
    intervenes when it repeats a recent title, using an already-planned event
    or hook as a compact suffix; it never bans punctuation or a natural title
    form globally.
    """
    def clean_title(value: Any) -> str:
        text = str(value or "").strip()
        text = re.sub(r"^第\s*\d+\s*章\s*[：:、\s]*", "", text)
        # Planning models sometimes return a sentence instead of a title:
        # "主角在旧宅中发现一张旧照". Strip only the meta/action lead; do
        # not ban natural punctuation or ordinary event wording.
        text = re.sub(
            r"^(?:本章|这一章|主角|人物|他|她)?"
            r"(?:在[^，。！？：:]{0,20})?"
            r"(?:发现|收到|看见|听见|进入|遭遇|面对|决定|开始)\s*",
            "",
            text,
        )
        text = re.sub(r"^(?:本章|这一章)(?:将|要)?\s*", "", text)
        text = re.sub(r"[（(][^）)]{0,20}[）)]$", "", text).strip()
        return text.strip(" ：:，,、—-")[:20]

    base = clean_title(title) or f"第{chapter_number}章"
    previous_keys = {
        _chapter_title_key(item)
        for item in (previous_titles or [])
        if _chapter_title_key(item)
    }
    if _chapter_title_key(base) not in previous_keys:
        return base[:40]

    for hint in hints or []:
        fragment = clean_title(_title_hint_fragment(hint))
        if len(_chapter_title_key(fragment)) < 2:
            continue
        candidate = f"{base}·{fragment}"
        if _chapter_title_key(candidate) not in previous_keys:
            return candidate[:40]

    # Last-resort uniqueness is preferable to silently presenting several
    # chapters under one label when a provider repeats an unhelpful title.
    suffix = f"第{chapter_number}章" if chapter_number else "新线索"
    return f"{base}·{suffix}"[:40]


class AIGatewayError(RuntimeError):
    """Raised when the LLM call cannot be completed."""


class BudgetAccountingError(AIGatewayError):
    """Raised when a successful provider call cannot be durably accounted for."""


def is_retryable_provider_failure(error: Any) -> bool:
    """Classify a provider failure that is safe to retry at the task layer.

    This is deliberately narrower than ``AIGatewayError``.  Missing keys,
    budget failures and ledger failures must stop immediately; a transient
    5xx/rate-limit/transport failure may be retried by the bounded Celery
    task.  Keeping the classification next to the gateway prevents the V7
    director and worker from making different decisions about the same error.
    """
    text = str(error or "").strip().lower()
    if not text:
        return False

    permanent_markers = (
        "api key",
        "not configured",
        "refusing to fabricate",
        "budget",
        "cost accounting",
        "accounting failed",
        "ledger",
    )
    if any(marker in text for marker in permanent_markers):
        return False

    transient_markers = (
        "server error",
        "service unavailable",
        "temporarily unavailable",
        "rate limit",
        "too many requests",
        "timeout",
        "timed out",
        "connection reset",
        "connection refused",
        "connection error",
        "502",
        "503",
        "504",
        "429",
        "llm call failed after",
        "did not return parseable json",
        "json unusable",
        "usable confidence",
    )
    return any(marker in text for marker in transient_markers)


class ContextAssembler:
    """Assembles real generation context out of the Novel Brain."""

    def __init__(self, brain: NovelBrain, project_id: str | None = None):
        self.brain = brain
        self.project_id = project_id

    async def load_style_card(self) -> dict[str, Any]:
        """Load the V6 author/genre card used by the shared project scope."""
        if not self.project_id:
            return {}

        def _read() -> dict[str, Any]:
            from ...db import connect, decode

            conn = connect()
            try:
                row = conn.execute(
                    "SELECT author_card, genre_card FROM style_cards "
                    "WHERE project_id=%s ORDER BY updated_at DESC LIMIT 1",
                    (self.project_id,),
                ).fetchone()
                if not row:
                    return {}
                return {
                    "author_card": decode(row.get("author_card"), {}) or {},
                    "genre_card": decode(row.get("genre_card"), {}) or {},
                }
            finally:
                conn.close()

        return await asyncio.to_thread(_read)

    async def load_previous_chapters(
        self,
        chapter_number: int,
        *,
        count: int = 2,
        include_rejected: bool = False,
    ) -> list[dict[str, Any]]:
        """Load accepted chapters; rejected drafts never become story context."""
        states = await self.brain.state.list_states(CHAPTER_STATE_TYPE, limit=200)
        chapters: list[dict[str, Any]] = []
        for s in states:
            value = s.get("value") or {}
            num = value.get("chapter_number")
            if (
                isinstance(num, int)
                and num < chapter_number
                and (include_rejected or value.get("passed_review") is not False)
            ):
                chapters.append(value)
        chapters.sort(key=lambda c: c.get("chapter_number", 0))
        return chapters[-count:] if count > 0 else chapters

    async def assemble_context(
        self,
        chapter_number: int,
        *,
        scene_type: str = "normal",
        token_budget: int = 5400,
        include_rejected: bool = False,
    ) -> dict[str, Any]:
        """Assemble layered context: state / goals / constraints / recap.

        Rejected drafts are excluded by default. Ordered diagnostic batches may
        opt in so a held chapter can still be measured for cross-chapter
        continuity; the rendered context labels that chapter as provisional.
        """
        overview = await self.brain.get_overview()

        # 长程连续性修复（2026-08-02）：此前 world/character/plot 各只取
        # 最新 30 条，50 章长程下早期关键设定（伏笔/设定细节）会被挤出
        # 上下文窗口，导致后段连贯性下滑（50 章测试 CH46-50 连贯性跌到
        # 78.8）。改为按需取全量：world/character 取 120 条、plot 取 100 条，
        # global 取全量。state 是压缩后的摘要（每条 ~200 字），120 条约
        # 2.4 万字 ≈ 6k tokens，仍在 8k 上下文预算内。
        character_states = await self.brain.state.list_states("character", limit=120)
        world_states = await self.brain.state.list_states("world", limit=120)
        plot_states = await self.brain.state.list_states("plot", limit=100)
        global_states = await self.brain.state.list_states("global", limit=100)

        goals = await self.brain.goals.list_goals(limit=50)
        active_goals = [
            g for g in goals if g.get("status") in ("in_progress", "pending")
        ]
        constraints = await self.brain.constraints.list_constraints(limit=50)
        style_card = await self.load_style_card()
        active_rules = await self.brain.rules.active_instructions(chapter_number=chapter_number)
        quality_learning = []
        quality_store = getattr(self.brain, "quality_learning", None)
        if quality_store is not None:
            quality_learning = await quality_store.active_recommendations(
                chapter_number=chapter_number,
                limit=2,  # P1-1 质量整改：quality_learning 从4条降到2条
            )

        previous = await self.load_previous_chapters(
            chapter_number,
            count=3,
            include_rejected=include_rejected,
        )
        payoff_history_chapters = await self.load_previous_chapters(
            chapter_number,
            count=5,  # P1-1 质量整改：payoff_history 从20章降到5章
            include_rejected=include_rejected,
        )
        recap_parts: list[str] = []
        for prev in previous:
            summary = prev.get("summary") or ""
            if summary:
                provisional = "（待复核草稿）" if prev.get("passed_review") is False else ""
                recap_parts.append(
                    f"第{prev.get('chapter_number')}章{provisional}梗概：{summary}"
                )
        last_tail = ""
        previous_transition_contract: dict[str, Any] = {}
        recent_payoff_types: list[str] = []
        recent_payoff_history: list[dict[str, Any]] = []
        if payoff_history_chapters:
            last_text = previous[-1].get("text") or ""
            # The old 400-character tail was too short to carry a scene's
            # actor/location/object state into the next chapter.  Keep a
            # durable transition contract as well as the literal tail.
            last_tail = last_text[-1200:] if last_text else ""
            previous_transition_contract = previous[-1].get("transition_contract") or {}
            if previous[-1].get("passed_review") is False:
                previous_transition_contract = {
                    **previous_transition_contract,
                    "provisional": True,
                    "warning": "上一章尚未通过质量复核；可承接事实，但不得把未确认状态当作真相写死。",
                }
            for previous_chapter in payoff_history_chapters:
                previous_contract = previous_chapter.get("payoff_contract") or {}
                payoff_type = str(previous_contract.get("payoff_type") or "").strip()
                if payoff_type:
                    recent_payoff_types.append(payoff_type)
                if payoff_type or previous_contract.get("payoff_intensity"):
                    # P1-1 质量整改：精简payoff_history，只保留类型和强度
                    recent_payoff_history.append({
                        "chapter_number": previous_chapter.get("chapter_number"),
                        "payoff_type": payoff_type,
                        "payoff_intensity": previous_contract.get("payoff_intensity") or "small",
                    })

        layers = {
            "story_state": {
                "total": overview.get("states", {}).get("total", 0),
                "pending_review": overview.get("states", {}).get("pending_review", 0),
            },
            "characters": [
                {"key": s["key"], "value": s["value"], "confidence": s["confidence"]}
                for s in character_states
            ],
            "world": [
                {"key": s["key"], "value": s["value"], "confidence": s["confidence"]}
                for s in world_states
            ],
            "plot": [
                {"key": s["key"], "value": s["value"], "confidence": s["confidence"]}
                for s in plot_states
            ],
            "global": [
                {"key": s["key"], "value": s["value"]} for s in global_states
            ],
            "active_goals": [
                {
                    "name": g.get("name"),
                    "description": g.get("description"),
                    "progress": g.get("progress") or 0.0,
                    "status": g.get("status"),
                    "target_chapter": g.get("target_chapter"),
                }
                for g in active_goals
            ],
            "constraints": [
                {
                    "name": c.get("name"),
                    "description": c.get("description"),
                    "severity": c.get("severity"),
                    "type": c.get("type"),
                }
                for c in constraints
            ],
            "recap": recap_parts,
            "previous_tail": last_tail,
            # Kept out of the rendered prompt; used only by the deterministic
            # mirror detector after the new chapter is generated.
            "previous_full_text": previous[-1].get("text") if previous else "",
            "previous_transition_contract": previous_transition_contract,
            "recent_payoff_types": recent_payoff_types[-8:],
            "recent_payoff_history": recent_payoff_history[-5:],  # P1-1 质量整改：从20章降到5章
            "style_card": style_card,
            "active_rules": active_rules,
            "quality_learning": quality_learning,
        }

        rendered = self.render(layers)
        # Rough token budgeting: ~1.6 chars per token for mixed zh/en text.
        max_chars = int(token_budget * 1.6)
        truncated = False
        if len(rendered) > max_chars:
            rendered = self._fit_context(layers, max_chars)
            truncated = True

        return {
            "chapter_number": chapter_number,
            "scene_type": scene_type,
            "token_budget": token_budget,
            "context_layers": layers,
            "rendered_context": rendered,
            "rendered_chars": len(rendered),
            "truncated": truncated,
            "previous_chapters": [p.get("chapter_number") for p in previous],
            "previous_titles": [p.get("title") for p in previous if p.get("title")],
        }

    @staticmethod
    def render(layers: dict[str, Any]) -> str:
        """Render context layers into a prompt-ready block."""
        blocks: list[str] = []

        def fmt_state(items: list[dict[str, Any]], title: str) -> None:
            if not items:
                return
            lines = []
            for it in items[:20]:
                value = it.get("value")
                if isinstance(value, dict):
                    text = value.get("summary") or value.get("description") or json.dumps(
                        value, ensure_ascii=False
                    )
                else:
                    text = str(value)
                lines.append(f"- {it['key']}: {text}")
            blocks.append(f"【{title}】\n" + "\n".join(lines))

        fmt_state(layers.get("characters", []), "人物状态")
        fmt_state(layers.get("world", []), "世界设定")
        fmt_state(layers.get("plot", []), "情节状态")

        goals = layers.get("active_goals", [])
        if goals:
            lines = [
                f"- {g.get('name')}（进度 {float(g.get('progress') or 0) * 100:.0f}%"
                + (f"，目标第{g['target_chapter']}章" if g.get("target_chapter") else "")
                + f"）：{g.get('description') or ''}"
                for g in goals[:15]
            ]
            blocks.append("【当前故事目标】\n" + "\n".join(lines))

        constraints = layers.get("constraints", [])
        if constraints:
            lines = [
                f"- [{c.get('severity')}] {c.get('name')}：{c.get('description') or ''}"
                for c in constraints[:20]
            ]
            blocks.append("【必须遵守的约束】\n" + "\n".join(lines))

        transition = layers.get("previous_transition_contract")
        if transition:
            blocks.append(
                "【上一章交接契约（必须优先遵守）】\n"
                + json.dumps(transition, ensure_ascii=False, separators=(",", ":"))
            )

        style_card = layers.get("style_card")
        if style_card:
            blocks.append(
                "【V6作者风格卡（只约束表达，不改变剧情事实）】\n"
                + json.dumps(style_card, ensure_ascii=False, separators=(",", ":"))
            )

        active_rules = layers.get("active_rules") or []
        if active_rules:
            blocks.append(
                "【已验证的低风险写作规则（只处理表达，不改变剧情）】\n"
                + "\n".join(
                    f"- {item.get('instruction') or item.get('code')}"
                    for item in active_rules[:12]
                )
            )

        quality_learning = layers.get("quality_learning") or []
        if quality_learning:
            blocks.append(
                "【本项目正负样本学习提示（达到灰度门槛后才会出现）】\n"
                + "\n".join(
                    f"- {item.get('instruction')}（样本{item.get('sample_count', 0)}，"
                    f"正向率{float(item.get('positive_rate') or 0) * 100:.0f}%）"
                    for item in quality_learning[:2]  # P1-1 质量整改：从4条降到2条
                    if isinstance(item, dict) and item.get("instruction")
                )
            )

        recap = layers.get("recap", [])
        if recap:
            blocks.append("【前情提要】\n" + "\n".join(recap))

        tail = layers.get("previous_tail")
        if tail:
            blocks.append("【上一章结尾原文（用于承接）】\n" + tail)

        return "\n\n".join(blocks) if blocks else "（暂无历史上下文，这是故事的开端）"

    @classmethod
    def _fit_context(cls, layers: dict[str, Any], max_chars: int) -> str:
        """Fit context without dropping the cross-chapter anchors.

        State inventories are compressible; the previous tail, hand-off
        contract, constraints and recap are not.  The previous implementation
        sliced the fully-rendered prompt from character zero, which commonly
        removed exactly those anchors.
        """
        anchor_layers = {
            "active_goals": layers.get("active_goals", []),
            "constraints": layers.get("constraints", []),
            "recap": layers.get("recap", []),
            "previous_transition_contract": layers.get("previous_transition_contract", {}),
            "previous_tail": layers.get("previous_tail", ""),
            "style_card": layers.get("style_card", {}),
            "active_rules": layers.get("active_rules", []),
            "quality_learning": layers.get("quality_learning", []),
        }
        anchor = cls.render(anchor_layers)
        state_blob = cls.render(
            {
                "characters": layers.get("characters", [])[:40],
                "world": layers.get("world", [])[:40],
                "plot": layers.get("plot", [])[:40],
            }
        )
        if len(anchor) >= max_chars:
            # Keep the literal tail and contract even if a pathological story
            # has an enormous constraint list.
            tail = str(layers.get("previous_tail") or "")[-1200:]
            contract = json.dumps(
                layers.get("previous_transition_contract") or {},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            required = "【上一章交接契约】\n" + contract + "\n\n【上一章结尾原文】\n" + tail
            return required[-max_chars:]
        available = max_chars - len(anchor) - 2
        if available <= 0:
            return anchor
        if len(state_blob) > available:
            state_blob = state_blob[:available] + "\n【设定状态其余条目见 Novel Brain，禁止据此改写已确认事实】"
        return state_blob + "\n\n" + anchor


class SceneDirector:
    """Plans the chapter beat sheet with a real AI call."""

    def __init__(self, brain: NovelBrain, gateway: "AIGateway"):
        self.brain = brain
        self.gateway = gateway

    @staticmethod
    def _adopt_plot_brief(
        chapter_number: int,
        target_word_count: int,
        plot_brief: dict[str, Any] | None,
        previous_titles: list[Any] | None = None,
    ) -> dict[str, Any] | None:
        """Turn a plot-engine brief into a beat sheet, or None if unusable."""
        if not plot_brief:
            return None
        beats = plot_brief.get("suggested_beats") or []
        if len(beats) < 4:
            return None

        normalised: list[dict[str, Any]] = []
        for beat in beats:
            if not isinstance(beat, dict) or not beat.get("name"):
                return None
            normalised.append({
                "name": str(beat.get("name"))[:80],
                "purpose": str(beat.get("purpose") or beat.get("emotion") or "")[:120],
                "content": str(beat.get("content") or "")[:600],
                "emotion": beat.get("emotion"),
                "target_words": int(beat.get("target_words") or 0),
                # PlotEngine emits these labels as part of the commercial
                # beat contract. Preserve them when adopting the brief;
                # dropping them here made the downstream writer infer a
                # different arc and could erase the build phase.
                "payoff_phase": beat.get("payoff_phase"),
                "payoff_phases": beat.get("payoff_phases"),
            })

        planned = sum(b["target_words"] for b in normalised)
        if planned <= 0:
            share = target_word_count // len(normalised)
            for b in normalised:
                b["target_words"] = share
        elif abs(planned - target_word_count) > target_word_count * 0.5:
            # Rescale rather than discard: the shape is useful, the sizing is not.
            factor = target_word_count / planned
            for b in normalised:
                b["target_words"] = max(200, int(b["target_words"] * factor))

        objectives = plot_brief.get("must_accomplish") or []
        chapter_title = ensure_unique_chapter_title(
            plot_brief.get("chapter_title_hint") or f"第{chapter_number}章",
            previous_titles=previous_titles,
            chapter_number=chapter_number,
            hints=[
                plot_brief.get("hook"),
                (plot_brief.get("payoff_contract") or {}).get("visible_result"),
                *[beat.get("name") for beat in normalised],
            ],
        )
        return {
            "chapter_number": chapter_number,
            "chapter_title": chapter_title,
            "scene_goal": plot_brief.get("tension_target")
            or (objectives[0] if objectives else ""),
            "beats": normalised,
            "pov_character": plot_brief.get("pov_character"),
            "pov_policy": "third_person_narrative",
            "pacing": plot_brief.get("pacing_advice"),
            "conflict": plot_brief.get("tension_target"),
            "hook": plot_brief.get("hook"),
            "reader_promise": plot_brief.get("reader_promise"),
            "payoff_contract": plot_brief.get("payoff_contract") or {},
            "chapter_type": plot_brief.get("chapter_type") or plot_brief.get("chapter_mode") or "normal",
            "emotional_target": plot_brief.get("emotional_target"),
            "opening_anchor": plot_brief.get("opening_anchor"),
            "risks": plot_brief.get("risks") or [],
            "must_accomplish": objectives,
            "target_word_count": target_word_count,
            "source": "plot_engine_brief",
            "_usage": {"tokens_input": 0, "tokens_output": 0, "cost": 0.0, "model": None},
        }

    async def plan_scene(
        self,
        chapter_number: int,
        context: dict[str, Any],
        *,
        outline: str | None = None,
        target_word_count: int = 3000,
        plot_brief: dict[str, Any] | None = None,
        quality_profile: dict[str, Any] | None = None,
        previous_titles: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Produce a beat sheet. Returns dict including `_usage` for accounting.

        When the Story Director already obtained a usable beat sheet from the
        plot engine's assessment pass, it is adopted directly instead of paying
        for a second planning call that could contradict the first.
        """
        adopted = self._adopt_plot_brief(
            chapter_number,
            target_word_count,
            plot_brief,
            previous_titles=previous_titles,
        )
        if adopted is not None:
            return adopted

        brief_block = ""
        if plot_brief:
            objectives = plot_brief.get("must_accomplish") or []
            if objectives:
                brief_block = (
                    "\n【结构编辑给出的本章目标】\n"
                    + "\n".join(f"- {o}" for o in objectives[:6])
                    + f"\n张力目标：{plot_brief.get('tension_target') or '未指定'}"
                    + f"\n节奏建议：{plot_brief.get('pacing_advice') or '未指定'}\n"
                )

        quality_directive = compile_quality_directive(
            quality_profile,
            chapter_number=chapter_number,
            chapter_function=plot_brief or {},
            payoff_contract=(plot_brief or {}).get("payoff_contract") if plot_brief else None,
            active_rules=(context.get("context_layers") or {}).get("active_rules") or [],
        )

        prompt = (
            f"你是小说的场景导演。请为第 {chapter_number} 章设计场景结构。\n\n"
            f"{context.get('rendered_context', '')}\n\n"
            f"本章大纲/要求：{outline or '（无，请依据故事目标自行推进）'}\n"
            f"{brief_block}\n"
            f"目标字数：{target_word_count} 字。\n\n"
            f"【网文质量策略】\n{quality_directive}\n\n"
            "请只输出 JSON，格式：\n"
            "{\n"
            '  "chapter_title": "本章标题",\n'
            '  "scene_goal": "本章要达成的叙事目的",\n'
            '  "chapter_type": "normal|aftermath|relationship|suspense",\n'
            '  "beats": [{"name":"节拍名","purpose":"作用","content":"要写什么",'
            '"emotion":"情绪","target_words":800,"payoff_phase":"pressure|build|burst|feedback|aftershock"}],\n'
            '  "pov_character": "视角人物",\n'
            '  "pov_policy": "third_person_narrative",\n'
            '  "pacing": "slow|medium|fast",\n'
            '  "conflict": "本章核心冲突",\n'
            '  "hook": "章末钩子",\n'
            '  "reader_promise": "读者在本章应获得的情绪/信息承诺",\n'
            '  "emotional_target": "开场情绪 -> 中段转折 -> 章末情绪",\n'
            '  "opening_anchor": "与上一章尾部衔接的具体动作/地点/未决问题",\n'
            '  "payoff_contract": {"reader_promise":"读者本章要等什么","pressure":"当前压力",'
            '"active_choice":"主角主动选择","payoff_type":"兑现类型",'
            '"visible_result":"正文中必须出现的可见结果","payoff_feedback":"对手/组织/资源/规则/旁观者的可见反馈",'
            '"payoff_intensity":"small|medium|high|peak","payoff_arc":["pressure","build","burst","feedback","aftershock"],'
            '"witness_reaction":"可选的具体他人反应","cost":"代价或余波",'
            '"next_pressure":"章末新增压力","setup_refs":[]},\n'
            '  "payoff_phases": ["pressure", "build", "burst", "feedback", "aftershock"],\n'
            '  "confidence": 0.85\n'
            "}\n"
            "beats 数量 4-6 个，各 beat 的 target_words 之和应接近目标字数；每个 beat 必须增加 payoff_phase 或 payoff_phases，"
            "严格覆盖 pressure/build/burst/feedback/aftershock 五个阶段，允许一个 beat 承担两个阶段；"
            "至少有一个 beat 明确写 build（压制后的试探、准备、取舍或蓄力），不能把连续的压力描述冒充 build。"
            "chapter_title 必须是 2-12 字的事件、物件、冲突或情绪短标题；"
            # 番茄爽文加码：章节标题番茄化
            "chapter_title 必须有番茄感：要有钩子、有冲突、有悬念，不能太平淡、太文学；"
            "好的章节标题：让读者一眼就想点进去，知道这章有好戏看；"
            "差的章节标题：太平淡，读完没感觉，不知道这章讲什么；"
            "章节标题范式：冲突前置型（《他居然敢动手》）、反转型（《废物竟是大佬》）、悬念型（《门后是什么》）、爽点直给型（《全场傻眼》）；"
            "chapter_type 必须从 normal、aftermath、relationship、suspense 中选择；"
            "禁止写成剧情摘要、操作说明或元叙述，禁止出现‘第X章’、‘本章’、"
            "‘主角在……发现……’、‘读者将……’等模板。"
        )
        result = await self.gateway.generate_json(
            prompt,
            system_prompt=(
                "你是资深小说结构编辑，只输出严格合法的 JSON。"
                + third_person_generation_contract()
                + content_generation_contract(quality_profile)
            ),
            max_tokens=2000,
            temperature=0.6,
            prompt_name="v7.generation.scene_plan",
            prompt_version="1.3.0",
        )
        plan = result["data"]
        # The planner can choose the focal character, never the product-wide
        # narrative mode.  This prevents a learned/project POV field from
        # silently re-enabling first-person prose.
        plan["pov_policy"] = "third_person_narrative"
        plan["chapter_title"] = ensure_unique_chapter_title(
            plan.get("chapter_title") or f"第{chapter_number}章",
            previous_titles=previous_titles,
            chapter_number=chapter_number,
            hints=[plan.get("hook"), plan.get("scene_goal"), plan.get("conflict")],
        )
        plan.setdefault("beats", [])
        plan["chapter_number"] = chapter_number
        plan["chapter_type"] = str(plan.get("chapter_type") or "normal").strip().lower()
        if plan["chapter_type"] not in {"normal", "aftermath", "relationship", "suspense"}:
            plan["chapter_type"] = "normal"
        plan["target_word_count"] = target_word_count
        plan["_usage"] = result["usage"]
        return plan


class DeAIPipeline:
    """Rule pre-clean plus a real semantic final-humanize pass.

    Regexes can remove a few visible clichés, but they cannot fix cadence,
    voice or the over-explained feeling the quality report identified.  The
    final pass therefore goes through the same real V7 provider gateway as the
    rest of generation.  Provider failure is explicit; the rule pass is not a
    fake success fallback.
    """

    # Layer 1: AI 腔套话
    CLICHE_PATTERNS: list[tuple[str, str]] = [
        (r"值得一提的是[，,]?", ""),
        (r"总而言之[，,]?", ""),
        (r"综上所述[，,]?", ""),
        (r"毫无疑问[，,]?", ""),
        (r"不得不说[，,]?", ""),
        (r"众所周知[，,]?", ""),
        (r"在这个[^，。]{0,8}的世界里[，,]?", ""),
        (r"这一切的一切[，,]?", "这一切"),
        (r"仿佛整个世界都", "像是"),
        (r"心中五味杂陈", "心里说不清是什么滋味"),
        (r"嘴角勾起一抹[^，。]{0,4}的弧度", "嘴角动了动"),
        (r"眼中闪过一丝", "眼里掠过"),
        (r"深深地吸了一口气", "吸了口气"),
        (r"缓缓地", "缓缓"),
        (r"轻轻地", "轻轻"),
        (r"默默地", "默默"),
    ]

    # Layer 5: 半角标点 -> 全角
    PUNCT_MAP = {
        ",": "，",
        ";": "；",
        ":": "：",
        "?": "？",
        "!": "！",
    }
    # Only medium/high signals justify a billable whole-chapter semantic
    # rewrite.  Low-severity observations remain in the metrics and review
    # report, but they are not proof that the prose needs a provider pass.
    # In particular, a deliberate repeated phrase or a small amount of
    # ellipsis is common in web fiction and should not erase the author's
    # voice merely because a detector noticed it.
    # P0-1 质量整改：恢复去AI味语义重写，把之前性能优化删掉的flag加回来
    SEMANTIC_REWRITE_FLAGS = {
        "dash_density",
        "ellipsis_density",          # P0-1: 恢复省略号密度检测
        "uniform_cadence",
        "repeated_paragraph_opening",
        "ai_phrase",
        "repeated_phrase",           # P0-1: 恢复重复短语检测
        "repeated_tic",
    }
    # P0-1 质量整改：降低语义重写触发门槛，low级别也触发
    SEMANTIC_REWRITE_SEVERITIES = {"low", "medium", "high"}
    DETERMINISTIC_HARD_FLAGS = {
        "dash_density",
        "uniform_cadence",
        "repeated_paragraph_opening",
        "duplicate_paragraph",
        "ai_phrase",
        "repeated_tic",
    }

    def __init__(self, gateway: "AIGateway | None" = None):
        self.gateway = gateway

    @classmethod
    def _deterministic_fallback_gate(
        cls,
        metrics: dict[str, Any],
        message: str,
    ) -> dict[str, Any]:
        """Decide whether a safe rule-only result can stand in for semantic rewrite.

        A malformed/oversized provider candidate is not itself proof that the
        chapter is bad. The deterministic pass may already have removed the
        actual high-risk patterns. Keep that distinction visible: a clean
        fallback is accepted with a warning; a fallback that still contains a
        hard signal remains blocked.
        """
        blocking_flags = [
            str(flag.get("code"))
            for flag in (metrics.get("flags") or [])
            if isinstance(flag, dict)
            and str(flag.get("code") or "") in cls.DETERMINISTIC_HARD_FLAGS
            and str(flag.get("severity") or "").lower() in {"medium", "high"}
        ]
        risk_score = int(metrics.get("risk_score") or 0)
        passed = not blocking_flags and risk_score < 70
        gate = {
            "passed": passed,
            "mode": "deterministic_fallback",
            "message": message,
            "warning": message,
            "risk_score": risk_score,
        }
        if passed:
            gate["code"] = "semantic_rewrite_unavailable"
        else:
            gate["code"] = "rewrite_candidate_rejected"
            gate["blocking_flags"] = sorted(set(blocking_flags))
        return gate

    @staticmethod
    def _paragraph_opening_guidance(metrics: dict[str, Any] | None) -> str:
        """Turn a repeated-opening signal into a concrete rewrite instruction."""
        opening = (metrics or {}).get("repeated_paragraph_opening") or {}
        ratio = float(opening.get("ratio") or 0.0)
        if ratio < 0.30 or not opening.get("opening"):
            return ""
        return (
            "【段首结构修复】检测到段落开头重复："
            f"‘{opening.get('opening')}’约占 {ratio:.1%}。"
            "定稿必须保留全部事件、人物和自然分段，把一部分段落改为从动作、环境、物件、对白或他人反应起笔，"
            "将同一人名段首尽量降到全章约四分之一以内；不能删段，也不能把人名全部粗暴替换成‘他/她’。"
        )

    @staticmethod
    def _tic_guidance(metrics: dict[str, Any] | None) -> str:
        """Turn repeated action/response tics into a bounded rewrite instruction."""
        tic = (metrics or {}).get("tic_metrics") or {}
        repeated = bool(tic.get("repeated"))
        phrase = str(tic.get("dominant") or "").strip()
        count = int(tic.get("dominant_count") or 0)
        if not repeated or not phrase:
            return ""
        return (
            "【动作短语去模板】检测到动作/反应短语"
            f"‘{phrase}’出现约 {count} 次。保留必要的沉默或反应，"
            "但至少改写其中一处为具体的视线、手部动作、停顿后的决定、声音变化或环境后果；"
            "不得删掉事件，也不要把它机械替换成另一个单一口头禅。"
        )

    @staticmethod
    def _deterministic_paragraph_opening_repair(
        text: str,
        opening: str,
        *,
        max_ratio: float = 0.25,
    ) -> tuple[str, dict[str, Any]]:
        """Safely reduce repeated named-character paragraph openings.

        A targeted Provider repair is preferred because it can choose a more
        natural action or object lead.  If that small request returns an empty
        or malformed result, however, the whole chapter must not be rejected
        when a lossless local repair is possible.  This fallback only changes
        a few leading occurrences of a specific two-character name to the
        neutral third-person pronoun ``他``; it never merges, deletes, or
        invents paragraphs and it skips quoted dialogue openings.
        """
        source = str(text or "")
        opening = str(opening or "").strip()
        evidence: dict[str, Any] = {
            "mode": "deterministic",
            "opening": opening,
            "applied": False,
            "replaced_count": 0,
            "before_ratio": 0.0,
            "after_ratio": 0.0,
            "reason": "",
        }
        if len(opening) != 2 or opening[0] in "他她它我你":
            evidence["reason"] = "generic_or_unsupported_opening"
            return source, evidence

        segments = re.split(r"(\n+)", source)
        paragraph_indexes = [
            index
            for index in range(0, len(segments), 2)
            if segments[index].strip()
        ]
        total = len(paragraph_indexes)
        if total < 12:
            evidence["reason"] = "too_few_paragraphs"
            return source, evidence

        quote_starts = ('"', "“", "”", "‘", "’", "「", "」", "『", "』")
        matches: list[int] = []
        for index in paragraph_indexes:
            paragraph = segments[index]
            leading = paragraph[: len(paragraph) - len(paragraph.lstrip())]
            body = paragraph[len(leading) :]
            if body.startswith(quote_starts):
                continue
            if body.startswith(opening) and len(body) > len(opening):
                matches.append(index)

        before_count = len(matches)
        evidence["before_count"] = before_count
        evidence["before_ratio"] = round(before_count / total, 4) if total else 0.0
        allowed = max(1, int(total * max_ratio))
        required = max(0, before_count - allowed)
        if required <= 0:
            evidence["after_ratio"] = evidence["before_ratio"]
            evidence["reason"] = "already_within_target"
            return source, evidence

        # Keep the first named opening for clarity and spread replacements
        # through the chapter instead of changing one contiguous block.
        candidates = matches[1:]
        selected_positions: list[int] = []
        if required >= len(candidates):
            selected_positions = list(range(len(candidates)))
        elif required == 1:
            selected_positions = [len(candidates) // 2]
        else:
            for step in range(required):
                position = round(step * (len(candidates) - 1) / (required - 1))
                if position not in selected_positions:
                    selected_positions.append(position)
        selected = {candidates[position] for position in selected_positions}

        replaced = 0
        for index in selected:
            paragraph = segments[index]
            leading = paragraph[: len(paragraph) - len(paragraph.lstrip())]
            body = paragraph[len(leading) :]
            if not body.startswith(opening) or len(body) <= len(opening):
                continue
            segments[index] = leading + "他" + body[len(opening) :]
            replaced += 1

        repaired = "".join(segments)
        after_metrics = analyze_deai_patterns(repaired)
        after_opening = after_metrics.get("repeated_paragraph_opening") or {}
        after_ratio = float(after_opening.get("ratio") or 0.0)
        evidence.update({
            "applied": replaced > 0 and after_ratio < 0.30,
            "replaced_count": replaced,
            "after_count": after_opening.get("count", 0),
            "after_ratio": round(after_ratio, 4),
            "reason": "ok" if replaced > 0 and after_ratio < 0.30 else "target_not_reached",
        })
        return repaired if evidence["applied"] else source, evidence

    async def process(
        self,
        text: str,
        *,
        source_facts: str = "",
        forbidden_changes: str = "",
        quality_retry_feedback: str = "",
        style_profile: str = "",
        quality_profile: dict[str, Any] | None = None,
        payoff_contract: dict[str, Any] | None = None,
        safe_deduplicate: bool = False,
        active_rules: list[Any] | None = None,
        force_semantic_rewrite: bool = False,
    ) -> dict[str, Any]:
        """Run rule pre-clean and semantic humanization.

        The semantic output must retain nearly all source material and
        paragraph structure.  If it does not, fail the generation instead of
        silently returning the weaker heuristic result.
        """
        original = text
        before_metrics = analyze_deai_patterns(text, profile=quality_profile)
        layers: list[dict[str, Any]] = []

        text, n = self._layer_cliches(text)
        layers.append({"layer": "cliche_removal", "changes": n})

        text, n = self._layer_dashes(text)
        layers.append({"layer": "dash_ellipsis_normalize", "changes": n})

        text, n = self._layer_parallel(text)
        layers.append({"layer": "parallel_structure_break", "changes": n})

        text, n = self._layer_repetition(text)
        layers.append({"layer": "repetition_reduction", "changes": n})

        text, n = self._layer_punctuation(text)
        layers.append({"layer": "punctuation_normalize", "changes": n})

        text, n = self._layer_paragraph(text)
        layers.append({"layer": "paragraph_rhythm", "changes": n})

        text, n = self._layer_trailing_moral(text)
        layers.append({"layer": "trailing_moral_removal", "changes": n})

        # Provider retries occasionally append an exact second copy of the
        # paragraph stream.  In the canonical generation path this repair is
        # safe because it removes only exact full-paragraph duplicates and
        # keeps the first occurrence; the evidence is retained for audit.
        dedup_evidence: dict[str, Any] = {}
        if safe_deduplicate:
            text, dedup_evidence = deduplicate_full_paragraphs(text)
            removed = int(dedup_evidence.get("removed_paragraphs") or 0)
            layers.append({
                "layer": "exact_duplicate_paragraph_repair",
                "changes": removed,
                "applied": bool(removed),
                "evidence": dedup_evidence,
            })

        # Do not send every chapter through a whole-chapter semantic rewrite.
        # A clean chapter should keep its original voice; the provider pass is
        # reserved for measured risks that deterministic rules cannot safely
        # repair.  This also makes a missing provider an explicit problem only
        # when semantic humanization is actually needed.
        rule_metrics = analyze_deai_patterns(text, profile=quality_profile)
        duplicate_flags = [
            flag
            for flag in rule_metrics.get("flags") or []
            if isinstance(flag, dict) and flag.get("code") == "duplicate_paragraph"
        ]
        semantic_flags = [
            flag
            for flag in rule_metrics.get("flags") or []
            if isinstance(flag, dict)
            and flag.get("code") in self.SEMANTIC_REWRITE_FLAGS
            and str(flag.get("severity") or "").lower()
            in self.SEMANTIC_REWRITE_SEVERITIES
        ]
        semantic_trigger_flags = sorted(
            {
                str(flag.get("code"))
                for flag in semantic_flags
                if flag.get("code")
            }
        )
        if force_semantic_rewrite and not duplicate_flags and not semantic_flags:
            semantic_trigger_flags = ["forced_local_repair"]
        if duplicate_flags or (not semantic_flags and not force_semantic_rewrite):
            quality_gate: dict[str, Any] = {
                "passed": not duplicate_flags,
                "mode": "deterministic_only",
            }
            if duplicate_flags:
                quality_gate.update(
                    {
                        "code": "duplicate_paragraph",
                        "message": str(duplicate_flags[0].get("message") or "正文存在完整段落重复"),
                    }
                )
            layers.append(
                {
                    "layer": "semantic_final_humanize",
                    "changes": 0,
                    "applied": False,
                    "reason": (
                        "duplicate paragraph detected; semantic rewrite is blocked"
                        if duplicate_flags
                        else "rule-cleaned text is below semantic rewrite trigger"
                    ),
                }
            )
            return {
                "original_text": original,
                "processed_text": text,
                "layers_applied": layers,
                "total_changes": sum(item["changes"] for item in layers),
                "original_chars": chinese_word_count(original),
                "processed_chars": chinese_word_count(text),
                "semantic_humanize": False,
                "humanize_changes": [],
                "ai_patterns_removed": [],
                "metrics": {
                    "before": before_metrics,
                    "after": rule_metrics,
                    "risk_delta": before_metrics["risk_score"] - rule_metrics["risk_score"],
                    "duplicate_repair": dedup_evidence,
                    "semantic_trigger_flags": semantic_trigger_flags,
                },
                "quality_gate": quality_gate,
                "usage": {},
            }

        if self.gateway is None:
            raise AIGatewayError("semantic final_humanize gateway is not configured")
        payoff_contract = payoff_contract if isinstance(payoff_contract, dict) else {}
        protected_payoff_fields = (
            ("主动选择", "active_choice"),
            ("爆发结果", "visible_result"),
            ("可见反馈", "payoff_feedback"),
            ("章末压力", "next_pressure"),
            ("关键证据锚点", "text_anchor"),
        )
        protected_payoff_lines = [
            f"- {label}：{payoff_contract.get(key)}"
            for label, key in protected_payoff_fields
            if payoff_contract.get(key)
        ]
        protected_payoff_block = "\n".join(protected_payoff_lines) or "（本章没有单独提供可保护锚点，以正文事实为准）"
        humanize_prompt = (
            "请对下面这章小说执行最终人文化定稿。只改表达，不改事件、人物、"
            "因果、物品状态或对话信息；保留具体细节和自然分段。按四层检查："
            "结构层打散‘提出观点-解释-总结’的重复段式，场景转换用动作/对白承接，"
            "章末保留悬念而不是总结；句法层减少正式连接词、对称排比和过度完整的解释；"
            "词语层删除高频套话、翻译腔和空泛形容；人物层保留角色口吻与对白潜台词，"
            "用动作和细节承载情绪，不把情绪标签直接说满。原文自然的地方少改，"
            "不得摘要、缩写、新增剧情或机械删成电报句。标点不设禁用清单；"
            "保留有语义必要的破折号、省略号和分号，只处理整章高密度、连续重复或模板化使用。\n\n"
            f"{third_person_generation_contract()}\n"
            f"{content_generation_contract(quality_profile)}\n\n"
            f"【不可变事实】\n{source_facts or '（无额外事实）'}\n\n"
            f"【禁止改动】\n{forbidden_changes or '情节、人物、时间线、设定与对白信息'}\n\n"
            f"【作者文风卡】\n{style_profile or '（暂无作者文风卡）'}\n\n"
            f"【上次质量反馈】\n{quality_retry_feedback or '（首次定稿）'}\n\n"
            f"【本章质量策略】\n{compile_quality_directive(quality_profile, payoff_contract=payoff_contract, active_rules=active_rules)}\n\n"
            f"【AI味候选词库指导】\n{render_ai_flavor_guidance(quality_profile)}\n\n"
            # P1-2 质量整改：调整爽点保护锚点的描述
            # 明确告诉模型：保护的是事实和因果，表达方式可以完全彻底重写
            "【爽点保护锚点】以下内容是本章爽点的核心事实与因果链，必须完整保留：\n"
            "- 保护范围：事件、人物动作、结果、对手反应、资源变化、规则后果、新的压力\n"
            "- 可以做的：表达方式可以完全彻底重写，换说法、换语序、换描写角度都可以\n"
            "- 不能做的：删除、弱化成抽象总结、改成原文没有的事件、降低爽感强度\n"
            "注意：锚点保护的是'发生了什么'和'为什么发生'，不是'怎么说的'；\n"
            "去AI味重写时请大胆改写表达方式，不要只微调措辞导致AI腔残留。\n"
            f"{protected_payoff_block}\n\n"
            "【爽点保真】保留并强化本章已经写出的压制、主动选择、爆发结果、可见反馈和余波；"
            "去 AI 味只改表达，不得把强反馈改成平铺直叙，不得删掉对手态度、资源变化、规则后果或新的压力；"
            "不得为了制造爽点新增原文没有的事件。\n"
            f"{self._paragraph_opening_guidance(rule_metrics)}\n\n"
            f"{self._tic_guidance(rule_metrics)}\n\n"
            f"【原文】\n{text}\n\n"
            "【长度约束】输出必须保留原文全部事件与细节，字符数尽量与原文一致，"
            "不得扩写；与原文相比不得增加超过 10%，不得摘要或新增剧情。\n"
            "输出 JSON：{\"humanized_text\":\"完整正文\","
            "\"changes\":[\"改动说明\"],\"ai_patterns_removed\":[\"消除的痕迹\"]}"
        )
        pre_humanized_text = text
        try:
            ai = await self.gateway.generate_json(
                humanize_prompt,
                system_prompt=(
                    "你是严格的真人网文责任编辑，只输出合法 JSON。"
                    + third_person_generation_contract()
                    + content_generation_contract(quality_profile)
                ),
                max_tokens=max(2400, min(5200, int(chinese_word_count(text) * 1.18))),
                temperature=0.45,
                prompt_name="bootstrap.final_humanize",
                prompt_version="1.3.0",
            )
        except AIGatewayError as exc:
            # A malformed/truncated semantic rewrite is a quality failure, not
            # an HTTP 500.  Keep the deterministic rule-cleaned text intact and
            # surface a blocking flag so StoryDirector's bounded rework loop
            # can retry the whole chapter or persist needs_review truthfully.
            logger.warning(
                "V7 final_humanize provider output invalid; retaining rule-cleaned text (%s)",
                type(exc).__name__,
            )
            after_metrics = analyze_deai_patterns(pre_humanized_text, profile=quality_profile)
            fallback_message = "语义去 AI 改写返回了无效 JSON，已保留规则清洗稿"
            quality_gate = self._deterministic_fallback_gate(
                after_metrics,
                fallback_message,
            )
            if not quality_gate["passed"]:
                after_metrics.setdefault("flags", []).append({
                    "code": "rewrite_candidate_rejected",
                    "severity": "high",
                    "message": fallback_message,
                })
            layers.append({
                "layer": "semantic_final_humanize",
                "changes": 0,
                "applied": False,
                "reason": "provider_invalid_json",
            })
            return {
                "original_text": original,
                "processed_text": pre_humanized_text,
                "layers_applied": layers,
                "total_changes": sum(item["changes"] for item in layers),
                "original_chars": chinese_word_count(original),
                "processed_chars": chinese_word_count(pre_humanized_text),
                "semantic_humanize": False,
                "humanize_changes": [],
                "ai_patterns_removed": [],
                "metrics": {
                    "before": before_metrics,
                    "after": after_metrics,
                    "risk_delta": before_metrics["risk_score"] - after_metrics["risk_score"],
                    "duplicate_repair": dedup_evidence,
                    "semantic_trigger_flags": semantic_trigger_flags,
                },
                "quality_gate": quality_gate,
                "usage": {},
            }

        payload = ai.get("data") or {}
        humanized = str(payload.get("humanized_text") or "").strip()
        try:
            # The provider may accidentally collapse JSON newlines.  Reflow
            # only at sentence boundaries; reject actual content loss.
            text, shape = normalize_and_validate_rewrite(
                pre_humanized_text,
                humanized,
                minimum_chars=50,
            )
            duplicate_stats = duplicate_paragraph_stats(text)
            if float(duplicate_stats.get("duplicate_ratio") or 0.0) >= 0.01:
                raise ValueError(
                    "rewrite candidate contains repeated full paragraphs: "
                    f"ratio={duplicate_stats.get('duplicate_ratio')}"
                )
        except ValueError as exc:
            message = str(exc)
            if not (
                "changed chapter length outside safe range" in message
                or "repeated full paragraphs" in message
            ):
                raise AIGatewayError(f"final_humanize {message}") from exc
            # Preserve the rule-cleaned source, but carry a blocking evidence
            # flag into ReviewEngine.  The director may retry; if retries are
            # exhausted this chapter becomes needs_review, never reviewed.
            logger.warning("V7 final_humanize candidate rejected: %s", message)
            text = pre_humanized_text
            after_metrics = analyze_deai_patterns(text, profile=quality_profile)
            quality_gate = self._deterministic_fallback_gate(
                after_metrics,
                message,
            )
            if not quality_gate["passed"]:
                after_metrics.setdefault("flags", []).append({
                    "code": "rewrite_candidate_rejected",
                    "severity": "high",
                    "message": message,
                })
            layers.append({
                "layer": "semantic_final_humanize",
                "changes": 0,
                "applied": False,
                "reason": message,
            })
            return {
                "original_text": original,
                "processed_text": text,
                "layers_applied": layers,
                "total_changes": sum(item["changes"] for item in layers),
                "original_chars": chinese_word_count(original),
                "processed_chars": chinese_word_count(text),
                "semantic_humanize": False,
                "humanize_changes": [],
                "ai_patterns_removed": [],
                "metrics": {
                    "before": before_metrics,
                    "after": after_metrics,
                    "risk_delta": before_metrics["risk_score"] - after_metrics["risk_score"],
                    "duplicate_repair": dedup_evidence,
                    "semantic_trigger_flags": semantic_trigger_flags,
                },
                "quality_gate": quality_gate,
                "usage": ai.get("usage") or {},
            }
        text, punctuation_changes = self._layer_dashes(text)
        if punctuation_changes:
            layers.append({
                "layer": "post_humanize_dash_density_repair",
                "changes": punctuation_changes,
                "applied": True,
            })
        after_metrics = analyze_deai_patterns(text, profile=quality_profile)
        combined_usage = dict(ai.get("usage") or {})
        opening_repair_gate: dict[str, Any] = {"passed": True, "mode": "not_needed"}
        opening_repair_usage: dict[str, Any] = {}
        opening_risk = after_metrics.get("repeated_paragraph_opening") or {}
        if float(opening_risk.get("ratio") or 0.0) >= 0.30:
            opening_repair_prompt = (
                "只修复下面正文的段落起笔重复，不改剧情。必须保留全部事件、人物、地点、时间、因果、对白、信息和段落数量；"
                "不删段、不合并段、不新增剧情，不把整章改成摘要。"
                f"当前约 {float(opening_risk.get('ratio') or 0.0):.1%} 的段落以‘{opening_risk.get('opening')}’开头，"
                "请只改动部分段落的前几个字，让它们自然地从动作、环境、物件、对白或他人反应起笔，"
                "目标是把同一人名段首降到全章约四分之一以内；不要把人名全部机械换成‘他/她’，保持第三人称限知清晰。"
                "输出完整正文 JSON，不要输出解释。\n\n"
                f"【正文】\n{text}"
            )
            try:
                opening_ai = await self.gateway.generate_json(
                    opening_repair_prompt,
                    system_prompt=(
                        "你是严格的中文网文段落编辑，只做局部起笔修复，只输出合法 JSON。"
                        + third_person_generation_contract()
                    ),
                    max_tokens=max(1800, min(4800, int(chinese_word_count(text) * 1.08))),
                    temperature=0.25,
                    prompt_name="bootstrap.final_humanize_opening_repair",
                    prompt_version="1.1.0",
                )
                opening_candidate = str((opening_ai.get("data") or {}).get("humanized_text") or "").strip()
                opening_candidate, opening_shape = normalize_and_validate_rewrite(
                    text,
                    opening_candidate,
                    minimum_chars=50,
                )
                opening_duplicates = duplicate_paragraph_stats(opening_candidate)
                if float(opening_duplicates.get("duplicate_ratio") or 0.0) >= 0.01:
                    raise ValueError("opening repair candidate contains repeated full paragraphs")
                opening_after = analyze_deai_patterns(opening_candidate, profile=quality_profile)
                opening_after_risk = opening_after.get("repeated_paragraph_opening") or {}
                opening_repair_usage = opening_ai.get("usage") or {}
                for key in ("tokens_input", "tokens_output", "cost"):
                    primary = combined_usage.get(key) or 0
                    extra = opening_repair_usage.get(key) or 0
                    combined_usage[key] = primary + extra
                combined_usage["model"] = opening_repair_usage.get("model") or combined_usage.get("model")
                if float(opening_after_risk.get("ratio") or 0.0) >= 0.30:
                    raise ValueError(
                        "opening repair did not reduce repeated paragraph opening below the hard gate"
                    )
                text = opening_candidate
                after_metrics = opening_after
                opening_repair_gate = {
                    "passed": True,
                    "mode": "targeted",
                    "before_ratio": opening_risk.get("ratio"),
                    "after_ratio": opening_after_risk.get("ratio"),
                    "shape": opening_shape,
                }
                layers.append({
                    "layer": "targeted_paragraph_opening_repair",
                    "changes": 1,
                    "applied": True,
                    "before_ratio": opening_risk.get("ratio"),
                    "after_ratio": opening_after_risk.get("ratio"),
                    "usage": opening_repair_usage,
                })
            except (AIGatewayError, ValueError) as exc:
                fallback_text, fallback_evidence = self._deterministic_paragraph_opening_repair(
                    text,
                    str(opening_risk.get("opening") or ""),
                )
                if fallback_evidence.get("applied"):
                    text = fallback_text
                    after_metrics = analyze_deai_patterns(text, profile=quality_profile)
                    opening_repair_gate = {
                        **fallback_evidence,
                        "passed": True,
                        "mode": "deterministic_fallback",
                        "provider_error": str(exc),
                    }
                else:
                    opening_repair_gate = {
                        "passed": False,
                        "mode": "targeted",
                        "code": "repeated_paragraph_opening",
                        "message": str(exc),
                        "before_ratio": opening_risk.get("ratio"),
                        "fallback": fallback_evidence,
                    }
                layers.append({
                    "layer": "targeted_paragraph_opening_repair",
                    "changes": 0,
                    "applied": False,
                    "reason": str(exc),
                    "usage": opening_repair_usage,
                })
                if fallback_evidence.get("applied"):
                    layers.append({
                        "layer": "deterministic_paragraph_opening_repair",
                        "changes": int(fallback_evidence.get("replaced_count") or 0),
                        "applied": True,
                        "evidence": fallback_evidence,
                    })
        layers.append(
            {
                "layer": "semantic_final_humanize",
                "changes": len(payload.get("changes") or []),
                "patterns_removed": payload.get("ai_patterns_removed") or [],
                "shape": shape,
                "usage": combined_usage,
            }
        )

        total = sum(item["changes"] for item in layers)
        return {
            "original_text": original,
            "processed_text": text,
            "layers_applied": layers,
            "total_changes": total,
            "original_chars": chinese_word_count(original),
            "processed_chars": chinese_word_count(text),
            "semantic_humanize": True,
            "humanize_changes": payload.get("changes") or [],
            "ai_patterns_removed": payload.get("ai_patterns_removed") or [],
            "metrics": {
                "before": before_metrics,
                "after": after_metrics,
                "risk_delta": before_metrics["risk_score"] - after_metrics["risk_score"],
                "duplicate_repair": dedup_evidence,
                "semantic_trigger_flags": semantic_trigger_flags,
            },
            "quality_gate": opening_repair_gate,
            "usage": combined_usage,
        }

    def _layer_cliches(self, text: str) -> tuple[str, int]:
        count = 0
        for pattern, repl in self.CLICHE_PATTERNS:
            text, n = re.subn(pattern, repl, text)
            count += n
        return text, count

    def _layer_dashes(self, text: str) -> tuple[str, int]:
        count = 0
        text, n = re.subn(r"-{2,}", "——", text)
        count += n
        text, n = re.subn(r"\.{3,}", "……", text)
        count += n
        text, n = re.subn(r"。{2,}", "。", text)
        count += n
        text, n = re.subn(r"(——){2,}", "——", text)
        count += n
        # Keep punctuation expressive, but do not let a chapter become a
        # repeated interruption template. Only chapters long enough to make a
        # density signal meaningful are touched; the first natural dashes are
        # preserved and only excess occurrences become commas.
        compact_size = len(re.sub(r"\s+", "", text))
        if compact_size >= 600:
            dash_limit = max(3, int(compact_size / 1000 * 5))
            seen = 0

            def replace_excess(match: re.Match[str]) -> str:
                nonlocal count, seen
                seen += 1
                if seen <= dash_limit:
                    return match.group(0)
                count += 1
                return "，"

            text = re.sub(r"——|—", replace_excess, text)
        return text, count

    PRONOUNS = "他她它我你"

    def _layer_parallel(self, text: str) -> tuple[str, int]:
        """Merge 3 consecutive short clauses that all open with the same pronoun.

        "他知道A。他知道B。他知道C。" -> "他知道A，知道B，也知道C。"
        Only a leading single-character pronoun is dropped, so no word can be
        broken apart.
        """
        count = 0
        out_paras: list[str] = []
        for para in text.split("\n"):
            clauses = [c for c in re.split(r"(?<=[。！？])", para) if c]
            i = 0
            while i + 2 < len(clauses):
                window = [clauses[i], clauses[i + 1], clauses[i + 2]]
                stripped = [c.strip() for c in window]
                head = stripped[0][:1] if stripped[0] else ""
                if (
                    head in self.PRONOUNS
                    and all(s.startswith(head) for s in stripped)
                    and all(4 < len(s) <= 30 for s in stripped)
                    and all(s[1:2] not in "们的" for s in stripped)
                ):
                    first = re.sub(r"[。！？]$", "，", stripped[0])
                    second = re.sub(r"[。！？]$", "，", stripped[1][1:])
                    third = "也" + stripped[2][1:]
                    clauses[i : i + 3] = [first + second + third]
                    count += 1
                    i += 1
                else:
                    i += 1
            out_paras.append("".join(clauses))
        return "\n".join(out_paras), count

    # Intensifiers the model likes to stutter on.
    STUTTER_WORDS = ("非常", "十分", "真的", "突然", "忽然", "渐渐", "慢慢")

    def _layer_repetition(self, text: str) -> tuple[str, int]:
        """Collapse artefact repetitions without touching legitimate ABAB forms."""
        count = 0
        # 3+ repeats of the same 2-4 char unit is always an artefact.
        text, n = re.subn(r"([\u4e00-\u9fa5]{2,4})\1{2,}", r"\1", text)
        count += n
        # Doubled intensifiers ("非常非常") are AI stutter, not style.
        for word in self.STUTTER_WORDS:
            text, n = re.subn(f"(?:{word}){{2,}}", word, text)
            count += n
        text, n = re.subn(r"的{2,}", "的", text)
        count += n
        return text, count

    def _layer_punctuation(self, text: str) -> tuple[str, int]:
        """Convert half-width punctuation only when it sits in Chinese context."""
        count = 0
        chars = list(text)

        def is_cjk(ch: str) -> bool:
            return bool(ch) and "\u4e00" <= ch <= "\u9fa5"

        for idx, ch in enumerate(chars):
            if ch not in self.PUNCT_MAP:
                continue
            prev_ch = chars[idx - 1] if idx > 0 else ""
            next_ch = chars[idx + 1] if idx + 1 < len(chars) else ""
            if is_cjk(prev_ch) or is_cjk(next_ch):
                chars[idx] = self.PUNCT_MAP[ch]
                count += 1

        text = "".join(chars)
        text, n = re.subn(r"[ \t]+(?=[\u4e00-\u9fa5])", "", text)
        count += n
        return text, count

    def _layer_paragraph(self, text: str) -> tuple[str, int]:
        """Split paragraphs longer than 220 chars at a sentence boundary."""
        count = 0
        out: list[str] = []
        for para in text.split("\n"):
            stripped = para.strip()
            if len(stripped) <= 220:
                out.append(para)
                continue
            sentences = re.findall(r"[^。！？]*[。！？]", stripped) or [stripped]
            buf = ""
            pieces: list[str] = []
            for s in sentences:
                if len(buf) + len(s) > 180 and buf:
                    pieces.append(buf)
                    buf = s
                else:
                    buf += s
            if buf:
                pieces.append(buf)
            if len(pieces) > 1:
                count += len(pieces) - 1
            out.extend(pieces)
        return "\n".join(out), count

    def _layer_trailing_moral(self, text: str) -> tuple[str, int]:
        """Drop the AI habit of closing with a summarising moral sentence."""
        count = 0
        paras = [p for p in text.split("\n")]
        while paras and not paras[-1].strip():
            paras.pop()
        if paras:
            last = paras[-1].strip()
            if len(last) < 90 and re.search(
                r"(或许|也许|然而)?[^。]*(明白了|懂得了|意味着|注定|命运的齿轮|故事才刚刚开始)[^。]*。$",
                last,
            ) and re.search(r"(懂得了|明白了|命运的齿轮|故事才刚刚开始)", last):
                paras.pop()
                count = 1
        return "\n".join(paras), count


class AIGateway:
    """Async LLM gateway with retry. Raises AIGatewayError instead of faking success."""

    INPUT_PRICE_PER_M = 1.0   # CNY / 1M tokens
    OUTPUT_PRICE_PER_M = 2.0  # CNY / 1M tokens

    def __init__(
        self,
        tracer: ExecutionTracer | None = None,
        *,
        db: AsyncSession | None = None,
        novel_id: uuid.UUID | None = None,
        project_id: str | None = None,
        provider_config: dict[str, str] | None = None,
    ):
        self.tracer = tracer
        self.db = db
        self.novel_id = novel_id
        self.project_id = project_id
        provider_config = provider_config or {}
        self.provider = provider_config.get("provider") or "deepseek"
        self.api_key = provider_config.get("api_key") or os.getenv(
            f"{self.provider.upper()}_API_KEY", ""
        )
        self.base_url = provider_config.get("base_url") or self._default_base_url(self.provider)
        self.default_model = provider_config.get("model") or os.getenv(
            f"{self.provider.upper()}_MODEL", "deepseek-chat"
        )
        self.timeout = float(os.getenv("V7_AI_TIMEOUT", "180"))
        self.max_retries = int(os.getenv("V7_AI_MAX_RETRIES", "3"))
        self._route_resolved = False

    @staticmethod
    def _default_base_url(provider: str) -> str:
        return {
            "deepseek": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            "openai": os.getenv("OPENAI_API_URL", "https://api.openai.com/v1"),
            "claude": os.getenv("CLAUDE_API_URL", "https://api.anthropic.com/v1/messages"),
            "gemini": os.getenv("GEMINI_API_URL", "https://generativelanguage.googleapis.com"),
        }.get(provider, os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"))

    @staticmethod
    def _route_candidates(prompt_name: str | None) -> list[str]:
        """Map V7 prompt names to the editable ``model_routes`` contract."""
        prompt_name = str(prompt_name or "").strip()
        aliases = {
            "v7.review.": "review_7dim",
            # The editor keeps the existing model-route task keys so deployed
            # provider/model configuration remains reusable, but the call
            # itself is owned by the V7 async gateway and is recorded under a
            # V7 prompt name/provenance identity.
            "v7.editor.polish": "editor_polish",
            "v7.editor.rewrite": "editor_rewrite",
            "v7.editor.continue": "editor_continue",
            "v7.editor.deai": "editor_deai",
            "v7.editor.expand": "editor_expand",
            "v7.editor.condense": "editor_condense",
            "v7.generation.chapter": "gen_next_chapter",
            "v7.generation.continuation": "gen_next_chapter",
            "v7.generation.scene_plan": "write_chapter_draft",
            "v7.generation.final_humanize": "final_humanize",
            "v7.generation.chapter_repair": "write_polish",
            "v7.memory.": "extract_story_facts",
            "v7.plot.": "generate_story_arc",
        }
        result = [prompt_name] if prompt_name else []
        for prefix, task_type in aliases.items():
            if prompt_name == prefix or prompt_name.startswith(prefix):
                result.append(task_type)
        return list(dict.fromkeys(result))

    async def _resolve_model_route(self, prompt_name: str | None) -> None:
        """Resolve the actual provider/model from ``model_routes`` once."""
        if self._route_resolved or self.db is None or not hasattr(self.db, "execute"):
            return
        self._route_resolved = True
        for task_type in self._route_candidates(prompt_name):
            try:
                result = await self.db.execute(
                    sql_text(
                        "SELECT provider, model, params FROM model_routes "
                        "WHERE task_type = :task_type AND is_active = TRUE LIMIT 1"
                    ),
                    {"task_type": task_type},
                )
                route = result.mappings().first()
            except Exception:
                # A missing route table or a unit double must not fabricate a
                # result.  The subsequent credential check remains fail-closed.
                return
            if not route:
                continue
            provider = str(route.get("provider") or self.provider)
            self.provider = provider
            self.default_model = str(route.get("model") or self.default_model)
            self.api_key = self.api_key or os.getenv(f"{provider.upper()}_API_KEY", "")
            self.base_url = self._default_base_url(provider)
            return

    async def _assert_budget(self, prompt: str, max_tokens: int) -> None:
        """Block before the provider call when a hard V7 budget is exceeded."""
        if self.db is None or self.novel_id is None:
            return
        from ..cost.cost_manager import BudgetExceededError, CostBudgetManager

        estimated_input = max(1, len(prompt) // 4)
        estimated_tokens = estimated_input + max(1, max_tokens)
        estimated_cost = (
            estimated_input / 1_000_000 * self.INPUT_PRICE_PER_M
            + max(1, max_tokens) / 1_000_000 * self.OUTPUT_PRICE_PER_M
        )
        try:
            await CostBudgetManager(self.db, self.novel_id).assert_within_budget(
                estimated_cost_cny=estimated_cost,
                estimated_tokens=estimated_tokens,
            )
        except BudgetExceededError as exc:
            raise AIGatewayError(str(exc)) from exc

    async def _record_budget_spend(self, usage: dict[str, Any], prompt_name: str | None) -> None:
        """Record provider-reported spend exactly once after a successful call."""
        if self.db is None or self.novel_id is None:
            return
        from ..cost.cost_manager import CostBudgetManager

        run_id = getattr(self.tracer, "_current_run", None) if self.tracer else None
        try:
            await CostBudgetManager(self.db, self.novel_id).record_cost(
                cost_cny=float(usage.get("cost") or 0.0),
                tokens=int(usage.get("tokens_input") or 0) + int(usage.get("tokens_output") or 0),
                run_id=run_id,
                source="v7_ai_gateway",
                description=f"V7 provider call: {prompt_name or 'unattributed'}",
            )
        except Exception as exc:
            # Do not retry the provider after a successful response if the
            # ledger write failed: that would create a second billable call.
            raise BudgetAccountingError(
                f"provider succeeded but V7 cost accounting failed: {type(exc).__name__}"
            ) from exc

    @staticmethod
    def _as_uuid(value: Any) -> uuid.UUID | None:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except (TypeError, ValueError):
            return None

    async def _record_shared_provenance(
        self,
        *,
        prompt: str,
        system_prompt: str,
        history: list[dict[str, str]] | None,
        result: dict[str, Any],
        prompt_name: str | None,
        prompt_version: str | None,
        json_mode: bool,
        attempt: int,
        logical_mutation_id: str,
        started: float,
    ) -> None:
        """Close PromptVersionManager + shared ledger in one V7 transaction."""
        if self.db is None or self.novel_id is None:
            return
        # Unit doubles used for provider/budget tests intentionally do not
        # pretend to be an AsyncSession.  Production sessions expose execute,
        # add and flush; only those sessions may claim durable provenance.
        if not all(hasattr(self.db, attr) for attr in ("execute", "flush")):
            return

        effective_name = (prompt_name or "v7.unattributed").strip() or "v7.unattributed"
        effective_version = normalise_prompt_version(prompt_version)
        run_id = getattr(self.tracer, "_current_run", None) if self.tracer else None
        step_stack = getattr(self.tracer, "_step_stack", []) if self.tracer else []
        step_id = step_stack[-1] if step_stack else None
        exact_hash = prompt_hash(
            prompt,
            system_prompt=system_prompt,
            history=history,
        )
        metadata = {
            "gateway_version": "v7",
            "provider": str(result.get("provider") or self.provider),
            "runtime_managed_prompt": True,
            "rendered_prompt_hash": exact_hash,
            "json_mode": json_mode,
            "attempt": attempt,
            "logical_mutation_id": logical_mutation_id,
        }

        from ..prompt.prompt_manager import PromptVersionManager

        manager = PromptVersionManager(self.db, self.novel_id)
        await manager.record_runtime_execution(
            effective_name,
            version_label=effective_version,
            rendered_prompt=prompt,
            model=str(result.get("model") or self.default_model),
            input_variables={
                "system_prompt": system_prompt,
                "history": history or [],
                "rendered_prompt_hash": exact_hash,
                "json_mode": json_mode,
            },
            output_raw=result.get("text"),
            tokens_input=int(result.get("tokens_input") or 0),
            tokens_output=int(result.get("tokens_output") or 0),
            cost=float(result.get("cost") or 0.0),
            duration_seconds=max(0.0, time.perf_counter() - started),
            status="success",
            run_id=self._as_uuid(run_id),
            step_id=self._as_uuid(step_id),
            novel_id=self.novel_id,
            validation_passed=True,
            extra_metadata=metadata,
        )
        await record_async_execution(
            self.db,
            execution_key=build_execution_key(
                "v7",
                scope=str(self.novel_id),
                client_mutation_id=logical_mutation_id,
                attempt=attempt,
            ),
            gateway_version="v7",
            project_id=self.project_id,
            novel_id=str(self.novel_id),
            run_id=str(run_id) if run_id else None,
            step_id=str(step_id) if step_id else None,
            task_type=effective_name,
            prompt_name=effective_name,
            prompt_version=effective_version,
            rendered_prompt=prompt,
            prompt_hash_value=exact_hash,
            provider=str(result.get("provider") or self.provider),
            model=str(result.get("model") or self.default_model),
            status="succeeded",
            prompt_tokens=int(result.get("tokens_input") or 0),
            completion_tokens=int(result.get("tokens_output") or 0),
            cost_cny=float(result.get("cost") or 0.0),
            latency_ms=int(max(0.0, time.perf_counter() - started) * 1000),
            client_mutation_id=logical_mutation_id,
            metadata=metadata,
        )

    async def _record_failed_provenance(
        self,
        *,
        prompt: str,
        system_prompt: str,
        history: list[dict[str, str]] | None,
        prompt_name: str | None,
        prompt_version: str | None,
        json_mode: bool,
        attempt: int,
        logical_mutation_id: str,
        model_name: str,
        error: Exception,
    ) -> None:
        """Best-effort record of a non-billable failed provider attempt."""
        if self.db is None or self.novel_id is None:
            return
        if not all(hasattr(self.db, attr) for attr in ("execute", "flush")):
            return
        effective_name = (prompt_name or "v7.unattributed").strip() or "v7.unattributed"
        effective_version = normalise_prompt_version(prompt_version)
        run_id = getattr(self.tracer, "_current_run", None) if self.tracer else None
        step_stack = getattr(self.tracer, "_step_stack", []) if self.tracer else []
        step_id = step_stack[-1] if step_stack else None
        exact_hash = prompt_hash(prompt, system_prompt=system_prompt, history=history)
        metadata = {
            "gateway_version": "v7",
            "provider": self.provider,
            "runtime_managed_prompt": True,
            "rendered_prompt_hash": exact_hash,
            "json_mode": json_mode,
            "attempt": attempt,
            "failure": True,
        }

        from ..prompt.prompt_manager import PromptVersionManager

        manager = PromptVersionManager(self.db, self.novel_id)
        await manager.record_runtime_execution(
            effective_name,
            version_label=effective_version,
            rendered_prompt=prompt,
            model=model_name,
            input_variables={
                "system_prompt": system_prompt,
                "history": history or [],
                "rendered_prompt_hash": exact_hash,
                "json_mode": json_mode,
            },
            output_raw=None,
            tokens_input=0,
            tokens_output=0,
            cost=0.0,
            status="failed",
            error_message=str(error)[:2000],
            run_id=self._as_uuid(run_id),
            step_id=self._as_uuid(step_id),
            novel_id=self.novel_id,
            extra_metadata=metadata,
        )
        await record_async_execution(
            self.db,
            execution_key=build_execution_key(
                "v7",
                scope=str(self.novel_id),
                client_mutation_id=logical_mutation_id,
                attempt=attempt,
            ),
            gateway_version="v7",
            project_id=self.project_id,
            novel_id=str(self.novel_id),
            run_id=str(run_id) if run_id else None,
            step_id=str(step_id) if step_id else None,
            task_type=effective_name,
            prompt_name=effective_name,
            prompt_version=effective_version,
            rendered_prompt=prompt,
            prompt_hash_value=exact_hash,
            provider=self.provider,
            model=model_name,
            status="failed",
            error=str(error)[:2000],
            client_mutation_id=logical_mutation_id,
            metadata=metadata,
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str = "你是一个专业的中文小说创作助手。",
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        json_mode: bool = False,
        history: list[dict[str, str]] | None = None,
        prompt_name: str | None = None,
        prompt_version: str | None = None,
        client_mutation_id: str | None = None,
        task_type: str | None = None,
    ) -> dict[str, Any]:
        """Call the LLM. Raises AIGatewayError after all retries fail."""
        await self._resolve_model_route(task_type or prompt_name)
        if not self.api_key:
            raise AIGatewayError(
                f"{self.provider.upper()}_API_KEY is not configured; refusing to fabricate output"
            )

        await self._assert_budget(prompt, max_tokens)

        model = model or self.default_model

        last_error: Exception | None = None
        logical_mutation_id = client_mutation_id or uuid.uuid4().hex
        for attempt in range(1, self.max_retries + 1):
            started = time.perf_counter()
            try:
                # Total-duration hard cap: httpx's ``timeout`` only guards the
                # idle gap between two socket reads, so a slow-but-chatty LLM
                # stream can hang the chapter forever (observed: DeepSeek slow
                # window left generate_chapter stuck >30min with no timeout
                # firing). wrap the whole request in asyncio.wait_for so the
                # call can never exceed ``self.timeout`` wall-clock seconds.
                async def _one_request() -> dict[str, Any]:
                    response = await UnifiedAIGateway(
                        provider=self.provider,
                        api_key=self.api_key,
                        base_url=self.base_url,
                        model=model,
                        timeout=self.timeout,
                    ).complete_async(
                        prompt,
                        system_prompt=system_prompt,
                        history=history,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        json_mode=json_mode,
                        # Keep the existing test seam while the transport is
                        # now owned by the shared V6/V7 gateway.
                        client_factory=httpx.AsyncClient,
                    )
                    return {
                        "content": response.content,
                        "prompt_tokens": response.prompt_tokens,
                        "completion_tokens": response.completion_tokens,
                        "finish_reason": response.finish_reason,
                    }

                result = await asyncio.wait_for(_one_request(), timeout=self.timeout)

                content = result["content"]
                tokens_input = int(result.get("prompt_tokens", 0))
                tokens_output = int(result.get("completion_tokens", 0))
                cost = (
                    tokens_input / 1_000_000 * self.INPUT_PRICE_PER_M
                    + tokens_output / 1_000_000 * self.OUTPUT_PRICE_PER_M
                )
                if not content or not content.strip():
                    raise AIGatewayError("LLM returned empty content")

                result_payload = {
                    "text": content,
                    "provider": self.provider,
                    "model": model,
                    "tokens_input": tokens_input,
                    "tokens_output": tokens_output,
                    "cost": cost,
                    "finish_reason": result.get("finish_reason", "stop"),
                    "attempts": attempt,
                    "prompt_name": prompt_name,
                    "prompt_version": prompt_version,
                }
                await self._record_budget_spend(result_payload, prompt_name)
                try:
                    await self._record_shared_provenance(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        history=history,
                        result=result_payload,
                        prompt_name=prompt_name,
                        prompt_version=prompt_version,
                        json_mode=json_mode,
                        attempt=attempt,
                        logical_mutation_id=logical_mutation_id,
                        started=started,
                    )
                except Exception as exc:
                    # Never retry a billable provider response after either
                    # provenance or the shared ledger failed to close.
                    raise BudgetAccountingError(
                        f"provider succeeded but V7 provenance accounting failed: {type(exc).__name__}"
                    ) from exc
                return result_payload
            except Exception as exc:  # noqa: BLE001 - retried and re-raised below
                last_error = exc
                if isinstance(exc, BudgetAccountingError):
                    break
                if attempt == self.max_retries:
                    try:
                        await self._record_failed_provenance(
                            prompt=prompt,
                            system_prompt=system_prompt,
                            history=history,
                            prompt_name=prompt_name,
                            prompt_version=prompt_version,
                            json_mode=json_mode,
                            attempt=attempt,
                            logical_mutation_id=logical_mutation_id,
                            model_name=model,
                            error=exc,
                        )
                    except Exception:
                        logger.warning(
                            "V7 failed provider provenance could not be persisted",
                            exc_info=True,
                        )
                if attempt < self.max_retries:
                    await asyncio.sleep(min(2 ** attempt, 8))

        raise AIGatewayError(
            f"LLM call failed after {self.max_retries} attempts: {last_error}"
        ) from last_error

    async def generate_json(
        self,
        prompt: str,
        *,
        system_prompt: str = "你是一个严谨的助手，只输出合法 JSON。",
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        prompt_name: str | None = None,
        prompt_version: str | None = None,
        client_mutation_id: str | None = None,
        task_type: str | None = None,
    ) -> dict[str, Any]:
        """Generate and parse a JSON object. Returns {"data":..., "usage":...}."""
        usage_total = {
            "tokens_input": 0,
            "tokens_output": 0,
            "cost": 0.0,
            "model": None,
            "provider": None,
        }
        last_text = ""
        for attempt in range(2):
            result = await self.generate(
                prompt if attempt == 0 else (
                    prompt
                    + "\n\n上一次输出不是合法 JSON，请严格只输出 JSON 对象，不要任何解释、不要代码块标记。"
                ),
                system_prompt=system_prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=True,
                prompt_name=prompt_name,
                prompt_version=prompt_version,
                client_mutation_id=client_mutation_id,
                task_type=task_type,
            )
            usage_total["tokens_input"] += result["tokens_input"]
            usage_total["tokens_output"] += result["tokens_output"]
            usage_total["cost"] += result["cost"]
            usage_total["model"] = result["model"]
            usage_total["provider"] = result.get("provider")
            last_text = result["text"]

            data = self._parse_json(last_text)
            if data is not None:
                return {"data": data, "usage": usage_total, "raw": last_text}

        raise AIGatewayError(
            f"LLM did not return parseable JSON after 2 attempts: {last_text[:200]}"
        )

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any] | None:
        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```[a-zA-Z]*\s*", "", candidate)
            candidate = re.sub(r"\s*```$", "", candidate)
        try:
            data = json.loads(candidate)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None
        return None


class GenerationEngine:
    """Main generation orchestrator: context -> scene plan -> AI text -> de-AI."""

    def __init__(
        self,
        db: AsyncSession,
        novel_id: uuid.UUID,
        brain: NovelBrain,
        tracer: ExecutionTracer,
        event_bus: EventBus,
        project_id: str | None = None,
        provider_config: dict[str, str] | None = None,
        quality_profile: dict[str, Any] | None = None,
    ):
        self.db = db
        self.novel_id = novel_id
        self.brain = brain
        self.tracer = tracer
        self.event_bus = event_bus
        self.project_id = project_id
        self.provider_config = provider_config or {}
        self.quality_profile = quality_profile or select_quality_profile()

        self.ai_gateway = AIGateway(
            tracer,
            db=db,
            novel_id=novel_id,
            project_id=project_id,
            provider_config=self.provider_config,
        )
        self.context_assembler = ContextAssembler(brain, project_id)
        self.scene_director = SceneDirector(brain, self.ai_gateway)
        self.deai_pipeline = DeAIPipeline(self.ai_gateway)

    async def generate_chapter(
        self,
        chapter_number: int,
        *,
        prompt: str | None = None,
        outline: str | None = None,
        target_word_count: int = 3000,
        max_continuations: int = 1,
        plot_brief: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate one chapter with a soft length target and hard quality gates.

        Length is a planning signal, not a reason to append unlimited prose.
        One continuation is allowed only when the first draft is materially
        short; every continuation is checked before it can be appended.
        """
        if not hasattr(self, "quality_profile"):
            self.quality_profile = select_quality_profile()
        usage = {"tokens_input": 0, "tokens_output": 0, "cost": 0.0, "model": None}
        minimum_chapter_chars = max(600, int(target_word_count * 0.72))
        maximum_chapter_chars = max(
            minimum_chapter_chars + 200,
            int(target_word_count * 1.45),
        )
        # DeepSeek's tokenisation can produce substantially more Chinese
        # characters than the nominal token count. A fixed 4000-token cap
        # therefore let a 3000-character chapter expand past the 4350-char
        # product ceiling. Derive the cap from the hard ceiling so the first
        # draft is length-safe instead of relying on a later rejection.
        generation_max_tokens = max(
            900,
            min(3200, int(maximum_chapter_chars * 0.58)),
        )

        def add_usage(step_ctx: Any, u: dict[str, Any]) -> None:
            usage["tokens_input"] += u.get("tokens_input", 0)
            usage["tokens_output"] += u.get("tokens_output", 0)
            usage["cost"] += u.get("cost", 0.0)
            usage["model"] = u.get("model") or usage["model"]
            if step_ctx is not None:
                step_ctx.set_output(
                    tokens_input=u.get("tokens_input", 0),
                    tokens_output=u.get("tokens_output", 0),
                    cost=u.get("cost", 0.0),
                    model=u.get("model"),
                )

        # Step: assemble context
        async with self.tracer.trace_step(
            "generation.assemble_context",
            "context_assembly",
            input_summary=f"Assemble context for chapter {chapter_number}",
        ) as step:
            context = await self.context_assembler.assemble_context(
                chapter_number,
                include_rejected=bool(getattr(self, "include_rejected_context", False)),
            )
            step.set_output(
                f"context {context['rendered_chars']} chars, "
                f"prev={context['previous_chapters']}",
                data={
                    "rendered_chars": context["rendered_chars"],
                    "truncated": context["truncated"],
                    "previous_chapters": context["previous_chapters"],
                },
            )

        # Step: plan scene (real AI)
        async with self.tracer.trace_step(
            "generation.plan_scene",
            "scene_planning",
            input_summary="Plan scene structure with AI",
        ) as step:
            scene_plan = await self.scene_director.plan_scene(
                chapter_number,
                context,
                outline=outline or prompt,
                target_word_count=target_word_count,
                plot_brief=plot_brief,
                quality_profile=self.quality_profile,
                previous_titles=context.get("previous_titles") or [],
            )
            add_usage(step, scene_plan.pop("_usage", {}))
            step.set_output(
                f"{len(scene_plan.get('beats', []))} beats: "
                f"{scene_plan.get('chapter_title')}",
                data={"scene_plan": scene_plan},
                confidence=float(scene_plan.get("confidence", 0.8) or 0.8),
            )

        scene_plan["recent_payoff_types"] = list(
            (context.get("context_layers") or {}).get("recent_payoff_types") or []
        )[-8:]
        scene_plan["recent_payoff_history"] = list(
            (context.get("context_layers") or {}).get("recent_payoff_history") or []
        )[-20:]

        # The payoff contract is a generation input, not only a review field.
        # Normalise it before the writer and humanizer see the chapter so a
        # missing/weak plan cannot be hidden by a later prose score.
        payoff_contract_required = True
        payoff_contract = build_payoff_contract(
            scene_plan.get("payoff_contract") or {},
            chapter_number=chapter_number,
            profile=self.quality_profile,
            recent_types=(context.get("context_layers") or {}).get("recent_payoff_types") or [],
            chapter_function=scene_plan,
        )
        scene_plan["payoff_contract"] = payoff_contract
        payoff_validation = validate_payoff_contract(
            payoff_contract,
            profile=self.quality_profile,
            required=payoff_contract_required,
            chapter_function=scene_plan,
        )
        payoff_variety = validate_payoff_variety(
            payoff_contract.get("payoff_type"),
            scene_plan.get("recent_payoff_types") or [],
            profile=self.quality_profile,
        )
        payoff_beat_repair = repair_payoff_beat_structure(scene_plan.get("beats") or [])
        scene_plan["beats"] = payoff_beat_repair["beats"]
        payoff_beat_validation = payoff_beat_repair["after"]
        scene_plan["payoff_validation"] = payoff_validation
        scene_plan["payoff_variety"] = payoff_variety
        scene_plan["payoff_beat_validation"] = payoff_beat_validation
        scene_plan["payoff_beat_repair"] = payoff_beat_repair

        # Step: AI generation (at most one quality-checked continuation)
        async with self.tracer.trace_step(
            "generation.ai_generate",
            "ai_generation",
            input_summary=f"Generate a complete chapter near {target_word_count} chars with AI",
        ) as step:
            gen_prompt = self._build_generation_prompt(
                chapter_number, context, scene_plan, outline or prompt, target_word_count
            )
            first = await self.ai_gateway.generate(
                gen_prompt,
                system_prompt=(
                    "你是一位专业中文网络小说作者。写作要求：画面感强、对白自然、"
                    "避免总结性旁白与说教结尾、避免翻译腔。直接输出正文，不要标题、"
                    "不要任何解释或markdown标记。标点不设禁用清单，按人物语气和"
                    "场景功能使用；只避免整章高密度、连续重复的模板化符号。"
                    + third_person_generation_contract()
                    + content_generation_contract(self.quality_profile)
                ),
                max_tokens=generation_max_tokens,
                temperature=0.85,
                prompt_name="v7.generation.chapter",
                prompt_version="1.5.0",
            )
            add_usage(step, first)
            text = first["text"].strip()
            # Cheap local preflight before any continuation or semantic
            # humanization call.  The generation prompt is the primary control;
            # this check only prevents spending another Provider request on a
            # draft that already violates the global writing contract.
            raw_pov_metrics = analyze_third_person_narrative(text)
            raw_content_policy = analyze_content_policy(text, self.quality_profile)
            preflight_failures: list[dict[str, Any]] = []
            if not raw_pov_metrics["passed"]:
                preflight_failures.append({
                    "code": "third_person_narrative_required",
                    "severity": "high",
                    "message": "生成初稿的叙述部分出现第一人称；对白/短信中的第一人称不计入。",
                    "evidence": raw_pov_metrics,
                })
            if not raw_content_policy["passed"]:
                preflight_failures.extend(raw_content_policy.get("failures") or [])

            continuations = 0
            continuation_failures: list[dict[str, Any]] = []
            # A chapter that is already close to its target should finish on
            # its hook.  Repeatedly asking for more text is a common source of
            # padding and duplicated paragraphs.
            continuation_limit = min(max(0, int(max_continuations)), 1)
            while (
                not preflight_failures
                and
                chinese_word_count(text) < minimum_chapter_chars
                and continuations < continuation_limit
            ):
                continuations += 1
                missing = target_word_count - chinese_word_count(text)
                continuation_max_tokens = max(
                    900,
                    min(
                        2400,
                        int(
                            max(
                                0,
                                maximum_chapter_chars - chinese_word_count(text),
                            )
                            * 0.58
                        ),
                    ),
                )
                cont = await self.ai_gateway.generate(
                    self._build_continuation_prompt(
                        text, scene_plan, missing, quality_profile=self.quality_profile
                    ),
                    system_prompt=(
                        "你是一位专业中文网络小说作者，正在续写同一章的后半部分。"
                        "直接接着写正文，不要重复已有内容，不要写标题或说明。"
                        "保持自然分段和人物语气；标点按语义使用，不要批量堆叠同一符号。"
                        + third_person_generation_contract()
                        + content_generation_contract(self.quality_profile)
                    ),
                    max_tokens=continuation_max_tokens,
                    temperature=0.85,
                    prompt_name="v7.generation.continuation",
                    prompt_version="1.5.0",
                )
                add_usage(step, cont)
                candidate = text.rstrip() + "\n\n" + cont["text"].strip()
                duplicate_stats = duplicate_paragraph_stats(candidate)
                if (
                    float(duplicate_stats.get("duplicate_ratio") or 0.0) >= 0.01
                    or int(duplicate_stats.get("adjacent_duplicate_count") or 0) > 0
                ):
                    continuation_failures.append(
                        {
                            "code": "continuation_duplicate",
                            "severity": "high",
                            "message": "续写候选与已有正文出现完整段落重复，已丢弃候选",
                            "evidence": duplicate_stats,
                        }
                    )
                    break
                if chinese_word_count(candidate) > maximum_chapter_chars:
                    continuation_failures.append(
                        {
                            "code": "continuation_overflow",
                            "severity": "high",
                            "message": (
                                f"续写候选超过本章最大长度 {maximum_chapter_chars} 字，"
                                "已丢弃候选"
                            ),
                            "candidate_chars": chinese_word_count(candidate),
                        }
                    )
                    break
                text = candidate

            raw_count = chinese_word_count(text)
            step.set_output(
                f"{raw_count} chars, {continuations} continuation(s)",
                data={
                    "raw_word_count": raw_count,
                    "continuations": continuations,
                    "continuation_limit": continuation_limit,
                    "continuation_failures": continuation_failures,
                },
            )

        # Step: de-AI pipeline (real transformations).  If the raw draft
        # already fails a generation-first contract, do not pay for semantic
        # humanization; return the draft for one bounded generation rework.
        async with self.tracer.trace_step(
            "generation.deai_process",
            "deai_processing",
            input_summary="Run 7-layer de-AI pipeline",
        ) as step:
            context_layers = context.get("context_layers") or {}
            if preflight_failures:
                before_metrics = analyze_deai_patterns(text, profile=self.quality_profile)
                deai_result = {
                    "processed_text": text,
                    "layers_applied": [],
                    "total_changes": 0,
                    "semantic_humanize": False,
                    "humanize_changes": [],
                    "ai_patterns_removed": [],
                    "metrics": {
                        "before": before_metrics,
                        "after": before_metrics,
                        "pov": raw_pov_metrics,
                        "content_policy": raw_content_policy,
                    },
                    "quality_gate": {
                        "passed": True,
                        "skipped": True,
                        "reason": "generation_preflight_failed; semantic humanization skipped",
                    },
                    "usage": {},
                }
            else:
                deai_result = await self.deai_pipeline.process(
                    text,
                    source_facts=json.dumps(
                        {
                            "previous_transition_contract": context_layers.get(
                                "previous_transition_contract"
                            ),
                            "previous_tail": context_layers.get("previous_tail"),
                        },
                        ensure_ascii=False,
                    ),
                    forbidden_changes=json.dumps(
                        context_layers.get("constraints") or [], ensure_ascii=False
                    ),
                    style_profile=json.dumps(
                        {
                            **(context_layers.get("style_card") or {}),
                            "active_rules": context_layers.get("active_rules") or [],
                        },
                        ensure_ascii=False,
                    ),
                    quality_profile=self.quality_profile,
                    payoff_contract=payoff_contract,
                    safe_deduplicate=True,
                    active_rules=context_layers.get("active_rules") or [],
                )
            deai_result.setdefault("metrics", {})["pov_preflight"] = raw_pov_metrics
            deai_result.setdefault("metrics", {})["content_policy_preflight"] = raw_content_policy
            add_usage(step, deai_result.get("usage") or {})
            step.set_output(
                f"{deai_result['total_changes']} edits across "
                f"{len(deai_result['layers_applied'])} layers",
                data={"layers": deai_result["layers_applied"]},
            )

        final_text = deai_result["processed_text"]
        word_count = chinese_word_count(final_text)
        generation_failures = [*preflight_failures, *continuation_failures]
        mirror_stats = chapter_mirror_stats(
            final_text,
            previous_text=str(context_layers.get("previous_full_text") or ""),
        )
        # P1-3 质量整改：chapter_mirror 从 hard gate 降为 soft warning
        # 只有当 CHAPTER_MIRROR_HARD_GATE 为 True 时才拦截
        if not mirror_stats.get("passed") and CHAPTER_MIRROR_HARD_GATE:
            generation_failures.append({
                "code": "chapter_mirror",
                "severity": "high",
                "message": "正文与自身前后半段或上一章高度镜像，不能进入完成状态",
                "evidence": mirror_stats,
            })
        if word_count < minimum_chapter_chars:
            generation_failures.append(
                {
                    "code": "chapter_too_short",
                    "severity": "high",
                    "message": (
                        f"最终正文 {word_count} 字，低于本章最低生成阈值 "
                        f"{minimum_chapter_chars} 字"
                    ),
                }
            )
        if word_count > maximum_chapter_chars:
            generation_failures.append(
                {
                    "code": "chapter_too_long",
                    "severity": "high",
                    "message": (
                        f"最终正文 {word_count} 字，超过本章最大生成阈值 "
                        f"{maximum_chapter_chars} 字"
                    ),
                }
            )
        deai_gate = deai_result.get("quality_gate") or {}
        if deai_gate.get("passed") is False:
            generation_failures.append(
                {
                    "code": str(deai_gate.get("code") or "deai_quality_gate_failed"),
                    "severity": "high",
                    "message": str(
                        deai_gate.get("message") or "去 AI 味候选未通过安全校验"
                    ),
                }
            )
        final_pov_metrics = analyze_third_person_narrative(final_text)
        final_content_policy = analyze_content_policy(final_text, self.quality_profile)
        if not final_pov_metrics["passed"] and not any(
            item.get("code") == "third_person_narrative_required" for item in generation_failures
        ):
            generation_failures.append({
                "code": "third_person_narrative_required",
                "severity": "high",
                "message": "最终正文的叙述部分出现第一人称；对白/短信中的第一人称不计入。",
                "evidence": final_pov_metrics,
            })
        for policy_failure in final_content_policy.get("failures") or []:
            if not any(
                item.get("code") == policy_failure.get("code") for item in generation_failures
            ):
                generation_failures.append(policy_failure)
        deai_result.setdefault("metrics", {})["after_pov"] = final_pov_metrics
        deai_result.setdefault("metrics", {})["after_content_policy"] = final_content_policy
        if payoff_contract and not payoff_validation.get("passed"):
            generation_failures.append({
                "code": "payoff_contract_missing",
                "severity": "high",
                "message": "本章爽点契约缺少必要字段：" + "、".join(payoff_validation.get("missing") or []),
            })
        if payoff_contract_required and not payoff_validation.get("strength_passed", True):
            generation_failures.append({
                "code": "payoff_strength_insufficient",
                "severity": "high",
                "message": "本章爽点强度或可见反馈不足：" + "；".join(payoff_validation.get("strength_issues") or []),
                "evidence": payoff_validation,
            })
        if payoff_contract_required and not payoff_beat_validation.get("passed"):
            generation_failures.append({
                "code": "payoff_beat_structure_missing",
                "severity": "high",
                "message": "爽点节拍没有覆盖：" + "、".join(payoff_beat_validation.get("missing_phases") or []),
                "evidence": payoff_beat_validation,
            })
        # P1-3 质量整改：payoff_variety 从 hard gate 降为 soft warning
        # 只有当 PAYOFF_VARIETY_HARD_GATE 为 True 时才拦截
        if payoff_contract_required and not payoff_variety.get("passed") and PAYOFF_VARIETY_HARD_GATE:
            generation_failures.append({
                "code": "payoff_type_repetition",
                "severity": "high",
                "message": payoff_variety.get("issue") or "本章爽点类型重复度过高",
                "evidence": payoff_variety,
            })
        payoff_score = score_payoff_contract(
            payoff_contract,
            profile=self.quality_profile,
            text=final_text,
            recent_types=scene_plan.get("recent_payoff_types") or [],
            recent_history=scene_plan.get("recent_payoff_history") or [],
        )
        generation_quality = {
            "schema_version": "generation-quality-v1",
            "passed": not generation_failures,
            "minimum_chars": minimum_chapter_chars,
            "maximum_chars": maximum_chapter_chars,
            "failures": generation_failures,
            "continuations": continuations,
            "continuation_limit": continuation_limit,
            "pov_metrics": final_pov_metrics,
            "content_policy": final_content_policy,
            "payoff_validation": payoff_validation,
            "payoff_beat_validation": payoff_beat_validation,
            "payoff_beat_repair": payoff_beat_repair,
            "payoff_variety": payoff_variety,
            "payoff_score": payoff_score,
            "chapter_mirror": mirror_stats,
            "quality_profile": quality_profile_metadata(self.quality_profile),
        }

        await self.event_bus.publish(
            "generation_completed",
            f"Chapter {chapter_number} generation completed",
            "generation",
            source="generation_engine",
            event_data={
                "chapter_number": chapter_number,
                "word_count": word_count,
                "tokens": usage["tokens_input"] + usage["tokens_output"],
                "cost": usage["cost"],
                "deai_changes": deai_result["total_changes"],
            },
        )

        return {
            "chapter_number": chapter_number,
            "title": scene_plan.get("chapter_title") or f"第{chapter_number}章",
            "text": final_text,
            "word_count": word_count,
            "target_word_count": target_word_count,
            "meets_target": word_count >= target_word_count,
            "generation_quality": generation_quality,
            "context": {
                "rendered_chars": context["rendered_chars"],
                "previous_chapters": context["previous_chapters"],
                "previous_titles": context.get("previous_titles") or [],
                "previous_tail": context["context_layers"].get("previous_tail", ""),
                "previous_transition_contract": context["context_layers"].get(
                    "previous_transition_contract", {}
                ),
                "constraints": context["context_layers"].get("constraints", []),
                "style_card": context["context_layers"].get("style_card", {}),
                "active_rules": context["context_layers"].get("active_rules", []),
                "recent_payoff_types": context["context_layers"].get("recent_payoff_types", []),
                "recent_payoff_history": context["context_layers"].get("recent_payoff_history", []),
            },
            "scene_plan": scene_plan,
            "payoff_contract": payoff_contract,
            "payoff_validation": payoff_validation,
            "payoff_variety": payoff_variety,
            "payoff_score": payoff_score,
            "chapter_mirror": mirror_stats,
            "pov_metrics": final_pov_metrics,
            "content_policy": final_content_policy,
            "quality_profile": quality_profile_metadata(self.quality_profile),
            "deai": {
                "layers_applied": deai_result["layers_applied"],
                "total_changes": deai_result["total_changes"],
                "semantic_humanize": deai_result.get("semantic_humanize", False),
                "humanize_changes": deai_result.get("humanize_changes", []),
                "ai_patterns_removed": deai_result.get("ai_patterns_removed", []),
                "metrics": deai_result.get("metrics", {}),
                "quality_gate": deai_result.get("quality_gate") or {"passed": True},
            },
            "usage": usage,
        }

    async def repair_local_quality(
        self,
        generation: dict[str, Any],
        *,
        feedback: str,
    ) -> dict[str, Any]:
        """Repair a prose-only defect without regenerating the whole scene.

        StoryDirector uses this only when every failed gate is a local prose
        contract (POV, content policy or deterministic de-AI signal).  The
        Provider still has to return a lossless rewrite through
        ``DeAIPipeline``; length, paragraph shape, POV, content policy and
        the existing quality gate are recomputed before the repaired draft is
        reviewed again.  Structural failures never enter this shortcut.
        """
        context = generation.get("context") or {}
        style_card = context.get("style_card") or {}
        active_rules = context.get("active_rules") or []
        deai_result = await self.deai_pipeline.process(
            generation.get("text") or "",
            source_facts=json.dumps(
                {
                    "previous_transition_contract": context.get(
                        "previous_transition_contract"
                    ),
                    "previous_tail": context.get("previous_tail"),
                },
                ensure_ascii=False,
            ),
            forbidden_changes=json.dumps(
                context.get("constraints") or [], ensure_ascii=False
            ),
            quality_retry_feedback=feedback,
            style_profile=json.dumps(
                {**style_card, "active_rules": active_rules},
                ensure_ascii=False,
            ),
            quality_profile=self.quality_profile,
            payoff_contract=generation.get("payoff_contract") or {},
            safe_deduplicate=True,
            active_rules=active_rules,
            force_semantic_rewrite=True,
        )

        final_text = deai_result.get("processed_text") or generation.get("text") or ""
        word_count = chinese_word_count(final_text)
        previous_quality = generation.get("generation_quality") or {}
        minimum_chars = int(previous_quality.get("minimum_chars") or 600)
        maximum_chars = int(
            previous_quality.get("maximum_chars")
            or max(minimum_chars + 200, int(generation.get("target_word_count") or 3000) * 1.45)
        )
        failures: list[dict[str, Any]] = []
        if word_count < minimum_chars:
            failures.append({
                "code": "chapter_too_short",
                "severity": "high",
                "message": f"修复后正文 {word_count} 字，低于最低阈值 {minimum_chars} 字",
            })
        if word_count > maximum_chars:
            failures.append({
                "code": "chapter_too_long",
                "severity": "high",
                "message": f"修复后正文 {word_count} 字，超过最大阈值 {maximum_chars} 字",
            })
        quality_gate = deai_result.get("quality_gate") or {}
        if quality_gate.get("passed") is False:
            failures.append({
                "code": str(quality_gate.get("code") or "deai_quality_gate_failed"),
                "severity": "high",
                "message": str(quality_gate.get("message") or "去 AI 味修复未通过安全校验"),
            })
        pov_metrics = analyze_third_person_narrative(final_text)
        content_policy = analyze_content_policy(final_text, self.quality_profile)
        if not pov_metrics.get("passed"):
            failures.append({
                "code": "third_person_narrative_required",
                "severity": "high",
                "message": "修复后叙述部分仍出现第一人称；对白/短信中的第一人称不计入。",
                "evidence": pov_metrics,
            })
        failures.extend(content_policy.get("failures") or [])

        generation_quality = {
            **previous_quality,
            "schema_version": "generation-quality-v1",
            "passed": not failures,
            "minimum_chars": minimum_chars,
            "maximum_chars": maximum_chars,
            "failures": failures,
            "pov_metrics": pov_metrics,
            "content_policy": content_policy,
        }
        usage = dict(generation.get("usage") or {})
        repair_usage = deai_result.get("usage") or {}
        for key in ("tokens_input", "tokens_output", "cost"):
            usage[key] = (usage.get(key) or 0) + (repair_usage.get(key) or 0)
        usage["model"] = repair_usage.get("model") or usage.get("model")

        return {
            **generation,
            "text": final_text,
            "word_count": word_count,
            "meets_target": word_count >= int(generation.get("target_word_count") or 0),
            "generation_quality": generation_quality,
            "pov_metrics": pov_metrics,
            "content_policy": content_policy,
            "deai": {
                "layers_applied": deai_result.get("layers_applied") or [],
                "total_changes": deai_result.get("total_changes") or 0,
                "semantic_humanize": deai_result.get("semantic_humanize", False),
                "humanize_changes": deai_result.get("humanize_changes") or [],
                "ai_patterns_removed": deai_result.get("ai_patterns_removed") or [],
                "metrics": deai_result.get("metrics") or {},
                "quality_gate": quality_gate,
            },
            "usage": usage,
        }

    def _build_generation_prompt(
        self,
        chapter_number: int,
        context: dict[str, Any],
        scene_plan: dict[str, Any],
        outline: str | None,
        target_word_count: int,
    ) -> str:
        beats = scene_plan.get("beats") or []
        quality_profile = getattr(self, "quality_profile", None) or select_quality_profile()
        quality_directive = compile_quality_directive(
            quality_profile,
            chapter_number=chapter_number,
            chapter_function=scene_plan,
            payoff_contract=scene_plan.get("payoff_contract") or None,
            active_rules=(context.get("context_layers") or {}).get("active_rules") or [],
        )
        beat_lines = "\n".join(
            f"{i + 1}. {b.get('name')}（约{b.get('target_words', 0)}字，情绪：{b.get('emotion','')}）："
            f"{b.get('content', '')}"
            for i, b in enumerate(beats)
        )
        return (
            f"{context.get('rendered_context', '')}\n\n"
            f"====================\n"
            f"现在写第 {chapter_number} 章：《{scene_plan.get('chapter_title')}》\n"
            f"视角人物：{scene_plan.get('pov_character', '主角')}\n"
            "叙述模式：第三人称限知；对白/短信中的‘我’可以保留，叙述句中的‘我’不可以出现。\n"
            f"核心冲突：{scene_plan.get('conflict', '')}\n"
            f"节奏：{scene_plan.get('pacing', 'medium')}\n"
            f"章节功能类型：{scene_plan.get('chapter_type') or scene_plan.get('chapter_mode') or 'normal'}\n"
            f"读者承诺：{scene_plan.get('reader_promise', '')}\n"
            f"情绪曲线：{scene_plan.get('emotional_target', '')}\n"
            f"开场接续锚点：{scene_plan.get('opening_anchor', '')}\n"
            f"章末钩子：{scene_plan.get('hook', '')}\n\n"
            f"【网文质量策略】\n{quality_directive}\n\n"
            f"【AI味候选词库指导】\n{render_ai_flavor_guidance(quality_profile)}\n\n"
            f"【本章爽点契约】\n{json.dumps(scene_plan.get('payoff_contract') or {}, ensure_ascii=False)}\n\n"
            "【连续性硬门禁】上一章结尾、交接契约和本章第一场必须处于同一"
            "时间线/地点/人物状态；除非正文明确给出过渡，不得跳场。\n"
            f"节拍安排：\n{beat_lines}\n\n"
            f"额外要求：{outline or '无'}\n\n"
            f"请写出约 {target_word_count} 个汉字的完整章节正文，合理范围为"
            f" {max(600, int(target_word_count * 0.72))}-{max(max(600, int(target_word_count * 0.72)) + 200, int(target_word_count * 1.45))} 字；"
            "完成节拍和章尾钩子后立即收束，不要为了凑字数继续解释或重复描写。"
            f"必须与前情提要和已有设定保持一致，不得与【必须遵守的约束】冲突。"
            "节拍完整性是硬要求：节拍表列出的关键过桥、交易、对抗、修炼或设定揭示，必须在正文中写出可见的动作过程、阻碍和结果，"
            "不能从‘准备’直接跳到‘成功’，也不能只用一句‘事情顺利完成’带过；首次出现的能力、印记、规则或代价，"
            "要通过一个动作、对白、感官反应或具体后果交代来源，避免百科式解释。"
            "爽点完整性是硬要求：按‘压制→蓄力→爆发→反馈→余波’推进，允许把相邻阶段合并但不能缺失；"
            "爆发必须由主角的主动选择和已有依据造成，反馈必须落到对手、组织、资源、规则或旁观者的可见变化，"
            "余波必须留下代价、身份变化或新的压力。不要把每章写成同一种打脸，不要用‘众人震惊’替代具体反应。"
            "P1-6 质量整改：主角主动性硬要求——"
            "主角必须主动发起至少一次行动，不能全程被动应对；主动装逼是核心爽点类型之一，"
            "包括主动展示实力、主动打脸、主动布局、主动挑事、主动揭短等；"
            "每3章至少有一次主角主动装逼/主动搞事的情节，避免主角一直被动挨打被动反应。"
            "正文质量要求：开头两段直接承接上一章的动作、地点或未决问题，不要重新讲背景；"
            "每个场景都要完成‘目标→阻碍→选择→代价/结果’，在篇幅允许时推进局部变化、"
            "信息揭示或情绪转折；可参考每约 800-1200 字出现一次局部变化，但只能作为节奏检查，"
            "不得按固定字数机械插入；"
            "转折前给读者可见的动作、线索或异常，高潮后留下具体余波；"
            "人物只能使用自己已经获得的信息，能力、物品、时间和地点必须有来源；"
            "句式长短要有变化，避免连续段落用同一主语和同一收束方式；"
            "同一个两字人名作为段落开头尽量不超过全章约四分之一，交替从动作、场景、物件、对白或他人反应起笔，"
            "同时保持第三人称限知清晰，不能把人名全换成‘他/她’来制造另一种重复。"
            "章末必须把钩子落实为动作、发现或新的选择，不得用总结/说教代替；"
            "情绪要有起伏，避免每段都用同一种‘提出问题-解释-总结’结构；"
            "不要为了‘去AI味’禁用任何单个词或标点，判断标准是整章分布、语境和阅读体验。"
        )

    @staticmethod
    def _build_continuation_prompt(
        text: str,
        scene_plan: dict[str, Any],
        missing: int,
        *,
        quality_profile: dict[str, Any] | None = None,
    ) -> str:
        tail = text[-1600:]
        beats = scene_plan.get("beats") or []
        remaining = "、".join(b.get("name", "") for b in beats[-2:]) if beats else ""
        payoff = scene_plan.get("payoff_contract") or {}
        return (
            f"{third_person_generation_contract()}\n"
            f"{content_generation_contract(quality_profile)}\n\n"
            f"以下是本章已写好的结尾部分：\n\n{tail}\n\n"
            f"请只补足剩余节拍，目标补写约 {missing} 个汉字，"
            f"完成剩余节拍（{remaining}）并以钩子收束："
            f"{scene_plan.get('hook', '')}。保持上一段的时间线、地点、人物状态和情绪，"
            f"爽点余波与新压力必须落地（可见反馈：{payoff.get('payoff_feedback') or '未指定'}；"
            f"下一压力：{payoff.get('next_pressure') or scene_plan.get('hook', '')}），"
            "如果节拍和钩子已经完成就立即停止，不要为了凑字数继续解释；"
            "不要重新开场、不要重复上文，不要写任何说明；补写段落也要变化起笔，"
            "不要机械重复同一人名或同一动作开头，也不要用大量‘他/她’替换。"
        )
