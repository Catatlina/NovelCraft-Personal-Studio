"""Real event subscribers.

These are what make V7 event-driven: publishing an event actually mutates the
Novel Brain instead of only writing a log row. Registered by StoryDirector.
"""
from __future__ import annotations

import uuid
from typing import Any

from ..brain.novel_brain import NovelBrain
from .event_bus import EventBus

PROGRESS_KEY = "story_progress"
GENERATION_STATS_KEY = "generation_stats"
QUALITY_STATS_KEY = "quality_stats"
ALERT_KEY = "integrity_alerts"


class BrainStateSubscribers:
    """Subscribers that project events onto Novel Brain state."""

    def __init__(self, brain: NovelBrain, event_bus: EventBus):
        self.brain = brain
        self.event_bus = event_bus
        self.handled: list[str] = []

    def register(self) -> None:
        self.event_bus.subscribe("chapter_generated", self.on_chapter_generated)
        self.event_bus.subscribe("generation_completed", self.on_generation_completed)
        self.event_bus.subscribe("review_completed", self.on_review_completed)
        self.event_bus.subscribe("constraint_violated", self.on_constraint_violated)
        self.event_bus.subscribe(
            "memory_conflict_detected", self.on_memory_conflict
        )

    async def _current(self, key: str) -> dict[str, Any]:
        state = await self.brain.state.get_state("global", key)
        value = (state or {}).get("value") or {}
        return dict(value) if isinstance(value, dict) else {}

    # ── handlers ────────────────────────────────────────────────────────
    async def on_chapter_generated(self, event: Any) -> None:
        data = event.event_data or {}
        chapter_number = int(data.get("chapter_number") or 0)
        word_count = int(data.get("word_count") or 0)

        progress = await self._current(PROGRESS_KEY)
        chapters = set(progress.get("chapters_done") or [])
        chapters.add(chapter_number)
        total_words = int(progress.get("total_words") or 0) + word_count

        await self.brain.state.update_state(
            "global",
            PROGRESS_KEY,
            {
                "last_chapter": max(chapter_number, int(progress.get("last_chapter") or 0)),
                "chapters_done": sorted(chapters),
                "chapter_count": len(chapters),
                "total_words": total_words,
                "avg_words": round(total_words / max(len(chapters), 1), 1),
            },
            0.95,
            source="event_subscriber",
            reason=f"chapter_generated event for chapter {chapter_number}",
        )
        self.handled.append("chapter_generated")

        # Chapter progress advances every in-progress goal proportionally.
        await self._advance_goals(chapter_number)

    async def on_generation_completed(self, event: Any) -> None:
        data = event.event_data or {}
        stats = await self._current(GENERATION_STATS_KEY)
        await self.brain.state.update_state(
            "global",
            GENERATION_STATS_KEY,
            {
                "runs": int(stats.get("runs") or 0) + 1,
                "total_tokens": int(stats.get("total_tokens") or 0)
                + int(data.get("tokens") or 0),
                "total_cost": round(
                    float(stats.get("total_cost") or 0.0) + float(data.get("cost") or 0.0),
                    6,
                ),
                "total_deai_changes": int(stats.get("total_deai_changes") or 0)
                + int(data.get("deai_changes") or 0),
                "last_chapter": data.get("chapter_number"),
            },
            0.95,
            source="event_subscriber",
            reason="generation_completed event",
        )
        self.handled.append("generation_completed")

    async def on_review_completed(self, event: Any) -> None:
        data = event.event_data or {}
        score = float(data.get("overall_score") or 0.0)
        stats = await self._current(QUALITY_STATS_KEY)
        count = int(stats.get("reviews") or 0) + 1
        total = float(stats.get("score_sum") or 0.0) + score

        await self.brain.state.update_state(
            "global",
            QUALITY_STATS_KEY,
            {
                "reviews": count,
                "score_sum": round(total, 2),
                "avg_score": round(total / count, 2),
                "min_score": min(
                    score, float(stats.get("min_score") or score)
                ),
                "max_score": max(
                    score, float(stats.get("max_score") or score)
                ),
                "last_score": score,
                "last_chapter": data.get("chapter_number"),
                "blocking_violations_total": int(
                    stats.get("blocking_violations_total") or 0
                )
                + int(data.get("blocking_violations") or 0),
            },
            0.95,
            source="event_subscriber",
            reason="review_completed event",
        )
        self.handled.append("review_completed")

    async def on_constraint_violated(self, event: Any) -> None:
        await self._bump_alert("constraint_violations", event)
        self.handled.append("constraint_violated")

    async def on_memory_conflict(self, event: Any) -> None:
        await self._bump_alert("memory_conflicts", event)
        self.handled.append("memory_conflict_detected")

    async def _bump_alert(self, field: str, event: Any) -> None:
        data = event.event_data or {}
        alerts = await self._current(ALERT_KEY)
        entries = list(alerts.get(f"{field}_recent") or [])
        entries.append(
            {
                "chapter_number": data.get("chapter_number"),
                "detail": data.get("description") or data.get("constraint") or data.get("key"),
                "severity": data.get("severity"),
            }
        )
        await self.brain.state.update_state(
            "global",
            ALERT_KEY,
            {
                **alerts,
                field: int(alerts.get(field) or 0) + 1,
                f"{field}_recent": entries[-20:],
            },
            0.95,
            source="event_subscriber",
            reason=f"{field} alert",
        )

    async def _advance_goals(self, chapter_number: int) -> None:
        """Move in-progress goals forward as chapters land (progress is 0..1)."""
        goals = await self.brain.goals.list_goals(limit=100)
        for goal in goals:
            if goal.get("status") not in ("in_progress", "pending"):
                continue
            target = goal.get("target_chapter")
            current = float(goal.get("progress") or 0.0)
            if isinstance(target, int) and target > 0:
                new_progress = min(1.0, round(chapter_number / target, 4))
            else:
                new_progress = min(1.0, round(current + 0.05, 4))
            if new_progress > current:
                await self.brain.goals.update_progress(
                    uuid.UUID(goal["id"]),
                    new_progress,
                    source="event_subscriber",
                )
