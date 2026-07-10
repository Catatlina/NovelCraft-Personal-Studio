"""Timeline & arc extraction from chapters."""
from __future__ import annotations

from app.db import connect, encode, new_id


def extract_timeline(chapter_id: str, chapter_body: str) -> list[dict]:
    """Extract timeline events from chapter text."""
    events = _call_ai("extract_timeline", chapter_body, "提取本章的时间线事件列表。")
    if not events:
        return []
    db = connect()
    for i, ev in enumerate(events):
        db.execute(
            "INSERT INTO timeline_events (id, chapter_id, event_text, event_order) VALUES (%s, %s, %s, %s)",
            (new_id(), chapter_id, ev.get("event", str(ev)), i + 1),
        )
    db.commit()
    db.close()
    return events


def update_arcs(novel_id: str, chapter_body: str) -> list[dict]:
    """Update character arcs based on chapter content."""
    arcs = _call_ai("extract_arcs", chapter_body, "提取本章中人物弧线的进展。")
    if not arcs:
        return []
    db = connect()
    for a in arcs:
        name = a.get("character", a.get("name", ""))
        stage = a.get("stage", a.get("progress", ""))
        db.execute(
            "INSERT INTO arcs (id, novel_id, character_name, stage, goal, status) VALUES (%s, %s, %s, %s, %s, 'in_progress')",
            (new_id(), novel_id, name, stage, a.get("goal", "")),
        )
    db.commit()
    db.close()
    return arcs


def _call_ai(task_type: str, text: str, instructions: str) -> list[dict]:
    try:
        from app.gateway import complete
        from app.db import connect as db_connect
        row = db_connect().execute("SELECT id FROM projects LIMIT 1").fetchone()
        pid = row["id"] if row else ""
        result = complete(
            run_id=None, node_key=None, project_id=pid,
            task_type=task_type, prompt_name=f"narrative.{task_type}",
            variables={"body": text[:5000], "instructions": instructions},
        )
        return result.get("events", result.get("arcs", []))
    except Exception:
        return []
