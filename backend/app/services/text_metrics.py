"""Shared text metrics used by all content generation paths."""
from __future__ import annotations

import re


def count_content_chars(content: str) -> int:
    """Count Chinese web-fiction characters after removing whitespace."""
    return len(re.sub(r"\s+", "", content or ""))
