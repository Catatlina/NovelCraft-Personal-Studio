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
        }

    compact = re.sub(r"\s+", "", text)
    size = max(1, len(compact))
    lengths = _sentence_lengths(text)
    average = mean(lengths) if lengths else 0.0
    burstiness = (pstdev(lengths) / average) if len(lengths) > 1 and average else 0.0
    dash_count = text.count("——") + text.count("—") + text.count("--")
    ellipsis_count = text.count("……") + text.count("...")
    ai_phrase_hits = sum(text.count(phrase) for phrase in _AI_PHRASES)
    repeated = _repeated_phrases(text)

    flags: list[dict[str, Any]] = []
    # Density is meaningful at chapter scale.  A single deliberate dash in a
    # short sample must never be treated as an AI smell.
    if size >= 200 and dash_count / size * 1000 > 5:
        flags.append({"code": "dash_density", "severity": "medium", "message": "破折号密度偏高，需结合对白语境定向检查"})
    if size >= 200 and ellipsis_count / size * 1000 > 4:
        flags.append({"code": "ellipsis_density", "severity": "low", "message": "省略号密度偏高，可能形成固定情绪模板"})
    if len(lengths) >= 10 and burstiness < 0.18:
        flags.append({"code": "uniform_cadence", "severity": "medium", "message": "句长过于整齐，缺少网文阅读所需的节奏起伏"})
    if ai_phrase_hits:
        flags.append({"code": "ai_phrase", "severity": "medium", "message": f"命中 {ai_phrase_hits} 个高风险套话"})
    if repeated:
        flags.append({"code": "repeated_phrase", "severity": "low", "message": "存在跨句重复短语，需要确认是否为刻意回环"})

    risk_score = min(
        100,
        ai_phrase_hits * 8
        + max(0, int((0.18 - burstiness) * 100))
        + (max(0, int((dash_count / size * 1000 - 5) * 8)) if size >= 200 else 0)
        + len(repeated) * 3,
    )
    return {
        "schema_version": "deai-metrics-v1",
        "risk_score": risk_score,
        "flags": flags,
        "sentence_count": len(lengths),
        "sentence_length_mean": round(average, 2),
        "sentence_length_burstiness": round(burstiness, 4),
        "dash_count": dash_count,
        "dash_density_per_1000": round(dash_count / size * 1000, 3),
        "ellipsis_count": ellipsis_count,
        "ai_phrase_hits": ai_phrase_hits,
        "repeated_phrases": repeated,
    }
