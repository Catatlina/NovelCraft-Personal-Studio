"""Deterministic naturalness metrics for Chinese web-fiction prose.

These metrics are not an AI detector and do not ban punctuation.  They flag
abnormal density, repetition and overly uniform cadence relative to a normal
chapter so the semantic editor can make a targeted repair.
"""
from __future__ import annotations

import re
from collections import Counter
from statistics import mean, pstdev
from typing import Any

from ...services.text_quality import duplicate_paragraph_stats


_SENTENCE_RE = re.compile(r"[^。！？!?\n]+[。！？!?]?")
_AI_PHRASES = (
    "值得一提的是",
    "综上所述",
    "总而言之",
    "不得不说",
    "显而易见",
    "从根本上",
    "在这个快节奏的时代",
    "命运的齿轮",
    "故事才刚刚开始",
)


def _sentence_lengths(text: str) -> list[int]:
    return [len(re.sub(r"\s+", "", item)) for item in _SENTENCE_RE.findall(text) if item.strip()]


def _repeated_phrases(text: str) -> list[dict[str, Any]]:
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 80:
        return []
    counts: Counter[str] = Counter()
    for size in (4, 5, 6):
        for start in range(0, len(compact) - size + 1):
            phrase = compact[start : start + size]
            if any(ch in phrase for ch in "，。！？；：\"“”‘’"):
                continue
            counts[phrase] += 1
    return [
        {"phrase": phrase, "count": count}
        for phrase, count in counts.most_common(8)
        if count >= 3
    ][:5]


def _repeated_paragraph_opening(text: str) -> dict[str, Any]:
    """Detect repeated multi-character paragraph openings.

    A single leading pronoun is common in readable Chinese web fiction and is
    not, by itself, evidence of a template.  Counting only the first character
    made ordinary passages such as several paragraphs beginning with ``他``
    fail the hard quality gate.  Keep the signal, but require the same
    two-character opening phrase to recur across paragraphs.
    """
    paras = [item for item in re.split(r"\n{2,}|\n", text) if item.strip()]
    if len(paras) < 12:
        return {"opening": "", "count": 0, "ratio": 0.0, "unit_length": 2}
    openings: Counter[str] = Counter()
    for paragraph in paras:
        first = re.sub(r"^[\s\"“”‘’「」『』（(]+", "", paragraph.strip())
        if first:
            # Two characters retain useful signals such as ``顾沉``/``他把``
            # while avoiding a false positive for the generic ``他``/``她``.
            openings[first[:2]] += 1
    opening, count = openings.most_common(1)[0] if openings else ("", 0)
    return {
        "opening": opening,
        "count": count,
        "ratio": round(count / len(paras), 4),
        "unit_length": 2,
    }


def analyze_deai_patterns(text: str) -> dict[str, Any]:
    """Return explainable risk signals; higher risk means more review needed."""
    if not text or not text.strip():
        return {
            "schema_version": "deai-metrics-v1",
            "risk_score": 0,
            "flags": [],
            "sentence_count": 0,
            "sentence_length_mean": 0.0,
            "sentence_length_burstiness": 0.0,
            "dash_count": 0,
            "dash_density_per_1000": 0.0,
            "ellipsis_count": 0,
            "ai_phrase_hits": 0,
            "repeated_phrases": [],
            "repeated_paragraph_opening": {"opening": "", "count": 0, "ratio": 0.0},
            "duplicate_paragraphs": duplicate_paragraph_stats(""),
        }

    compact = re.sub(r"\s+", "", text)
    size = max(1, len(compact))
    lengths = _sentence_lengths(text)
    average = mean(lengths) if lengths else 0.0
    burstiness = (pstdev(lengths) / average) if len(lengths) > 1 and average else 0.0
    # Match long dashes as one token; counting both "——" and its two "—"
    # characters overstated the density and made the metric hard to explain.
    dash_count = len(re.findall(r"——|--|—", text))
    ellipsis_count = len(re.findall(r"……|\.\.\.|…{2,}", text))
    ai_phrase_hits = sum(text.count(phrase) for phrase in _AI_PHRASES)
    repeated = _repeated_phrases(text)
    repeated_opening = _repeated_paragraph_opening(text)
    duplicate_paragraphs = duplicate_paragraph_stats(text)
    dash_density = dash_count / size * 1000
    ellipsis_density = ellipsis_count / size * 1000

    flags: list[dict[str, Any]] = []
    # Density is meaningful at chapter scale.  A single deliberate dash in a
    # short sample must never be treated as an AI smell.
    if size >= 200 and dash_count / size * 1000 > 5:
        flags.append({"code": "dash_density", "severity": "medium", "message": "破折号密度偏高，需结合对白语境定向检查"})
    if size >= 200 and ellipsis_count / size * 1000 > 4:
        flags.append({"code": "ellipsis_density", "severity": "low", "message": "省略号密度偏高，可能形成固定情绪模板"})
    if len(lengths) >= 10 and burstiness < 0.18:
        flags.append({"code": "uniform_cadence", "severity": "medium", "message": "句长过于整齐，缺少网文阅读所需的节奏起伏"})
    if repeated_opening["ratio"] >= 0.3:
        flags.append({
            "code": "repeated_paragraph_opening",
            "severity": "medium",
            "message": f"{repeated_opening['opening']}字开头段落占比偏高，可能形成机械句式",
        })
    if ai_phrase_hits:
        flags.append({"code": "ai_phrase", "severity": "medium", "message": f"命中 {ai_phrase_hits} 个高风险套话"})
    if repeated:
        flags.append({"code": "repeated_phrase", "severity": "low", "message": "存在跨句重复短语，需要确认是否为刻意回环"})
    duplicate_ratio = float(duplicate_paragraphs.get("duplicate_ratio") or 0.0)
    adjacent_duplicates = int(duplicate_paragraphs.get("adjacent_duplicate_count") or 0)
    if duplicate_ratio >= 0.01:
        severity = "high" if duplicate_ratio >= 0.08 or adjacent_duplicates >= 2 else "medium"
        flags.append({
            "code": "duplicate_paragraph",
            "severity": severity,
            "message": (
                "检测到完整段落重复："
                f"重复字符占比 {duplicate_ratio:.1%}，额外重复段落 "
                f"{duplicate_paragraphs.get('duplicate_paragraph_count') or 0} 个"
            ),
            "evidence": duplicate_paragraphs.get("examples") or [],
        })

    risk_score = min(
        100,
        ai_phrase_hits * 12
        + max(0, int((0.18 - burstiness) * 100))
        + (max(0, int((dash_density - 4) * 6)) if size >= 200 else 0)
        + (max(0, int((ellipsis_density - 3) * 4)) if size >= 200 else 0)
        + (max(0, int((repeated_opening["ratio"] - 0.25) * 45)) if repeated_opening["ratio"] else 0)
        + len(repeated) * 4,
    )
    if duplicate_ratio >= 0.01:
        risk_score = min(100, max(risk_score, 70 if duplicate_ratio < 0.08 else 95))
    return {
        "schema_version": "deai-metrics-v1",
        "risk_score": risk_score,
        "flags": flags,
        "sentence_count": len(lengths),
        "sentence_length_mean": round(average, 2),
        "sentence_length_burstiness": round(burstiness, 4),
        "dash_count": dash_count,
        "dash_density_per_1000": round(dash_density, 3),
        "ellipsis_count": ellipsis_count,
        "ellipsis_density_per_1000": round(ellipsis_density, 3),
        "ai_phrase_hits": ai_phrase_hits,
        "repeated_phrases": repeated,
        "repeated_paragraph_opening": repeated_opening,
        "duplicate_paragraphs": duplicate_paragraphs,
    }
