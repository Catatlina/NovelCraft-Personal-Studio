"""V3 §11.1 reader-experience review dimension (merged into review_7dim).

Deterministic helpers only — the LLM scoring itself is produced by the
existing ``bootstrap.review_7dim`` call (no new agent / call chain). These
functions normalize the optional ``reader_experience`` block and derive a
non-blocking warning summary that is persisted on the chapter meta and
surfaced by patrol_check.
"""

from __future__ import annotations

from typing import Any

# key -> human label used in issues / UI
READER_EXPERIENCE_KEYS: dict[str, str] = {
    "expectation": "期待感",
    "conflict": "冲突感",
    "payoff": "爽点",
    "emotion_shift": "情绪变化",
    "worth_continuing": "追读意愿",
}

# below this score a sub-dimension counts as weak (warning, never blocking)
READER_EXPERIENCE_WEAK_THRESHOLD = 60.0


def normalize_reader_experience(rx: Any) -> dict[str, float] | None:
    """Return a {key: score} dict limited to known keys, or None if absent/invalid."""
    if not isinstance(rx, dict):
        return None
    out: dict[str, float] = {}
    for key in READER_EXPERIENCE_KEYS:
        value = rx.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[key] = max(0.0, min(100.0, float(value)))
    return out or None


def summarize_reader_experience(rx: Any,
                                threshold: float = READER_EXPERIENCE_WEAK_THRESHOLD) -> dict[str, Any]:
    """Build the durable summary stored on chapter meta.

    status: "skip" (no block returned) / "pass" / "warning" (>=1 weak dim).
    Never blocks the review gate — reader experience is advisory (§11.1).
    """
    scores = normalize_reader_experience(rx)
    if scores is None:
        return {"status": "skip", "scores": None, "weak_dimensions": [], "avg": None}
    weak = [key for key, value in scores.items() if value < threshold]
    avg = round(sum(scores.values()) / len(scores), 1)
    return {
        "status": "warning" if weak else "pass",
        "scores": scores,
        "weak_dimensions": weak,
        "avg": avg,
    }


def reader_experience_issues(summary: dict[str, Any]) -> list[str]:
    """Render weak dimensions as human-readable issue strings (may be empty)."""
    if not isinstance(summary, dict) or summary.get("status") != "warning":
        return []
    scores = summary.get("scores") or {}
    issues = []
    for key in summary.get("weak_dimensions") or []:
        label = READER_EXPERIENCE_KEYS.get(key, key)
        score = scores.get(key)
        shown = f"{score:.0f}" if isinstance(score, (int, float)) else "?"
        issues.append(f"读者体验薄弱：{label}（{shown}分）")
    return issues
