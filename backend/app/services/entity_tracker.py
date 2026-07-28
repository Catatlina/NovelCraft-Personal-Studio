"""Entity state tracker — extracts and stores character/location state from chapters."""
from __future__ import annotations

from typing import Any

from app.db import connect, encode, new_id

# V3 §9: known_info split into 5 cognition layers.
KNOWN_INFO_LAYERS = [
    "world_facts",            # 世界事实（客观存在，不代表任何人知道）
    "reader_known",           # 读者已知（叙事已揭示给读者）
    "protagonist_known",      # 主角已知
    "character_known",        # 该角色已知
    "character_misunderstood",  # 该角色误解的内容（明确记录错误认知）
]


def split_known_info(known_info: Any) -> dict[str, list[str]]:
    """Split a character's known_info into the 5 V3 cognition layers (§9.2).

    Accepts a list of strings/dicts. Dicts may carry an explicit ``layer`` or a
    ``misunderstood`` flag; anything unmarked defaults to world_facts. Pure and
    deterministic so it is fully unit-testable.
    """
    result = {k: [] for k in KNOWN_INFO_LAYERS}
    items = known_info if isinstance(known_info, list) else ([known_info] if known_info else [])
    for it in items:
        if isinstance(it, dict):
            txt = str(it.get("text", "")).strip()
            if not txt:
                continue
            layer = str(it.get("layer", "")).strip()
            if layer in result:
                result[layer].append(txt)
            elif it.get("misunderstood"):
                result["character_misunderstood"].append(txt)
            else:
                result["world_facts"].append(txt)
        else:
            text = str(it).strip()
            if text:
                result["world_facts"].append(text)
    return result


def extract_and_store(chapter_id: str, novel_id: str, chapter_body: str) -> list[dict]:
    """Extract entity states from chapter text and store in entity_states table."""
    db = connect()
    row = db.execute("SELECT project_id FROM contents WHERE id = %s", (chapter_id,)).fetchone()
    db.close()
    states = [item for item in _extract_via_ai(chapter_body, row["project_id"] if row else "")
              if isinstance(item, dict)]
    if not states:
        return []

    db = connect()
    for s in states:
        known = split_known_info(s.get("known_info"))
        db.execute(
            """INSERT INTO entity_states (id, chapter_id, entity_type, entity_name, location, relationships, known_info)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (new_id(), chapter_id, s.get("type", "character"), s.get("name", ""),
             s.get("location", ""), encode(s.get("relationships", {})), encode(known)),
        )
    db.commit()
    db.close()
    return states


def _extract_via_ai(text: str, project_id: str) -> list[dict]:
    """Use AI to extract entity states from chapter text."""
    from app.gateway import complete
    result = complete(
        run_id=None, node_key=None, project_id=project_id,
        task_type="extract_entities", prompt_name="narrative.extract_entities",
        variables={"body": text[:6000]},
    )
    return result.get("entities", [])


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
