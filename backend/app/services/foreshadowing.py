"""Foreshadowing extraction — AI detects and stores foreshadowing from chapters."""
from __future__ import annotations

from app.db import connect, encode, new_id


def extract_and_store_foreshadowing(chapter_id: str, seq: int, chapter_body: str) -> list[dict]:
    """Extract foreshadowing from chapter text."""
    db = connect()
    row = db.execute("SELECT project_id FROM contents WHERE id = %s", (chapter_id,)).fetchone()
    db.close()
    items = [item for item in _extract_via_ai(chapter_body, row["project_id"] if row else "")
             if isinstance(item, dict)]
    if not items:
        return []
    db = connect()
    for item in items:
        db.execute(
            """INSERT INTO foreshadowings (id, chapter_id, content, planned_resolve_chapter, status)
               VALUES (%s, %s, %s, %s, 'planted')""",
            (new_id(), chapter_id, item.get("content", ""),
             item.get("planned_chapter", item.get("hint_chapter", seq + 5))),
        )
    db.commit()
    db.close()
    return items


def _extract_via_ai(text: str, project_id: str) -> list[dict]:
    from app.gateway import complete
    result = complete(
        run_id=None, node_key=None, project_id=project_id,
        task_type="extract_foreshadowing", prompt_name="narrative.extract_foreshadowing",
        variables={"body": text[:5000]},
    )
    return result.get("foreshadowings", result.get("foreshadowing", []))
