"""Generation-time prose texture and local candidate helpers.

This module deliberately stays detector-agnostic.  It turns confirmed prose
samples into a compact feature card, identifies paragraph-sized risk segments,
and applies only validated local replacements.  It never claims that an
internal metric is a Zhuque score and it never rewrites a whole chapter.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from statistics import median
from typing import Any


FEATURE_CARD_SCHEMA_VERSION = "prose-feature-card-v1"
GENERATION_CRITIC_SCHEMA_VERSION = "generation-critic-v1"

_SENTENCE_RE = re.compile(r"[^。！？!?\n]+[。！？!?]?")
_SAMPLE_KEYS = {
    "sample_prose",
    "positive_samples",
    "negative_samples",
    "samples",
    "golden_samples",
    "raw_samples",
}
_EXPLANATION_MARKERS = (
    "也就是说",
    "换句话说",
    "真正的问题是",
    "这意味着",
    "显然",
    "因此",
    "总而言之",
)
_SENSORY_MARKERS = (
    "风",
    "雨",
    "光",
    "影",
    "声音",
    "气味",
    "温度",
    "触感",
    "灰尘",
    "血",
    "水",
)
_ACTION_MARKERS = (
    "抬",
    "转",
    "推",
    "抓",
    "按",
    "拔",
    "走",
    "退",
    "撞",
    "看",
    "听",
    "开口",
    "停下",
    "回头",
)
_TIC_MARKERS = (
    "笑了笑",
    "点了点头",
    "深吸一口气",
    "眼中闪过",
    "眼里闪过",
    "下意识地",
    "本能地",
    "心中一动",
    "没有说话",
    "沉默了片刻",
)


def _compact(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def _paragraphs(text: Any) -> list[str]:
    return [item.strip() for item in re.split(r"\n{2,}|\n", str(text or "")) if item.strip()]


def _sentence_lengths(text: str) -> list[int]:
    return [len(_compact(item)) for item in _SENTENCE_RE.findall(text) if _compact(item)]


def _quantiles(values: list[int]) -> dict[str, float]:
    if not values:
        return {"p25": 0.0, "p50": 0.0, "p75": 0.0}
    ordered = sorted(values)

    def pick(fraction: float) -> float:
        index = min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction)))
        return float(ordered[index])

    return {"p25": pick(0.25), "p50": pick(0.50), "p75": pick(0.75)}


def _ratio(count: int, size: int) -> float:
    return round(count / max(1, size), 5)


def _texture_metrics(text: str) -> dict[str, Any]:
    compact = _compact(text)
    size = len(compact)
    paragraphs = _paragraphs(text)
    sentences = _sentence_lengths(text)
    paragraph_lengths = [len(_compact(item)) for item in paragraphs]
    dialogue_chars = sum(
        len(_compact(item))
        for item in paragraphs
        if re.match(r"^[\"“‘「『《〈]", item)
    )
    openings = [
        re.sub(r"^[\s\"“”‘’「」『』（(]+", "", item)[:2]
        for item in paragraphs
        if item
    ]
    opening_counts = Counter(openings)
    explanation_hits = sum(compact.count(marker) for marker in _EXPLANATION_MARKERS)
    sensory_hits = sum(compact.count(marker) for marker in _SENSORY_MARKERS)
    action_hits = sum(compact.count(marker) for marker in _ACTION_MARKERS)
    tic_hits = sum(compact.count(marker) for marker in _TIC_MARKERS)
    sentence_q = _quantiles(sentences)
    paragraph_q = _quantiles(paragraph_lengths)
    return {
        "char_count": size,
        "paragraph_count": len(paragraphs),
        "sentence_count": len(sentences),
        "sentence_length": sentence_q,
        "sentence_length_mean": round(sum(sentences) / max(1, len(sentences)), 2),
        "paragraph_length": paragraph_q,
        "dialogue_ratio": _ratio(dialogue_chars, size),
        "opening_diversity": round(len(set(openings)) / max(1, len(openings)), 4),
        "explanation_density_per_1000": round(explanation_hits / max(1, size) * 1000, 3),
        "sensory_density_per_1000": round(sensory_hits / max(1, size) * 1000, 3),
        "action_density_per_1000": round(action_hits / max(1, size) * 1000, 3),
        "tic_density_per_1000": round(tic_hits / max(1, size) * 1000, 3),
        "top_openings": opening_counts.most_common(5),
    }


def _normalise_samples(samples: list[Any] | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in samples or []:
        if isinstance(item, str):
            text = item.strip()
            label = "positive"
            metadata: dict[str, Any] = {}
        elif isinstance(item, dict):
            text = str(item.get("text") or item.get("content") or item.get("sample_prose") or "").strip()
            label = str(item.get("label") or item.get("kind") or "positive").strip().lower()
            metadata = item
        else:
            continue
        if not text:
            continue
        if label in {"negative", "bad", "high_risk", "risk"}:
            label = "negative"
        else:
            label = "positive"
        result.append({
            "text": text,
            "label": label,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "detector": str(metadata.get("detector") or "") if metadata else "",
            "score": metadata.get("score") if metadata else None,
        })
    return result


def build_prose_feature_card(
    samples: list[Any] | None = None,
    *,
    provider: str | None = None,
    genre: str | None = None,
    detector: str | None = None,
) -> dict[str, Any]:
    """Build a compact, non-verbatim writing profile from confirmed samples."""
    normalised = _normalise_samples(samples)
    positive = [item for item in normalised if item["label"] == "positive"]
    negative = [item for item in normalised if item["label"] == "negative"]
    positive_metrics = [_texture_metrics(item["text"]) for item in positive]
    negative_metrics = [_texture_metrics(item["text"]) for item in negative]

    def aggregate(metrics: list[dict[str, Any]]) -> dict[str, Any]:
        if not metrics:
            return {}

        def values(path: tuple[str, ...]) -> list[float]:
            result: list[float] = []
            for metric in metrics:
                value: Any = metric
                for key in path:
                    value = value.get(key) if isinstance(value, dict) else None
                if isinstance(value, (int, float)):
                    result.append(float(value))
            return result

        def med(path: tuple[str, ...]) -> float:
            items = values(path)
            return round(float(median(items)), 4) if items else 0.0

        return {
            "sample_count": len(metrics),
            "sentence_length_p25": med(("sentence_length", "p25")),
            "sentence_length_p50": med(("sentence_length", "p50")),
            "sentence_length_p75": med(("sentence_length", "p75")),
            "paragraph_length_p25": med(("paragraph_length", "p25")),
            "paragraph_length_p50": med(("paragraph_length", "p50")),
            "paragraph_length_p75": med(("paragraph_length", "p75")),
            "dialogue_ratio": med(("dialogue_ratio",)),
            "opening_diversity": med(("opening_diversity",)),
            "explanation_density_per_1000": med(("explanation_density_per_1000",)),
            "sensory_density_per_1000": med(("sensory_density_per_1000",)),
            "action_density_per_1000": med(("action_density_per_1000",)),
            "tic_density_per_1000": med(("tic_density_per_1000",)),
        }

    positive_profile = aggregate(positive_metrics)
    negative_profile = aggregate(negative_metrics)
    rules: list[str] = []
    if positive_profile:
        rules.extend([
            "句长按现场节奏自然伸缩，短句用于动作和压力，较长句用于观察或犹豫，不人为追求固定比例。",
            (
                "段落长度以自然推进为准，优先让每段完成一个动作、反应或信息落点；"
                f"已确认样本的段长中位数约 {positive_profile['paragraph_length_p50']:.0f} 字。"
            ),
            (
                "对白、动作、物件和现场反馈交替承载信息；"
                f"已确认样本对白段占比约 {positive_profile['dialogue_ratio']:.0%}，仅作质地参考。"
            ),
            "先让读者看到行为和结果，再在人物需要选择时露出解释；不替读者总结主题。",
            "人物可以漏答、误判、改主意或停在半句话，信息不必一次交换完。",
        ])
    if negative_profile:
        rules.append("负样本只用于避开其结构风险，不复制负样本的措辞、剧情或句式。")

    return {
        "schema_version": FEATURE_CARD_SCHEMA_VERSION,
        "sample_count": len(normalised),
        "positive_sample_count": len(positive),
        "negative_sample_count": len(negative),
        "provider": provider or None,
        "genre": genre or None,
        "detector": detector or None,
        "positive_profile": positive_profile,
        "negative_profile": negative_profile,
        "writer_rules": rules,
        "source_hashes": [item["sha256"] for item in normalised[:12]],
        "raw_samples_in_prompt": False,
    }


def feature_card_from_style_card(style_card: dict[str, Any] | None) -> dict[str, Any]:
    """Extract positive/negative samples without leaking their raw text."""
    card = style_card if isinstance(style_card, dict) else {}
    author = card.get("author_card") if isinstance(card.get("author_card"), dict) else card
    genre = card.get("genre_card") if isinstance(card.get("genre_card"), dict) else {}
    samples: list[Any] = []
    for source in (author, genre):
        if not isinstance(source, dict):
            continue
        if source.get("sample_prose"):
            samples.append({"text": source["sample_prose"], "label": "positive"})
        for key in ("positive_samples", "golden_samples", "samples"):
            value = source.get(key)
            if isinstance(value, list):
                samples.extend(value)
        value = source.get("negative_samples")
        if isinstance(value, list):
            samples.extend({**item, "label": "negative"} if isinstance(item, dict) else {"text": item, "label": "negative"} for item in value)
    existing = card.get("prose_feature_card")
    if isinstance(existing, dict) and existing.get("schema_version") == FEATURE_CARD_SCHEMA_VERSION:
        return existing
    return build_prose_feature_card(
        samples,
        provider=str(author.get("provider") or "") if isinstance(author, dict) else None,
        genre=str(genre.get("genre") or genre.get("name") or "") if isinstance(genre, dict) else None,
        detector=str(author.get("detector") or "") if isinstance(author, dict) else None,
    )


def sanitise_style_card_for_prompt(style_card: dict[str, Any] | None) -> dict[str, Any]:
    """Keep human-readable style metadata but remove verbatim sample payloads."""
    card = style_card if isinstance(style_card, dict) else {}

    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: clean(item)
                for key, item in value.items()
                if key not in _SAMPLE_KEYS
            }
        if isinstance(value, list):
            return [clean(item) for item in value[:12]]
        return value

    cleaned = clean(card)
    cleaned["prose_feature_card"] = feature_card_from_style_card(card)
    return cleaned


def render_prose_feature_card(card: dict[str, Any] | None) -> str:
    card = card if isinstance(card, dict) else {}
    profile = card.get("positive_profile") or {}
    rules = card.get("writer_rules") or []
    if not profile and not rules:
        return ""
    lines = [
        f"样本证据：正样本 {card.get('positive_sample_count', 0)}，负样本 {card.get('negative_sample_count', 0)}；只学习统计质地，不复制原文。",
    ]
    if profile:
        lines.append(
            "句长 p25/p50/p75="
            f"{profile.get('sentence_length_p25', 0):.0f}/{profile.get('sentence_length_p50', 0):.0f}/{profile.get('sentence_length_p75', 0):.0f}；"
            "段长 p25/p50/p75="
            f"{profile.get('paragraph_length_p25', 0):.0f}/{profile.get('paragraph_length_p50', 0):.0f}/{profile.get('paragraph_length_p75', 0):.0f}；"
            f"对白段参考占比={profile.get('dialogue_ratio', 0):.0%}；"
            f"段首多样性={profile.get('opening_diversity', 0):.0%}。"
        )
    lines.extend(f"- {rule}" for rule in rules[:6])
    return "【自然叙事特征卡（生成期执行）】\n" + "\n".join(lines)


def build_generation_critic_report(text: str, metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return paragraph-local risk evidence; low-risk paragraphs stay locked."""
    paragraphs = _paragraphs(text)
    opening_counts: Counter[str] = Counter()
    cleaned_openings: list[str] = []
    for paragraph in paragraphs:
        first = re.sub(r"^[\s\"“”‘’「」『』（(]+", "", paragraph)
        opening = first[:2]
        cleaned_openings.append(opening)
        if opening and opening[:1] not in "他她它我你":
            opening_counts[opening] += 1
    repeated_opening = opening_counts.most_common(1)[0] if opening_counts else ("", 0)
    repeated_name = repeated_opening[0] if repeated_opening[1] >= 2 else ""
    risk_codes: dict[int, set[str]] = {}
    for index, paragraph in enumerate(paragraphs):
        reasons: set[str] = set()
        if repeated_name and cleaned_openings[index] == repeated_name and index > 0:
            reasons.add("repeated_paragraph_opening")
        if any(marker in paragraph for marker in _EXPLANATION_MARKERS):
            reasons.add("explicit_explanation")
        if "——" in paragraph or "—" in paragraph or "--" in paragraph:
            reasons.add("dash_density")
        if any(marker in paragraph for marker in _TIC_MARKERS):
            reasons.add("repeated_tic")
        if re.search(r"根据大纲|场景目标|场景卡|接下来写|读者将|本章需要", paragraph):
            reasons.add("meta_leakage")
        if reasons:
            risk_codes[index] = reasons
    ranked = sorted(
        risk_codes.items(),
        key=lambda item: (-len(item[1]), item[0]),
    )[:4]
    segments = [
        {
            "segment_id": f"p-{index}",
            "paragraph_index": index,
            "text": paragraphs[index],
            "risk_codes": sorted(reasons),
            "locked": False,
        }
        for index, reasons in ranked
    ]
    locked = [index for index in range(len(paragraphs)) if index not in {item[0] for item in ranked}]
    return {
        "schema_version": GENERATION_CRITIC_SCHEMA_VERSION,
        "paragraph_count": len(paragraphs),
        "segments": segments,
        "locked_paragraph_indexes": locked,
        "risk_segment_count": len(segments),
        "internal_only": True,
        "metrics_risk_score": int((metrics or {}).get("risk_score") or 0),
    }


def apply_segment_replacements(text: str, replacements: list[dict[str, Any]]) -> str | None:
    """Apply only paragraph replacements; return None for any contract violation."""
    source = str(text or "")
    parts = re.split(r"(\n+)", source)
    paragraph_positions = [index for index in range(0, len(parts), 2) if parts[index].strip()]
    used: set[int] = set()
    for item in replacements or []:
        if not isinstance(item, dict):
            return None
        try:
            paragraph_index = int(item.get("paragraph_index"))
        except (TypeError, ValueError):
            return None
        replacement = str(item.get("text") or "").strip()
        if paragraph_index in used or paragraph_index < 0 or paragraph_index >= len(paragraph_positions) or not replacement:
            return None
        if "\n" in replacement:
            return None
        parts[paragraph_positions[paragraph_index]] = replacement
        used.add(paragraph_index)
    return "".join(parts).strip() if used else None


def validate_segment_replacement_payload(data: Any, expected_indexes: set[int]) -> list[dict[str, Any]] | None:
    if not isinstance(data, dict) or not isinstance(data.get("replacements"), list):
        return None
    replacements = data["replacements"]
    indexes: set[int] = set()
    normalised: list[dict[str, Any]] = []
    for item in replacements:
        if not isinstance(item, dict):
            return None
        try:
            index = int(item.get("paragraph_index"))
        except (TypeError, ValueError):
            return None
        value = str(item.get("text") or "").strip()
        if index not in expected_indexes or index in indexes or not value or "\n" in value:
            return None
        indexes.add(index)
        normalised.append({"paragraph_index": index, "text": value})
    return normalised if indexes == expected_indexes else None
