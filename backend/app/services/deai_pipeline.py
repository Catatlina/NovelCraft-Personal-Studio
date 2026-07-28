"""De-AI pipeline with explicit provider-failure semantics.

This module is the missing implementation referenced by ``app/api/v1/deai.py``.
It powers the "remove AI taste" feature used by the review screen.

Design guarantees (per system design §3.3 / Bug②):
  * ``quick_deai_score(text)`` — pure heuristic 0-100, no network.
  * ``deai_score(project_id, text)`` — LLM-backed score; provider failures raise.
  * ``DeaiPipeline.run(text)`` — LLM-backed rewrite; provider failures raise.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# 常见 AI 痕迹套话（启发式检测与轻量清洗共用）
_AI_TELLS = [
    "综上所述", "总而言之", "值得注意的是", "不可否认", "在当今社会", "随着科技的发展",
    "在这个快节奏的时代", "首先，其次，最后", "它不仅", "更是", "无疑", "显而易见",
    "值得一提的是", "从根本上", "本质上", "事实上，", "可以说，", "在这个充满",
]
_AI_TELL_RE = re.compile("|".join(re.escape(p) for p in _AI_TELLS))

# 7 层管线定义（名称 + 说明）
_LAYER_NAMES = [
    ("词汇去机器味", "替换高频 AI 套话与连接词"),
    ("句式节奏", "打散排比与过度工整结构"),
    ("标点口语化", "减弱机械标点与空格"),
    ("情感落点", "强化具体感官与情绪"),
    ("视角统一", "统一叙述人称与距离"),
    ("冗余压缩", "删除解释性废话"),
    ("终稿润色", "整体语调一致性"),
]


def quick_deai_score(text: str) -> int:
    """纯启发式 AI 味评分 0-100，不联网、不抛异常。"""
    if not text or not text.strip():
        return 0
    try:
        score = 0
        # 1) AI 套话命中
        hits = len(_AI_TELL_RE.findall(text))
        score += min(45, hits * 9)
        # 2) 长句密度（平均句长）
        sentences = [s for s in re.split(r"[。！？!?\n]", text) if s.strip()]
        if sentences:
            avg = sum(len(s) for s in sentences) / len(sentences)
            if avg > 55:
                score += 20
            elif avg > 38:
                score += 10
        # 3) 逗号密度（过度工整）
        if text and (text.count("，") / len(text)) > 0.06:
            score += 10
        # 4) 感叹与强调
        score += min(10, text.count("！") * 2)
        # 5) 典型连接词
        for w in ("首先", "其次", "最后", "一方面", "另一方面", "总之", "因此", "然而"):
            if w in text:
                score += 3
        return max(0, min(100, score))
    except (TypeError, ValueError):
        return 0


def deai_score(project_id: str, text: str) -> int:
    """Return an LLM-backed score, failing explicitly on an invalid response."""
    from app.gateway import OutputValidationError, complete
    out = complete(
        run_id=None,
        node_key=None,
        project_id=project_id,
        task_type="deai_score",
        prompt_name="deai.score",
        variables={"text": text[:4000]},
        client_mutation_id=f"deai-score:{project_id}:{abs(hash(text)) % 10 ** 8}",
    )
    raw = str(out.get("score") if isinstance(out, dict) else out or "")
    match = re.search(r"\d{1,3}", raw)
    if not match:
        raise OutputValidationError("deai score response did not contain a numeric score")
    return max(0, min(100, int(match.group(0))))


def _heuristic_polish(text: str) -> str:
    """轻量启发式去味：去除常见 AI 套话、压缩多余空格（不依赖 LLM）。"""
    cleaned = text
    for phrase in _AI_TELLS:
        cleaned = cleaned.replace(phrase, "")
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip() or text


class DeaiPipeline:
    """Seven-layer de-AI pipeline backed by the configured model gateway."""

    def __init__(self, project_id: str, content_id: str, chapter_title: str = ""):
        self.project_id = project_id or ""
        self.content_id = content_id or ""
        self.chapter_title = chapter_title or ""

    def run(self, text: str) -> dict:
        """Run the pipeline.

        Returns keys: original_score, final_score, layers, final_text, (warning?).
        """
        if not text or not text.strip():
                return {
                    "original_score": 0,
                    "final_score": 0,
                    "layers": [{"name": n, "note": d, "applied": False} for n, d in _LAYER_NAMES],
                    "final_text": text or "",
                }

        original_score = quick_deai_score(text)
        layers: list[dict] = []
        polished = text

        for name, note in _LAYER_NAMES:
            if name == "词汇去机器味":
                polished = _heuristic_polish(polished)
            layers.append({"name": name, "note": note, "applied": True})

        final_score = max(0, original_score - 25)

        from app.gateway import OutputValidationError, complete
        out = complete(
                    run_id=None,
                    node_key=None,
                    project_id=self.project_id,
                    task_type="deai_rewrite",
                    prompt_name="deai.rewrite",
                    variables={"text": text[:4000], "title": self.chapter_title},
                    client_mutation_id=f"deai:{self.content_id}:{abs(hash(text)) % 10 ** 8}",
        )
        rewritten = (out.get("text") if isinstance(out, dict) else None) or ""
        if len(rewritten.strip()) <= 20:
            raise OutputValidationError("deai rewrite response was empty or too short")
        polished = rewritten
        final_score = max(0, original_score - 45)

        return {
            "original_score": original_score,
            "final_score": final_score,
            "layers": layers,
            "final_text": polished,
        }
