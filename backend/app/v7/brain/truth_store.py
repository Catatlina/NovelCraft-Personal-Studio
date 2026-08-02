"""Structured truth-domain projection backed by Novel Brain state."""
from __future__ import annotations

from typing import Any

from .state_manager import StoryStateManager


TRUTH_DOMAINS: tuple[str, ...] = (
    "current_state",
    "characters",
    "world",
    "timeline",
    "foreshadowing",
    "resources",
    "style_bible",
)


class TruthStore:
    """Expose seven readable truth domains without creating a second SSOT."""

    def __init__(self, state: StoryStateManager):
        self.state = state

    async def snapshot(self, *, include_chapter_text: bool = False) -> dict[str, Any]:
        global_states = await self.state.list_states("global", limit=200)
        character_states = await self.state.list_states("character", limit=200)
        world_states = await self.state.list_states("world", limit=200)
        plot_states = await self.state.list_states("plot", limit=300)
        chapter_states = await self.state.list_states("chapter", limit=500)
        rule_states = await self.state.list_states("learning_rule", limit=100)

        def values(states: list[dict[str, Any]], *, text: bool = True) -> list[dict[str, Any]]:
            result = []
            for item in states:
                value = dict(item.get("value") or {})
                if not include_chapter_text and not text:
                    value.pop("text", None)
                result.append({"key": item.get("key"), "value": value, "version": item.get("version")})
            return result

        timeline = [
            item for item in global_states + plot_states
            if "time" in str(item.get("key") or "").lower()
            or "timeline" in str(item.get("key") or "").lower()
            or "chapter" in str(item.get("key") or "").lower()
        ]
        foreshadowing = [
            item for item in plot_states
            if (item.get("value") or {}).get("category") == "foreshadowing"
            or "foreshadow" in str(item.get("key") or "").lower()
        ]
        resources = [
            item for item in world_states + character_states + plot_states
            if (item.get("value") or {}).get("category") in {"resources", "resource_updates"}
            or "resource" in str(item.get("key") or "").lower()
        ]
        style = [
            item for item in global_states + rule_states
            if "style" in str(item.get("key") or "").lower()
            or "rule" in str(item.get("key") or "").lower()
        ]
        current_state = {
            "global": values(global_states),
            "plot": values(plot_states),
            "chapters": values(chapter_states, text=include_chapter_text),
        }
        return {
            "schema_version": "truth-domains-v1",
            "domains": {
                "current_state": current_state,
                "characters": values(character_states),
                "world": values(world_states),
                "timeline": timeline,
                "foreshadowing": foreshadowing,
                "resources": resources,
                "style_bible": style,
            },
            "counts": {
                "current_state": sum(len(value) for value in current_state.values()),
                "characters": len(character_states),
                "world": len(world_states),
                "timeline": len(timeline),
                "foreshadowing": len(foreshadowing),
                "resources": len(resources),
                "style_bible": len(style),
            },
        }

    async def digest(self) -> dict[str, int]:
        snapshot = await self.snapshot(include_chapter_text=False)
        return dict(snapshot["counts"])
