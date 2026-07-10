"""TASK-037: Hotspot collection system with web adapter."""
from __future__ import annotations

import os
import json
import urllib.request
from app.db import connect, encode, new_id

HOTSPOT_SOURCES = {
    "zhihu": {"name": "知乎热榜", "url": "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=10"},
    "weibo": {"name": "微博热搜", "url": "https://weibo.com/ajax/side/hotSearch"},
}


def fetch_hotspots() -> list[dict]:
    """TASK-037: Fetch hotspots from external sources."""
    results = []
    for key, cfg in HOTSPOT_SOURCES.items():
        try:
            req = urllib.request.Request(cfg["url"], headers={"User-Agent": "NovelCraft/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            items = data.get("data", data.get("realtime", []))[:10]
            for item in items:
                results.append({
                    "source": key,
                    "title": item.get("target", {}).get("title", item.get("word", "")),
                    "category": item.get("category", "general"),
                    "score": item.get("detail_text", item.get("raw_hot", 0)),
                })
        except Exception:
            pass  # Source unavailable — skip gracefully
    return results


def store_hotspots(items: list[dict]) -> int:
    """Store hotspot items in knowledge_items table."""
    db = connect()
    count = 0
    for item in items:
        db.execute(
            "INSERT INTO knowledge_items (id, kind, title, body, meta) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (new_id(), "hotspot", item.get("title", ""),
             json.dumps(item, ensure_ascii=False),
             encode({"source": item.get("source", ""), "score": item.get("score", 0)})),
        )
        count += 1
    db.commit(); db.close()
    return count


def analyze_hotspots(items: list[dict]) -> list[dict]:
    """TASK-037: Generate creative angles from hotspots (template-based, no LLM needed)."""
    angles = []
    templates = [
        "如果「{title}」发生在一个虚构世界里会怎样？",
        "「{title}」背后的故事，比新闻更精彩",
        "从「{title}」看人性的复杂",
    ]
    for item in items[:5]:
        for tpl in templates:
            angles.append({
                "topic": item.get("title", ""),
                "angle": tpl.format(title=item.get("title", "")),
                "category": item.get("category", ""),
            })
    return angles
