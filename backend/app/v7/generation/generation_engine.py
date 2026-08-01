"""Generation Engine - Sprint 2.

Real generation pipeline:
  context assembly -> scene planning (AI) -> AI generation -> de-AI pipeline

No mocks, no placeholder text. Failures raise instead of returning fake success.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ..brain.novel_brain import NovelBrain
from ..trace.tracer import ExecutionTracer
from ..events.event_bus import EventBus

CHAPTER_STATE_TYPE = "chapter"


def chinese_word_count(text: str) -> int:
    """Count characters the way Chinese novel platforms do (whitespace ignored)."""
    if not text:
        return 0
    return len(re.sub(r"\s+", "", text))


def chapter_state_key(chapter_number: int) -> str:
    return f"chapter_{chapter_number:04d}"


class AIGatewayError(RuntimeError):
    """Raised when the LLM call cannot be completed."""


class ContextAssembler:
    """Assembles real generation context out of the Novel Brain."""

    def __init__(self, brain: NovelBrain):
        self.brain = brain

    async def load_previous_chapters(
        self, chapter_number: int, *, count: int = 2
    ) -> list[dict[str, Any]]:
        """Load the most recent already-generated chapters from brain state."""
        states = await self.brain.state.list_states(CHAPTER_STATE_TYPE, limit=200)
        chapters: list[dict[str, Any]] = []
        for s in states:
            value = s.get("value") or {}
            num = value.get("chapter_number")
            if isinstance(num, int) and num < chapter_number:
                chapters.append(value)
        chapters.sort(key=lambda c: c.get("chapter_number", 0))
        return chapters[-count:] if count > 0 else chapters

    async def assemble_context(
        self,
        chapter_number: int,
        *,
        scene_type: str = "normal",
        token_budget: int = 5400,
    ) -> dict[str, Any]:
        """Assemble layered context: state / goals / constraints / recap."""
        overview = await self.brain.get_overview()

        character_states = await self.brain.state.list_states("character", limit=30)
        world_states = await self.brain.state.list_states("world", limit=30)
        plot_states = await self.brain.state.list_states("plot", limit=30)
        global_states = await self.brain.state.list_states("global", limit=20)

        goals = await self.brain.goals.list_goals(limit=50)
        active_goals = [
            g for g in goals if g.get("status") in ("in_progress", "pending")
        ]
        constraints = await self.brain.constraints.list_constraints(limit=50)

        previous = await self.load_previous_chapters(chapter_number, count=2)
        recap_parts: list[str] = []
        for prev in previous:
            summary = prev.get("summary") or ""
            if summary:
                recap_parts.append(
                    f"第{prev.get('chapter_number')}章梗概：{summary}"
                )
        last_tail = ""
        if previous:
            last_text = previous[-1].get("text") or ""
            last_tail = last_text[-400:] if last_text else ""

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
        }

        rendered = self.render(layers)
        # Rough token budgeting: ~1.6 chars per token for mixed zh/en text.
        max_chars = int(token_budget * 1.6)
        truncated = False
        if len(rendered) > max_chars:
            rendered = rendered[:max_chars]
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

        recap = layers.get("recap", [])
        if recap:
            blocks.append("【前情提要】\n" + "\n".join(recap))

        tail = layers.get("previous_tail")
        if tail:
            blocks.append("【上一章结尾原文（用于承接）】\n" + tail)

        return "\n\n".join(blocks) if blocks else "（暂无历史上下文，这是故事的开端）"


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
        return {
            "chapter_number": chapter_number,
            "chapter_title": plot_brief.get("chapter_title_hint") or f"第{chapter_number}章",
            "scene_goal": plot_brief.get("tension_target")
            or (objectives[0] if objectives else ""),
            "beats": normalised,
            "pov_character": plot_brief.get("pov_character"),
            "pacing": plot_brief.get("pacing_advice"),
            "conflict": plot_brief.get("tension_target"),
            "hook": plot_brief.get("hook"),
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
    ) -> dict[str, Any]:
        """Produce a beat sheet. Returns dict including `_usage` for accounting.

        When the Story Director already obtained a usable beat sheet from the
        plot engine's assessment pass, it is adopted directly instead of paying
        for a second planning call that could contradict the first.
        """
        adopted = self._adopt_plot_brief(chapter_number, target_word_count, plot_brief)
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

        prompt = (
            f"你是小说的场景导演。请为第 {chapter_number} 章设计场景结构。\n\n"
            f"{context.get('rendered_context', '')}\n\n"
            f"本章大纲/要求：{outline or '（无，请依据故事目标自行推进）'}\n"
            f"{brief_block}\n"
            f"目标字数：{target_word_count} 字。\n\n"
            "请只输出 JSON，格式：\n"
            "{\n"
            '  "chapter_title": "本章标题",\n'
            '  "scene_goal": "本章要达成的叙事目的",\n'
            '  "beats": [{"name":"节拍名","purpose":"作用","content":"要写什么",'
            '"emotion":"情绪","target_words":800}],\n'
            '  "pov_character": "视角人物",\n'
            '  "pacing": "slow|medium|fast",\n'
            '  "conflict": "本章核心冲突",\n'
            '  "hook": "章末钩子",\n'
            '  "confidence": 0.85\n'
            "}\n"
            "beats 数量 4-6 个，各 beat 的 target_words 之和应接近目标字数。"
        )
        result = await self.gateway.generate_json(
            prompt,
            system_prompt="你是资深小说结构编辑，只输出严格合法的 JSON。",
            max_tokens=2000,
            temperature=0.6,
        )
        plan = result["data"]
        plan.setdefault("chapter_title", f"第{chapter_number}章")
        plan.setdefault("beats", [])
        plan["chapter_number"] = chapter_number
        plan["target_word_count"] = target_word_count
        plan["_usage"] = result["usage"]
        return plan


class DeAIPipeline:
    """Rule-based de-AI pipeline. Every layer reports how many edits it made."""

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

    async def process(self, text: str) -> dict[str, Any]:
        """Run all 7 layers. Returns processed text + per-layer edit counts."""
        original = text
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

        total = sum(item["changes"] for item in layers)
        return {
            "original_text": original,
            "processed_text": text,
            "layers_applied": layers,
            "total_changes": total,
            "original_chars": chinese_word_count(original),
            "processed_chars": chinese_word_count(text),
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

    def __init__(self, tracer: ExecutionTracer | None = None):
        self.tracer = tracer
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        self.default_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.timeout = float(os.getenv("V7_AI_TIMEOUT", "180"))
        self.max_retries = int(os.getenv("V7_AI_MAX_RETRIES", "3"))

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
    ) -> dict[str, Any]:
        """Call the LLM. Raises AIGatewayError after all retries fail."""
        if not self.api_key:
            raise AIGatewayError(
                "DEEPSEEK_API_KEY is not configured; refusing to fabricate output"
            )

        model = model or self.default_model
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                # Total-duration hard cap: httpx's ``timeout`` only guards the
                # idle gap between two socket reads, so a slow-but-chatty LLM
                # stream can hang the chapter forever (observed: DeepSeek slow
                # window left generate_chapter stuck >30min with no timeout
                # firing). wrap the whole request in asyncio.wait_for so the
                # call can never exceed ``self.timeout`` wall-clock seconds.
                async def _one_request() -> dict[str, Any]:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(
                        connect=self.timeout, read=self.timeout,
                        write=self.timeout, pool=self.timeout,
                    )) as client:
                        response = await client.post(url, headers=headers, json=payload)
                        response.raise_for_status()
                        return response.json()

                result = await asyncio.wait_for(_one_request(), timeout=self.timeout)

                choice = result["choices"][0]
                content = choice["message"]["content"]
                usage = result.get("usage", {}) or {}
                tokens_input = int(usage.get("prompt_tokens", 0))
                tokens_output = int(usage.get("completion_tokens", 0))
                cost = (
                    tokens_input / 1_000_000 * self.INPUT_PRICE_PER_M
                    + tokens_output / 1_000_000 * self.OUTPUT_PRICE_PER_M
                )
                if not content or not content.strip():
                    raise AIGatewayError("LLM returned empty content")

                return {
                    "text": content,
                    "model": model,
                    "tokens_input": tokens_input,
                    "tokens_output": tokens_output,
                    "cost": cost,
                    "finish_reason": choice.get("finish_reason", "stop"),
                    "attempts": attempt,
                    "prompt_name": prompt_name,
                    "prompt_version": prompt_version,
                }
            except Exception as exc:  # noqa: BLE001 - retried and re-raised below
                last_error = exc
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
    ) -> dict[str, Any]:
        """Generate and parse a JSON object. Returns {"data":..., "usage":...}."""
        usage_total = {"tokens_input": 0, "tokens_output": 0, "cost": 0.0, "model": None}
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
            )
            usage_total["tokens_input"] += result["tokens_input"]
            usage_total["tokens_output"] += result["tokens_output"]
            usage_total["cost"] += result["cost"]
            usage_total["model"] = result["model"]
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
    ):
        self.db = db
        self.novel_id = novel_id
        self.brain = brain
        self.tracer = tracer
        self.event_bus = event_bus

        self.ai_gateway = AIGateway(tracer)
        self.context_assembler = ContextAssembler(brain)
        self.scene_director = SceneDirector(brain, self.ai_gateway)
        self.deai_pipeline = DeAIPipeline()

    async def generate_chapter(
        self,
        chapter_number: int,
        *,
        prompt: str | None = None,
        outline: str | None = None,
        target_word_count: int = 3000,
        max_continuations: int = 3,
        plot_brief: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate one chapter of at least `target_word_count` Chinese characters."""
        usage = {"tokens_input": 0, "tokens_output": 0, "cost": 0.0, "model": None}

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
            context = await self.context_assembler.assemble_context(chapter_number)
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
            )
            add_usage(step, scene_plan.pop("_usage", {}))
            step.set_output(
                f"{len(scene_plan.get('beats', []))} beats: "
                f"{scene_plan.get('chapter_title')}",
                data={"scene_plan": scene_plan},
                confidence=float(scene_plan.get("confidence", 0.8) or 0.8),
            )

        # Step: AI generation (with continuation until target length is met)
        async with self.tracer.trace_step(
            "generation.ai_generate",
            "ai_generation",
            input_summary=f"Generate >= {target_word_count} chars with AI",
        ) as step:
            gen_prompt = self._build_generation_prompt(
                chapter_number, context, scene_plan, outline or prompt, target_word_count
            )
            first = await self.ai_gateway.generate(
                gen_prompt,
                system_prompt=(
                    "你是一位专业中文网络小说作者。写作要求：画面感强、对白自然、"
                    "避免总结性旁白与说教结尾、避免翻译腔。直接输出正文，不要标题、"
                    "不要任何解释或markdown标记。"
                ),
                max_tokens=4000,
                temperature=0.85,
                prompt_name="v7.generation.chapter",
                prompt_version="1.0.0",
            )
            add_usage(step, first)
            text = first["text"].strip()

            continuations = 0
            while (
                chinese_word_count(text) < target_word_count
                and continuations < max_continuations
            ):
                continuations += 1
                missing = target_word_count - chinese_word_count(text)
                cont = await self.ai_gateway.generate(
                    self._build_continuation_prompt(text, scene_plan, missing),
                    system_prompt=(
                        "你是一位专业中文网络小说作者，正在续写同一章的后半部分。"
                        "直接接着写正文，不要重复已有内容，不要写标题或说明。"
                    ),
                    max_tokens=3000,
                    temperature=0.85,
                    prompt_name="v7.generation.continuation",
                    prompt_version="1.0.0",
                )
                add_usage(step, cont)
                text = text.rstrip() + "\n" + cont["text"].strip()

            raw_count = chinese_word_count(text)
            step.set_output(
                f"{raw_count} chars, {continuations} continuation(s)",
                data={"raw_word_count": raw_count, "continuations": continuations},
            )

        # Step: de-AI pipeline (real transformations)
        async with self.tracer.trace_step(
            "generation.deai_process",
            "deai_processing",
            input_summary="Run 7-layer de-AI pipeline",
        ) as step:
            deai_result = await self.deai_pipeline.process(text)
            step.set_output(
                f"{deai_result['total_changes']} edits across "
                f"{len(deai_result['layers_applied'])} layers",
                data={"layers": deai_result["layers_applied"]},
            )

        final_text = deai_result["processed_text"]
        word_count = chinese_word_count(final_text)

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
            "context": {
                "rendered_chars": context["rendered_chars"],
                "previous_chapters": context["previous_chapters"],
            },
            "scene_plan": scene_plan,
            "deai": {
                "layers_applied": deai_result["layers_applied"],
                "total_changes": deai_result["total_changes"],
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
            f"本章目的：{scene_plan.get('scene_goal', '')}\n"
            f"核心冲突：{scene_plan.get('conflict', '')}\n"
            f"节奏：{scene_plan.get('pacing', 'medium')}\n"
            f"章末钩子：{scene_plan.get('hook', '')}\n\n"
            f"节拍安排：\n{beat_lines}\n\n"
            f"额外要求：{outline or '无'}\n\n"
            f"请写出不少于 {target_word_count} 个汉字的完整章节正文。"
            f"必须与前情提要和已有设定保持一致，不得与【必须遵守的约束】冲突。"
        )

    @staticmethod
    def _build_continuation_prompt(
        text: str, scene_plan: dict[str, Any], missing: int
    ) -> str:
        tail = text[-800:]
        beats = scene_plan.get("beats") or []
        remaining = "、".join(b.get("name", "") for b in beats[-2:]) if beats else ""
        return (
            f"以下是本章已写好的结尾部分：\n\n{tail}\n\n"
            f"请无缝接着往下写，至少再写 {missing} 个汉字，"
            f"完成剩余节拍（{remaining}）并以钩子收束："
            f"{scene_plan.get('hook', '')}。不要重复上文，不要写任何说明。"
        )
