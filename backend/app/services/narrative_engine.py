"""C6: Foreshadow到期注入 + 跨章矛盾检测 + 弧线偏移校验"""
from __future__ import annotations
import json
from app.db import connect, decode, encode


def check_foreshadow_due(novel_id: str, current_chapter_seq: int) -> list[dict]:
    """Check if any foreshadows are due for resolution at this chapter."""
    db = connect()
    rows = db.execute(
        """SELECT * FROM foreshadowings 
           WHERE chapter_id IN (SELECT id FROM contents WHERE parent_id = %s)
           AND target_chapter <= %s AND status != 'resolved'
           ORDER BY target_chapter""",
        (novel_id, current_chapter_seq)
    ).fetchall()
    db.close()
    due = []
    for r in rows:
        due.append({
            "id": r["id"], "content": r.get("content", ""),
            "target": r.get("target_chapter", 0),
            "planted_at": str(r.get("plant_chapter", "")),
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
    """TASK-019: Cross-chapter contradiction detection via timeline events."""
    db = connect()
    events = db.execute(
        """SELECT te.*, c.title as chapter_title FROM timeline_events te
           JOIN contents c ON te.chapter_id = c.id
           WHERE c.parent_id = %s ORDER BY te.event_order""",
        (novel_id,)
    ).fetchall()
    db.close()

    conflicts = []
    event_map = {}
    for e in events:
        key = f"{e.get('character_name','')}-{e.get('location','')}"
        if key in event_map:
            prev = event_map[key]
            if e.get("event_time", "") and prev.get("event_time", ""):
                if e["event_time"] < prev["event_time"]:
                    conflicts.append({
                        "type": "timeline_contradiction",
                        "character": e.get("character_name", ""),
                        "chapter_a": prev.get("chapter_title", ""),
                        "chapter_b": e.get("chapter_title", ""),
                        "detail": f"事件 '{e.get('event','')}' 时间早于 '{prev.get('event','')}'",
                    })
        event_map[key] = dict(e)
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
