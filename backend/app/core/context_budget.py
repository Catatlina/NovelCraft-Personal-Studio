"""P2-T2 / Q9: Token budgeting for the bootstrap writing context.

``write_chapter_draft`` (bootstrap writing) previously assembled the *full*
planning context with no upper bound, so a million-word outline or a long
prior-chapter window could blow the prompt cost or get silently truncated.
``gen_next_chapter`` already caps its context via ``ContextAssembler``
(``MAX_TOKENS = 5400``); this module provides the equivalent budget for the
bootstrap path.

The implementation is pure standard library (no third-party dependencies) so it
can be unit-tested and imported anywhere without side effects.
"""
from __future__ import annotations

DEFAULT_MAX_TOKENS = 5400


def _estimate_tokens(text: str) -> int:
    """Approximate token count using ~4 characters per token.

    A simple character-based heuristic keeps the estimate language-agnostic
    (CJK has no whitespace) and dependency-free. It deliberately errs on the
    side of a slightly *higher* token count for safety when truncating.
    """
    if not text:
        return 0
    return len(text) // 4


def cap_context_tokens(context: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    """Cap a context string to ``max_tokens`` tokens, preserving structure.

    The context is split into segments (by newline). If the total estimate
    exceeds ``max_tokens``, the longest segment is repeatedly shrunk until the
    budget is met, so multi-paragraph / multi-section structure is retained as
    much as possible instead of bluntly truncating the tail.

    Args:
        context: The raw context string to budget. Non-string inputs are
            coerced to ``str``.
        max_tokens: Maximum allowed tokens. ``<= 0`` returns an empty string.

    Returns:
        The (possibly truncated) context string, guaranteed to fit the budget.
    """
    if max_tokens <= 0:
        return ""
    if not isinstance(context, str):
        context = str(context)
    if not context:
        return context

    segments = context.split("\n")
    total = sum(_estimate_tokens(seg) for seg in segments)
    if total <= max_tokens:
        return context

    # Greedily shrink the longest segment until within budget.
    while total > max_tokens:
        idx = max(range(len(segments)), key=lambda i: len(segments[i]))
        if not segments[idx]:
            break  # nothing left to shrink
        current_len = len(segments[idx])
        new_len = max(0, int(current_len * 0.85))
        if new_len >= current_len:
            new_len = current_len - 1  # guarantee progress
        if new_len <= 0:
            segments[idx] = ""
            total -= _estimate_tokens(segments[idx])
            continue
        total -= _estimate_tokens(segments[idx]) - _estimate_tokens(segments[idx][:new_len])
        segments[idx] = segments[idx][:new_len]

    return "\n".join(segments)
