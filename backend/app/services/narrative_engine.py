"""C6: Foreshadow到期注入 + 跨章矛盾检测 + 弧线偏移校验"""
from __future__ import annotations
import json
from app.db import connect, decode, encode


def check_foreshadow_due(novel_id: str, current_chapter_seq: int) -> list[dict]:
    """Check if any foreshadows are due for resolution at this chapter."""
    db = connect()
    rows = db.execute(
        """SELECT f.*, (c.meta->>'seq') AS planted_seq FROM foreshadowings f
           JOIN contents c ON c.id = f.chapter_id
           WHERE c.parent_id = %s
           AND f.planned_resolve_chapter <= %s AND f.status != 'resolved'
           ORDER BY f.planned_resolve_chapter""",
        (novel_id, current_chapter_seq)
    ).fetchall()
    db.close()
    due = []
    for r in rows:
        due.append({
            "id": r["id"], "content": r.get("content", ""),
            "target": r.get("planned_resolve_chapter", 0),
            "planted_at": str(r.get("planted_seq") or ""),
            "status": r.get("status", "unknown"),
        })
    return due


def inject_foreshadow_context(due_items: list[dict]) -> str:
    """Generate a context injection for due foreshadows."""
    if not due_items:
        return ""
    lines = ["⚠️ 以下伏笔已到期，必须在本章中回收："]

    for item in due_items:
        lines.append(f"- [{item['status']}] {item['content'][:120]}")
    return "\n".join(lines)


def detect_cross_chapter_conflicts(novel_id: str) -> list[dict]:
    """TASK-019: Contradiction detection from persisted entity states.

    The previous version queried timeline_events columns that do not exist
    (character_name/event_time), so it silently never found anything. Entity
    states are what the pipeline actually records per chapter."""
    db = connect()
    rows = db.execute(
        """SELECT es.entity_name, es.location, c.title AS chapter_title,
                  (c.meta->>'seq')::int AS seq
           FROM entity_states es JOIN contents c ON c.id = es.chapter_id
           WHERE c.parent_id = %s AND es.entity_type = 'character'
             AND COALESCE(es.location, '') != ''
           ORDER BY seq, es.entity_name, es.created_at""",
        (novel_id,)
    ).fetchall()
    db.close()

    conflicts = []
    seen: dict[tuple, dict] = {}
    for row in rows:
        key = (row["entity_name"], row["seq"])
        prev = seen.get(key)
        if prev and prev["location"] != row["location"]:
            conflicts.append({
                "type": "entity_location_contradiction",
                "character": row["entity_name"],
                "chapter_a": prev.get("chapter_title", ""),
                "chapter_b": row.get("chapter_title", ""),
                "detail": f"{row['entity_name']} 在第{row['seq']}章被同时记录于 '{prev['location']}' 与 '{row['location']}'",
            })
        seen[key] = dict(row)
    return conflicts


def validate_character_arc(novel_id: str, arc_config: list[dict]) -> list[dict]:
    """TASK-019: Validate character arcs against current progress."""
    db = connect()
    characters = db.execute(
        "SELECT DISTINCT meta->'character_name' as name FROM contents WHERE parent_id = %s AND type = 'character'",
        (novel_id,)
    ).fetchall()
    db.close()

    issues = []
    for arc in arc_config:
        name = arc.get("name", "")
        expected_stage = arc.get("stage", "")
        target_chapter = arc.get("target_chapter", 0)
        if target_chapter > 0 and target_chapter < arc.get("current_chapter", 0):
            issues.append({
                "character": name,
                "issue": f"弧线阶段 '{expected_stage}' 应于第{target_chapter}章完成，现已超期",
                "suggestion": "调整弧线进度或推进剧情",
            })
    return issues
