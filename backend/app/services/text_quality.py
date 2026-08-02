"""Shared deterministic safeguards for long-form web-fiction text.

The provider owns prose decisions.  This module only protects the product
contract: a rewrite must retain the chapter's material, and a provider that
serialises several paragraphs into one large JSON string must not be mistaken
for a destructive rewrite just because its line breaks changed.
"""
from __future__ import annotations

import re
from math import ceil


_SENTENCE_END = re.compile(r"(?<=[。！？!?])")


def content_chars(text: str) -> int:
    """Count content characters using the platform's whitespace-free rule."""
    return len(re.sub(r"\s+", "", str(text or "")))


def paragraphs(text: str) -> list[str]:
    """Return non-empty paragraphs without changing their contents."""
    return [part.strip() for part in re.split(r"\n{2,}|\n", str(text or "")) if part.strip()]


def _split_long_paragraph(paragraph: str, max_chars: int) -> list[str]:
    """Split only at sentence boundaries, retaining every source character."""
    if len(paragraph) <= max_chars:
        return [paragraph]
    sentences = [item.strip() for item in _SENTENCE_END.split(paragraph) if item.strip()]
    if len(sentences) <= 1:
        return [paragraph]

    result: list[str] = []
    bucket = ""
    for sentence in sentences:
        if bucket and len(bucket) + len(sentence) > max_chars:
            result.append(bucket)
            bucket = sentence
        else:
            bucket += sentence
    if bucket:
        result.append(bucket)
    return result or [paragraph]


def normalize_narrative_paragraphs(
    text: str,
    *,
    minimum_paragraphs: int = 0,
    max_paragraph_chars: int = 220,
) -> str:
    """Repair provider line-break loss without rewriting prose.

    Providers sometimes return the correct text with 20--30 paragraphs joined
    together.  Reflow is activated only when the output is below the source
    paragraph floor; otherwise the provider's natural paragraphing is kept.
    The operation is deterministic and content-preserving.
    """
    source_paragraphs = paragraphs(text)
    if not source_paragraphs:
        return ""
    if len(source_paragraphs) >= max(1, minimum_paragraphs):
        return "\n\n".join(source_paragraphs)

    result: list[str] = []
    for paragraph in source_paragraphs:
        result.extend(_split_long_paragraph(paragraph, max_paragraph_chars))

    # Keep tightening only while the provider still collapsed too much
    # structure.  This reaches the source floor when sentence boundaries are
    # available, without touching a short paragraph or inventing text.
    current_max = max(40, max_paragraph_chars // 2)
    while len(result) < minimum_paragraphs and current_max < max_paragraph_chars:
        expanded: list[str] = []
        for paragraph in result:
            expanded.extend(_split_long_paragraph(paragraph, current_max))
        if len(expanded) == len(result):
            break
        result = expanded
        current_max = max(40, current_max // 2)
    return "\n\n".join(result)


def normalize_and_validate_rewrite(
    source: str,
    candidate: str,
    *,
    min_ratio: float = 0.8,
    max_ratio: float = 1.2,
    min_paragraph_ratio: float = 0.6,
    minimum_chars: int = 50,
) -> tuple[str, dict[str, int]]:
    """Normalize paragraph shape and enforce the lossless rewrite contract.

    Raises ``ValueError`` with a user-safe reason.  Callers translate that to
    their gateway/domain error type so failed work remains visibly failed.
    """
    source = str(source or "")
    candidate = str(candidate or "").strip()
    if content_chars(candidate) < minimum_chars:
        raise ValueError("returned text is empty or too-short")

    source_count = content_chars(source)
    candidate_count = content_chars(candidate)
    if source_count and (
        candidate_count < int(source_count * min_ratio)
        or candidate_count > int(source_count * max_ratio)
    ):
        raise ValueError(
            f"changed chapter length outside safe range: {source_count}->{candidate_count}"
        )

    source_paragraph_count = len(paragraphs(source))
    minimum_paragraphs = max(1, ceil(source_paragraph_count * min_paragraph_ratio))
    normalized = normalize_narrative_paragraphs(
        candidate,
        minimum_paragraphs=minimum_paragraphs,
    )
    candidate_paragraph_count = len(paragraphs(normalized))
    if candidate_paragraph_count < minimum_paragraphs:
        raise ValueError(
            "dropped too many narrative paragraphs: "
            f"{source_paragraph_count}->{candidate_paragraph_count}"
        )
    return normalized, {
        "source_chars": source_count,
        "candidate_chars": candidate_count,
        "source_paragraphs": source_paragraph_count,
        "candidate_paragraphs": candidate_paragraph_count,
    }
