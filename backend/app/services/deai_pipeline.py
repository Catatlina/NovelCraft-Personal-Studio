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
import hashlib
import re

from app.services.text_quality import (
    content_chars,
    duplicate_paragraph_stats,
    normalize_and_validate_rewrite,
)

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
    # Do not collapse newlines: a paragraph boundary is narrative structure,
    # not expendable whitespace.  The old ``\s`` pattern turned a safe
    # fallback into one giant paragraph with spaces.
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip() or text


def _normalize_excess_dashes(text: str) -> tuple[str, int]:
    """Preserve expressive dashes while reducing chapter-wide overuse."""
    count = 0
    text, n = re.subn(r"-{2,}", "——", text)
    count += n
    text, n = re.subn(r"\.{3,}", "……", text)
    count += n
    text, n = re.subn(r"。{2,}", "。", text)
    count += n
    text, n = re.subn(r"(——){2,}", "——", text)
    count += n
    compact_size = content_chars(text)
    if compact_size < 600:
        return text, count

    dash_limit = max(3, int(compact_size / 1000 * 5))
    seen = 0

    def replace_excess(match: re.Match[str]) -> str:
        nonlocal count, seen
        seen += 1
        if seen <= dash_limit:
            return match.group(0)
        count += 1
        return "，"

    return re.sub(r"——|—", replace_excess, text), count


def _fallback_quality_gate(text: str, message: str) -> tuple[dict, dict]:
    """Accept a rule-only fallback only when its measurable risks are clean."""
    from app.v7.quality.deai_metrics import analyze_deai_patterns

    metrics = analyze_deai_patterns(text)
    hard_codes = {
        "dash_density",
        "uniform_cadence",
        "repeated_paragraph_opening",
        "duplicate_paragraph",
        "ai_phrase",
        "repeated_tic",
    }
    blocking = sorted({
        str(flag.get("code"))
        for flag in metrics.get("flags") or []
        if isinstance(flag, dict)
        and str(flag.get("code") or "") in hard_codes
        and str(flag.get("severity") or "").lower() in {"medium", "high"}
    })
    risk_score = int(metrics.get("risk_score") or 0)
    passed = not blocking and risk_score < 70
    gate = {
        "passed": passed,
        "mode": "deterministic_fallback",
        "code": "semantic_rewrite_unavailable" if passed else "rewrite_candidate_rejected",
        "message": message,
        "warning": message,
        "risk_score": risk_score,
    }
    if blocking:
        gate["blocking_flags"] = blocking
    return gate, metrics


class DeaiPipeline:
    """Seven-layer de-AI pipeline backed by the configured model gateway."""

    def __init__(self, project_id: str, content_id: str, chapter_title: str = ""):
        self.project_id = project_id or ""
        self.content_id = content_id or ""
        self.chapter_title = chapter_title or ""

    def final_humanize(
        self,
        text: str,
        *,
        source_facts: str = "",
        forbidden_changes: str = "",
        quality_retry_feedback: str = "",
        style_profile: str = "",
        run_id: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Run the V6 final semantic humanization gate.

        The rule-only pass in :meth:`run` is useful for cheap pre-cleaning, but
        it cannot repair cadence, voice, or over-explanation.  The chapter loop
        therefore calls this provider-backed pass after content repairs.  A
        malformed, destructive, or empty response raises instead of silently
        publishing the pre-humanized text as if the quality gate had passed.
        """
        from app.gateway import OutputValidationError, complete

        if not text or not text.strip():
            return {
                "final_text": text or "",
                "changes": [],
                "ai_patterns_removed": [],
            }

        mutation_seed = hashlib.sha256(
            (text + "\n" + (quality_retry_feedback or "")).encode("utf-8")
        ).hexdigest()[:20]
        out = complete(
            run_id=run_id,
            node_key="final_humanize",
            project_id=self.project_id,
            user_id=user_id,
            task_type="final_humanize",
            prompt_name="bootstrap.final_humanize",
            variables={
                "_chapter_body": text,
                "source_facts": source_facts or "（无额外不可变事实）",
                "forbidden_changes": forbidden_changes or "情节、人物、时间线、设定与对白信息",
                "quality_retry_feedback": quality_retry_feedback or "（首次最终定稿）",
                "style_profile": style_profile or "（暂无作者文风卡）",
            },
            client_mutation_id=f"final-humanize:{self.content_id}:{mutation_seed}:v2",
        )
        final_text = str(out.get("humanized_text") or "").strip() if isinstance(out, dict) else ""
        try:
            # A provider is allowed to reflow paragraphs, but not to lose the
            # narrative.  The shared guard can recover accidental line-break
            # loss by splitting at sentence boundaries before deciding that
            # the result is destructive.
            final_text, _shape = normalize_and_validate_rewrite(
                text,
                final_text,
                minimum_chars=50,
            )
            duplicate_stats = duplicate_paragraph_stats(final_text)
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
                raise OutputValidationError(f"final_humanize {message}") from exc
            # A provider that expands or duplicates a chapter has returned an
            # unsafe candidate.  Preserve the source and keep the operation
            # visibly unverified; never turn the bad candidate into a success.
            logger.warning("final_humanize candidate rejected: %s", message)
            return {
                "final_text": text,
                "changes": [],
                "ai_patterns_removed": [],
                "quality_gate": {
                    "passed": False,
                    "code": "rewrite_candidate_rejected",
                    "message": message,
                },
                "warnings": [message],
            }

        return {
            "final_text": final_text,
            "changes": out.get("changes", []) if isinstance(out, dict) else [],
            "ai_patterns_removed": out.get("ai_patterns_removed", []) if isinstance(out, dict) else [],
            "quality_gate": {"passed": True},
            "warnings": [],
        }

    def run(self, text: str, *, style_profile: str = "") -> dict:
        """Run the pipeline.

        Returns keys: original_score, final_score, layers, final_text.
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

        # Layer 1: heuristic polish (词法级快速清洗)
        polished = _heuristic_polish(text)
        polished, dash_changes = _normalize_excess_dashes(polished)
        layers.append({"name": "词汇去机器味", "note": "heuristic", "applied": True})
        if dash_changes:
            layers.append({
                "name": "破折号密度修复",
                "note": "只替换超出章节密度阈值的多余用法",
                "applied": True,
                "changes": dash_changes,
            })

        # Layer 2: real AI rewrite with web-novel style prompt
        from app.gateway import OutputValidationError, complete
        out = complete(
            run_id=None,
            node_key=None,
            project_id=self.project_id,
            task_type="deai_rewrite",
            prompt_name="deai.rewrite",
            # Do not silently throw away the second half of a chapter.  The
            # prompt and gateway own context sizing; this layer must preserve
            # the complete source for a fact-safe rewrite.
            variables={"text": text, "title": self.chapter_title,
                       "style_profile": style_profile or "（暂无作者文风卡）"},
            client_mutation_id=f"deai:{self.content_id}:{abs(hash(text)) % 10 ** 8}",
        )
        rewritten = (out.get("text") if isinstance(out, dict) else None) or ""
        if len(rewritten.strip()) < 20:
            raise OutputValidationError("deai.rewrite returned empty or too-short text")

        source_chars = content_chars(text)
        rewritten_chars = content_chars(rewritten)

        def _reject_candidate(code: str, message: str) -> dict:
            # Heuristic cleanup is deterministic and loss-aware.  It is safe
            # only when it retained essentially all source material; otherwise
            # the exact source is the only honest fallback.
            heuristic_chars = content_chars(polished)
            fallback_text = (
                polished if heuristic_chars >= int(source_chars * 0.95) else text
            )
            fallback_text, fallback_dash_changes = _normalize_excess_dashes(fallback_text)
            if fallback_dash_changes:
                layers.append({
                    "name": "破折号密度修复",
                    "note": "fallback",
                    "applied": True,
                    "changes": fallback_dash_changes,
                })
            safe_message = f"{message}；已保留规则清洗稿"
            quality_gate, fallback_metrics = _fallback_quality_gate(
                fallback_text,
                safe_message,
            )
            if not quality_gate["passed"]:
                quality_gate["code"] = code
            layers.append({
                "name": "AI 网文风格重写",
                "note": code,
                "applied": False,
                "source_chars": source_chars,
                "candidate_chars": rewritten_chars,
                "reason": safe_message,
            })
            logger.warning("deai.rewrite candidate rejected: %s", message)
            return {
                "original_score": original_score,
                "final_score": quick_deai_score(fallback_text),
                "layers": layers,
                "final_text": fallback_text,
                "metrics": fallback_metrics,
                "quality_gate": {
                    **quality_gate,
                    "source_chars": source_chars,
                    "candidate_chars": rewritten_chars,
                    "rejection_code": code,
                },
                "warnings": [safe_message],
            }

        if rewritten_chars < int(source_chars * 0.8) or rewritten_chars > int(source_chars * 1.2):
            return _reject_candidate(
                "changed_length_outside_safe_range",
                f"deai.rewrite changed length outside safe range: {source_chars}->{rewritten_chars}",
            )
        duplicate_stats = duplicate_paragraph_stats(rewritten)
        if float(duplicate_stats.get("duplicate_ratio") or 0.0) >= 0.01:
            return _reject_candidate(
                "duplicate_paragraph",
                "deai.rewrite returned repeated full paragraphs: "
                f"ratio={duplicate_stats.get('duplicate_ratio')}",
            )
        polished, dash_changes = _normalize_excess_dashes(rewritten)
        layers.append({"name": "AI 网文风格重写", "note": "deai.rewrite", "applied": True})
        if dash_changes:
            layers.append({
                "name": "破折号密度修复",
                "note": "semantic candidate",
                "applied": True,
                "changes": dash_changes,
            })

        # Layer 3: repair provider line-break loss without changing prose.
        # This is the same lossless contract used by the canonical V7
        # humanizer, so editor de-AI cannot silently collapse a chapter into
        # fewer paragraphs either.
        try:
            polished, shape = normalize_and_validate_rewrite(
                text,
                polished,
                min_ratio=0.8,
                max_ratio=1.2,
                minimum_chars=max(20, min(50, len(re.sub(r"\s+", "", text)))),
            )
        except ValueError as exc:
            raise OutputValidationError(f"deai.rewrite {exc}") from exc
        layers.append({"name": "段落拆分", "note": "lossless-reflow", "applied": True, "shape": shape})

        final_score = quick_deai_score(polished)

        return {
            "original_score": original_score,
            "final_score": final_score,
            "layers": layers,
            "final_text": polished,
            "quality_gate": {"passed": True},
            "warnings": [],
        }
