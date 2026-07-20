"""AI Memory system — long-term context retention across chapters.

Ensures character consistency, plot coherence, and prevents 
AI from "forgetting" established facts across long novels.
"""
from app.db import connect, encode, decode, row_to_dict


def get_novel_memory(novel_id: str) -> dict:
    """Retrieve aggregated memory for a novel: characters, world, timeline, arcs."""
    db = connect()
    try:
        # Characters
        chars = [
            row_to_dict(r)
            for r in db.execute(
                "SELECT id, name, role, traits, relationships, status FROM entity_states WHERE novel_id=%s AND entity_type='character' ORDER BY updated_at DESC",
                (novel_id,),
            ).fetchall()
        ]
        # Timeline
        timeline = [
            row_to_dict(r)
            for r in db.execute(
                "SELECT id, event, chapter_no, chapter_title, status FROM timeline_events WHERE novel_id=%s ORDER BY chapter_no",
                (novel_id,),
            ).fetchall()
        ]
        # Foreshadowing
        foreshadowing = [
            row_to_dict(r)
            for r in db.execute(
                "SELECT id, description, status, resolved_in_chapter, created_in_chapter FROM foreshadowings WHERE novel_id=%s ORDER BY created_in_chapter",
                (novel_id,),
            ).fetchall()
        ]
        # Recent chapter summaries
        summaries = [
            row_to_dict(r)
            for r in db.execute(
                "SELECT meta FROM contents WHERE project_id=(SELECT project_id FROM contents WHERE id=%s LIMIT 1) AND type='chapter' AND meta->>'chapter_summary' IS NOT NULL ORDER BY updated_at DESC LIMIT 10",
                (novel_id,),
            ).fetchall()
        ]

        return {
            "novel_id": novel_id,
            "characters": len(chars),
            "character_details": [{"name": c.get("name"), "role": c.get("role"), "traits": c.get("traits")} for c in chars[:10]],
            "timeline_events": len(timeline),
            "recent_events": [t.get("event", "")[:100] for t in timeline[-5:]],
            "foreshadowing_total": len(foreshadowing),
            "unresolved_foreshadowing": [f.get("description", "")[:100] for f in foreshadowing if f.get("status") != "resolved"],
            "chapter_summaries": [decode(s.get("meta", {}), {}).get("chapter_summary", "")[:200] for s in summaries if s.get("meta")],
        }
    finally:
        db.close()


def inject_memory_context(project_id: str, current_chapters: int) -> str:
    """Build a context string for AI prompts, summarizing the novel's state."""
    mem = None
    db = connect()
    try:
        novel = db.execute(
            "SELECT id FROM contents WHERE project_id=%s AND type='novel' LIMIT 1",
            (project_id,),
        ).fetchone()
        if novel:
            mem = get_novel_memory(novel[0])
    finally:
        db.close()

    if not mem:
        return ""

    ctx = f"[Memory: {mem['characters']} characters, {mem['timeline_events']} events, {mem['foreshadowing_total']} foreshadowings]\n"

    if mem["character_details"]:
        ctx += "Key Characters:\n"
        for c in mem["character_details"]:
            ctx += f"- {c.get('name', 'Unknown')}: {c.get('role', '')} | {c.get('traits', '')}\n"

    if mem["recent_events"]:
        ctx += "\nRecent Events:\n"
        for e in mem["recent_events"]:
            ctx += f"- {e}\n"

    if mem["unresolved_foreshadowing"]:
        ctx += f"\nUnresolved Foreshadowing ({len(mem['unresolved_foreshadowing'])}):\n"
        for f in mem["unresolved_foreshadowing"][:5]:
            ctx += f"- {f}\n"

    return ctx
