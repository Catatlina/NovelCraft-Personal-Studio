"""Shared quality gates for the V7 director pipeline.

The old director treated a 70-point review as publishable.  That made a
chapter with a weak continuity or writing score look successful when its
average happened to be high.  This module keeps the gate deterministic and
testable: the model supplies evidence, while the application decides whether
the chapter can enter the V6 library.
"""
from __future__ import annotations

from typing import Any

from ...services.reader_experience import (
    reader_experience_issues,
    summarize_reader_experience,
)

QUALITY_PASS_SCORE = 85.0
QUALITY_REWORK_SCORE = 80.0
MAX_REWORKS = 2

# These dimensions directly affect cross-chapter reading experience.  A low
# emotional/pacing score is reviewable; a low continuity/logic/writing score is
# not allowed to pass merely because other dimensions compensate for it.
CRITICAL_DIMENSION_MINIMUMS: dict[str, float] = {
    "consistency": 85.0,
    "character_voice": 85.0,
    "plot_logic": 85.0,
    "writing_quality": 85.0,
    "constraint_compliance": 85.0,
}


def evaluate_review(review_data: dict[str, Any]) -> dict[str, Any]:
    """Return the application-level decision for an AI review payload."""
    score = float(review_data.get("overall_score") or 0.0)
    blocking = int(review_data.get("blocking_violations") or 0)
    dimensions = review_data.get("dimension_scores") or review_data.get("dimensions") or {}
    failures: list[dict[str, Any]] = []
    if score < QUALITY_PASS_SCORE:
        failures.append({"dimension": "overall_score", "actual": score, "minimum": QUALITY_PASS_SCORE})
    for name, minimum in CRITICAL_DIMENSION_MINIMUMS.items():
        actual = float(dimensions.get(name) or 0.0)
        if actual < minimum:
            failures.append({"dimension": name, "actual": actual, "minimum": minimum})
    if blocking:
        failures.append({"dimension": "blocking_violations", "actual": blocking, "minimum": 0})
    reader_experience = summarize_reader_experience(review_data.get("reader_experience"))
    return {
        "passed": not failures,
        "score": score,
        "blocking_violations": blocking,
        "failures": failures,
        "threshold": QUALITY_PASS_SCORE,
        "critical_dimension_minimums": dict(CRITICAL_DIMENSION_MINIMUMS),
        # Reader experience is advisory; it must not replace the continuity
        # and writing hard gates above.  It is nevertheless returned with the
        # decision so weak expectation/payoff is visible to rework and UI.
        "reader_experience": reader_experience,
        "reader_experience_warnings": reader_experience_issues(reader_experience),
    }
