"""Foreshadowing extraction — AI detects and stores foreshadowing from chapters."""
from __future__ import annotations

from app.db import connect, encode, new_id


def extract_and_store_foreshadowing(chapter_id: str, seq: int, chapter_body: str) -> list[dict]:
    """Extract foreshadowing from chapter text."""
    items = _extract_via_ai(chapter_body)
    if not items:
        return []
    db = connect()
    for item in items:
        db.execute(
            """INSERT INTO foreshadowings (id, chapter_id, content, planned_resolve_chapter, status)
               VALUES (%s, %s, %s, %s, 'planted')""",
            (new_id(), chapter_id, item.get("content", ""), item.get("planned_chapter", seq + 5)),
        )
    db.commit()
    db.close()
    return items


def _extract_via_ai(text: str) -> list[dict]:
    try:
        from app.gateway import complete
        from app.db import connect as db_connect
        row = db_connect().execute("SELECT id FROM projects LIMIT 1").fetchone()
        pid = row["id"] if row else ""
        result = complete(
            run_id=None, node_key=None, project_id=pid,
            task_type="extract_foreshadowing", prompt_name="narrative.extract_foreshadowing",
            variables={"body": text[:5000]},
        )
        return result.get("foreshadowing", [])
    except Exception:
        return []
