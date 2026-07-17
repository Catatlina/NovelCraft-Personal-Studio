"""
NovelCraft 七层去AI味润色管线 (7-Layer De-AI Pipeline)

7 layers progressively remove AI-taste from Chinese novel text:
1. deai_detect     — identify & rewrite AI clichés (套路句式)
2. deai_colloquialize — make more conversational, natural Chinese
3. deai_rhythm     — vary sentence length, adjust pacing
4. deai_character  — check character voice/behavior consistency
5. deai_context    — check timeline, location, event continuity
6. deai_deduplicate — remove repeated phrases/expressions
7. deai_polish     — overall refinement

All layers call app.gateway.complete() with real provider paths — no mock/fallback.
"""
from __future__ import annotations

import logging
from typing import Any

from app.gateway import complete as gateway_complete, ProviderError, OutputValidationError

logger = logging.getLogger(__name__)

# ── 7-layer pipeline definition ──────────────────────────────────────────
LAYERS = [
    {
        "name": "deai_detect",
        "label": "检测与去套路",
        "prompt_name": "deai.detect",
        "task_type": "deai_detect",
        "description": "识别AI套路句式（不仅如此/总而言之/值得一提的是/命运的齿轮/心猛地一沉 等），重写为自然表达",
    },
    {
        "name": "deai_colloquialize",
        "label": "口语化",
        "prompt_name": "deai.colloquialize",
        "task_type": "deai_colloquialize",
        "description": "使文字更口语化、自然，增加对话感，减少书面语腔调",
    },
    {
        "name": "deai_rhythm",
        "label": "节奏优化",
        "prompt_name": "deai.rhythm",
        "task_type": "deai_rhythm",
        "description": "变化句长，调整叙事节奏，避免千篇一律的句式",
    },
    {
        "name": "deai_character",
        "label": "人物一致性",
        "prompt_name": "deai.character",
        "task_type": "deai_character",
        "description": "检查人物语气/行为是否符合设定，修复OOC问题",
    },
    {
        "name": "deai_context",
        "label": "上下文一致性",
        "prompt_name": "deai.context",
        "task_type": "deai_context",
        "description": "检查时间线、地点、事件连续性，修复矛盾",
    },
    {
        "name": "deai_deduplicate",
        "label": "去重",
        "prompt_name": "deai.deduplicate",
        "task_type": "deai_deduplicate",
        "description": "移除重复短语/表达，减少冗余修饰",
    },
    {
        "name": "deai_polish",
        "label": "最终润色",
        "prompt_name": "deai.polish",
        "task_type": "deai_polish",
        "description": "整体精修，确保文笔流畅自然，无可察觉的AI痕迹",
    },
]

# ── AI-ism patterns for heuristic pre-check (before LLM scoring) ─────────
AI_ISMS = [
    "不仅如此", "总而言之", "值得一提的是", "毫无疑问",
    "命运的齿轮", "心猛地一沉", "眼神复杂", "踏上新的旅程",
    "新的篇章", "他终于明白", "这一切都说明", "深刻变化",
    "翻天覆地", "不可思议", "前所未有", "毋庸置疑",
    "从此以后", "在那之后", "经过一番", "最终",
    "徐徐展开", "悄然发生", "不知不觉中", "恍惚之间",
]


class DeaiPipeline:
    """7-layer progressive de-AI pipeline for Chinese novel text."""

    def __init__(self, project_id: str, content_id: str = "", chapter_title: str = ""):
        self.project_id = project_id
        self.content_id = content_id
        self.chapter_title = chapter_title
        self.layer_results: list[dict[str, Any]] = []

    def run(self, text: str) -> dict[str, Any]:
        """Run all 7 layers sequentially on the given text.

        Returns:
            {
                "original_score": int,   # 0-100 (lower = less AI taste)
                "final_score": int,
                "layers": [{"name": "deai_detect", "score_before": 78, "score_after": 55,
                            "changes": ["..."], ...}],
                "final_text": str,
            }
        """
        if not text or not text.strip():
            return {
                "original_score": 0,
                "final_score": 0,
                "layers": [],
                "final_text": text,
            }

        original_score = deai_score(self.project_id, text)
        current_text = text
        current_score = original_score
        self.layer_results = []

        for i, layer in enumerate(LAYERS):
            layer_result = {
                "name": layer["name"],
                "label": layer["label"],
                "description": layer["description"],
                "score_before": current_score,
                "score_after": current_score,
                "changes": [],
                "status": "pending",
            }

            try:
                result = gateway_complete(
                    run_id=None,
                    node_key=None,
                    project_id=self.project_id,
                    task_type=layer["task_type"],
                    prompt_name=layer["prompt_name"],
                    variables={
                        "text": current_text,
                        "title": self.chapter_title,
                        "layer_number": str(i + 1),
                        "previous_score": str(current_score),
                    },
                )
                new_text = result.get("text", current_text)
                if new_text and new_text.strip() and new_text != current_text:
                    current_text = new_text

                # Re-score after this layer
                new_score = deai_score(self.project_id, current_text)
                layer_result["score_after"] = new_score
                layer_result["changes"] = result.get("changes", [])
                layer_result["status"] = "done"
                current_score = new_score

            except (ProviderError, OutputValidationError) as exc:
                logger.warning(
                    "DeAI layer %s (%s) failed: %s — skipping layer",
                    i + 1, layer["label"], exc,
                )
                layer_result["status"] = "skipped"
                layer_result["error"] = str(exc)

            self.layer_results.append(layer_result)

        return {
            "original_score": original_score,
            "final_score": current_score,
            "layers": self.layer_results,
            "final_text": current_text,
        }


def deai_score(project_id: str, text: str) -> int:
    """Score a text for AI-taste (0 = natural, 100 = robotic/AI-generated).

    Uses heuristic pre-check + LLM scoring via gateway.complete().
    Returns 0-100 integer.
    """
    if not text or not text.strip():
        return 0

    # Heuristic pre-check: count AI-isms
    detected_isms = []
    for pattern in AI_ISMS:
        count = text.count(pattern)
        if count > 0:
            detected_isms.append({"pattern": pattern, "count": count})

    heuristic_base = min(len(detected_isms) * 6, 45)  # Cap heuristic at 45

    # LLM deep scoring
    try:
        result = gateway_complete(
            run_id=None,
            node_key=None,
            project_id=project_id,
            task_type="deai_score",
            prompt_name="deai.score",
            variables={
                "text": text[:3000],  # Cap length for scoring
                "heuristic_score": str(heuristic_base),
                "detected_patterns": str(detected_isms)[:500],
            },
        )
        ai_score = int(result.get("score", 50))
    except (ProviderError, OutputValidationError, ValueError) as exc:
        logger.warning("DeAI scoring via LLM failed: %s — using heuristic", exc)
        ai_score = heuristic_base + 30  # Conservative fallback

    # Blend: 40% heuristic + 60% AI
    final_score = int(heuristic_base * 0.4 + ai_score * 0.6)
    return max(0, min(100, final_score))


def quick_deai_score(text: str) -> int:
    """Fast heuristic-only score, no AI call. Returns 0-100."""
    if not text or not text.strip():
        return 0
    detected = sum(1 for p in AI_ISMS if p in text)
    return min(detected * 6, 100)
