"""Pure unit tests for ``app.core.context_budget.cap_context_tokens``.

No external dependencies — runs under ``pytest`` with no Postgres/Redis.
"""
from __future__ import annotations

from app.core.context_budget import cap_context_tokens, _estimate_tokens


def test_short_input_unchanged():
    text = "hello world, this is a short context"
    assert cap_context_tokens(text, 5400) == text
    assert cap_context_tokens(text) == text  # default budget


def test_empty_string_returns_empty():
    assert cap_context_tokens("", 5400) == ""
    assert cap_context_tokens("", 0) == ""


def test_long_input_is_truncated():
    text = "x" * 100_000  # ~25k tokens, far above the 5400 default
    capped = cap_context_tokens(text, 5400)
    assert isinstance(capped, str)
    assert len(capped) < len(text)
    # Budget respected (with a small safety margin for segment rounding).
    assert _estimate_tokens(capped) <= 5400 + 16


def test_structure_preserved_for_multiline():
    # Three lines, the middle one enormous.
    ctx = "line one\n" + ("y" * 80_000) + "\nline three"
    capped = cap_context_tokens(ctx, 5400)
    lines = capped.split("\n")
    assert len(lines) == 3  # all segments retained
    # The huge middle line is the one that got shortened.
    assert len(lines[1]) < 80_000
    assert lines[0] == "line one"  # short lines untouched
    assert lines[2] == "line three"


def test_max_tokens_one_does_not_crash():
    text = "a reasonably long piece of text that is well above a single token"
    result = cap_context_tokens(text, 1)
    assert isinstance(result, str)
    # Still fits the (tiny) budget.
    assert _estimate_tokens(result) <= 1 + 4


def test_non_string_input_coerced():
    assert cap_context_tokens(12345, 5400) == "12345"


def test_zero_or_negative_budget_returns_empty():
    assert cap_context_tokens("anything at all", 0) == ""
    assert cap_context_tokens("anything at all", -5) == ""
