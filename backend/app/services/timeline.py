"""Timeline & arc extraction from chapters."""
from __future__ import annotations

from app.db import connect, encode, new_id


def extract_timeline(chapter_id: str, chapter_body: str) -> list[dict]:
    """Extract timeline events from chapter text."""
    project_id = _content_project_id(chapter_id)
    events = _call_ai("extract_timeline", chapter_body, "提取本章的时间线事件列表。", project_id)
    if not events:
        return []
    db = connect()
    for i, ev in enumerate(events):
        event_text = ev.get("event", str(ev)) if isinstance(ev, dict) else str(ev)
        db.execute(
            "INSERT INTO timeline_events (id, chapter_id, event_text, event_order) VALUES (%s, %s, %s, %s)",
            (new_id(), chapter_id, event_text, i + 1),
        )
    db.commit()
    db.close()
    return events


def update_arcs(novel_id: str, chapter_body: str) -> list[dict]:
    """Update character arcs based on chapter content."""
    arcs = _call_ai("extract_arcs", chapter_body, "提取本章中人物弧线的进展。",
                    _content_project_id(novel_id))
    if not arcs:
        return []
    db = connect()
    for a in (item for item in arcs if isinstance(item, dict)):
        name = a.get("character", a.get("name", ""))
        stage = a.get("stage", a.get("progress", ""))
        db.execute(
            "INSERT INTO arcs (id, novel_id, character_name, stage, goal, status) VALUES (%s, %s, %s, %s, %s, 'in_progress')",
            (new_id(), novel_id, name, stage, a.get("goal", "")),
        )
    db.commit()
    db.close()
    return arcs


def _content_project_id(content_id: str) -> str:
    db = connect()
    row = db.execute("SELECT project_id FROM contents WHERE id = %s", (content_id,)).fetchone()
    db.close()
    return row["project_id"] if row else ""


def _call_ai(task_type: str, text: str, instructions: str, project_id: str) -> list[dict]:
    try:
        from app.gateway import complete
        result = complete(
            run_id=None, node_key=None, project_id=project_id,
            task_type=task_type, prompt_name=f"narrative.{task_type}",
            variables={"body": text[:5000], "instructions": instructions},
        )
        return result.get("events", result.get("arcs", []))
    except Exception:
        return []
