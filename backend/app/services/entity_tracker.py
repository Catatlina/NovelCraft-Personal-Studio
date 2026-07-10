"""Entity state tracker — extracts and stores character/location state from chapters."""
from __future__ import annotations

from app.db import connect, encode, new_id


def extract_and_store(chapter_id: str, novel_id: str, chapter_body: str) -> list[dict]:
    """Extract entity states from chapter text and store in entity_states table."""
    states = _extract_via_ai(chapter_body)
    if not states:
        return []

    db = connect()
    for s in states:
        db.execute(
            """INSERT INTO entity_states (id, chapter_id, entity_type, entity_name, location, relationships)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (new_id(), chapter_id, s.get("type", "character"), s.get("name", ""),
             s.get("location", ""), encode(s.get("relationships", {}))),
        )
    db.commit()
    db.close()
    return states


def _extract_via_ai(text: str) -> list[dict]:
    """Use AI to extract entity states from chapter text."""
    try:
        from app.gateway import complete
        from app.db import connect as db_connect
        row = db_connect().execute("SELECT id FROM projects LIMIT 1").fetchone()
        pid = row["id"] if row else ""
        result = complete(
            run_id=None, node_key=None, project_id=pid,
            task_type="extract_entities", prompt_name="narrative.extract_entities",
            variables={"body": text[:6000]},
        )
        return result.get("entities", [])
    except Exception:
        return []


def get_states(novel_id: str, limit: int = 10) -> list[dict]:
    """Get latest entity states for a novel."""
    db = connect()
    rows = db.execute(
        """SELECT DISTINCT ON (entity_name) entity_type, entity_name, location, relationships, updated_at
           FROM entity_states ORDER BY entity_name, updated_at DESC LIMIT %s""",
        (limit,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]
