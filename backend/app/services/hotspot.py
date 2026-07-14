"""M3: Hotspot monitoring — real-source daily briefing.

This module must never ask an AI model to invent "current hotspots". Hotspot
facts come only from the collector or already-stored collected items; AI may
only transform those real-source items into drafts/briefings.
"""
from __future__ import annotations

from fastapi import HTTPException

from app.db import connect, row_to_dict
from app.gateway import complete


def fetch_hotspots(project_id: str, user_id: str = "") -> list[dict]:
    """Fetch current hotspots from real configured/public sources only.

    The previous implementation used an LLM to "list current hot topics" and
    stored those invented items as kind=hotspot. That violates the product's
    real-data requirement, so this function now delegates to hotspot_collector.
    """
    from app.services.hotspot_collector import fetch_hotspots as collect_hotspots, store_hotspots

    items, source_status = collect_hotspots(user_id=user_id)
    if items:
        store_hotspots(items)
        return items
    if source_status and all(status.startswith("error") for status in source_status.values()):
        raise HTTPException(status_code=502, detail={"code": "HOTSPOT_SOURCES_FAILED", "sources": source_status})
    return []


def _recent_stored_hotspots(project_id: str, limit: int = 10) -> list[dict]:
    """Fallback to recent real collected hotspot rows, never generated rows."""
    db = connect()
    rows = db.execute(
        """
        SELECT title, body, meta, created_at
        FROM knowledge_items
        WHERE kind='hotspot'
          AND created_at > now() - interval '24 hours'
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    db.close()
    out: list[dict] = []
    for row in rows:
        item = row_to_dict(row)
        meta = item.get("meta") or {}
        out.append({
            "title": item.get("title", ""),
            "source": meta.get("source", ""),
            "category": meta.get("category", "general"),
            "raw_score": meta.get("score", 0),
            "url": meta.get("url", ""),
            "fetched_at": meta.get("fetched_at") or str(item.get("created_at", "")),
        })
    return out


def generate_daily_briefing(project_id: str, user_id: str = "") -> dict:
    """Generate daily content briefing from collected hotspots only."""
    topics = fetch_hotspots(project_id, user_id=user_id) or _recent_stored_hotspots(project_id)
    if not topics:
        return {"status": "no_topics", "topics": [], "source": "real_collector"}

    # Generate platform-specific drafts
    briefing = {"topics": topics, "generated": [], "source": "real_collector"}
    from app.prompt_registry import sanitize_untrusted
    for topic in topics[:3]:
        try:
            draft = complete(
                run_id=None, node_key=None, project_id=project_id,
                task_type="hm_daily_brief", prompt_name="social.gen_daily_brief",
                variables={"topic": sanitize_untrusted(topic.get("title", ""), 120),
                           "angle": sanitize_untrusted(
                               f"来源：{topic.get('source','')}；分类：{topic.get('category','')}；链接：{topic.get('url','')}",
                               300,
                           )},
            )
            briefing["generated"].append({"topic": topic.get("title"), "draft": draft})
        except Exception as exc:
            briefing["generated"].append({"topic": topic.get("title"), "status": "failed", "error": str(exc)})
    return briefing
