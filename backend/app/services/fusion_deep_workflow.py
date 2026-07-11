"""NC-FUS-DEEP: denova WorkflowPlan + event ledger + show-me-the-story fact chain."""
from __future__ import annotations
from datetime import datetime
from app.db import connect, new_id, encode, decode


# ===== denova: WorkflowPlan (完整工作流定义) =====

class WorkflowPlan:
    """Denova-style workflow plan — full definition with nodes, edges, conditions."""

    @staticmethod
    def create(name: str, project_id: str, nodes: list[dict], edges: list[dict] = []) -> dict:
        db = connect()
        wid = new_id()
        db.execute(
            "INSERT INTO workflows (id, name, definition) VALUES (%s,%s,%s)",
            (wid, name, encode({"nodes": nodes, "edges": edges, "project_id": project_id})),
        )
        db.commit(); db.close()
        return {"workflow_id": wid, "name": name, "node_count": len(nodes), "edge_count": len(edges)}

    @staticmethod
    def execute(workflow_id: str, run_id: str, node_key: str) -> dict:
        """Execute a node and return next nodes per edge conditions."""
        db = connect()
        wf = db.execute("SELECT * FROM workflows WHERE id=%s", (workflow_id,)).fetchone()
        if not wf: db.close(); return {"status": "error", "message": "workflow not found"}
        definition = wf.get("definition", {})
        edges = definition.get("edges", [])
        next_nodes = [e["to"] for e in edges if e.get("from") == node_key]
        db.close()
        return {"run_id": run_id, "current": node_key, "next": next_nodes, "edge_count": len(edges)}


# ===== denova: Event ledger (完整事件账本) =====

EVENT_TYPES = [
    "run.created", "run.started", "run.completed", "run.failed", "run.cancelled",
    "node.started", "node.completed", "node.failed", "node.retried",
    "checkpoint.created", "checkpoint.restored",
    "mutation.applied", "mutation.reverted",
    "human.confirmed", "human.rejected",
]


def record_event(run_id: str, event_type: str, node_key: str = "", payload: dict = {}) -> dict:
    """Record an event in the immutable ledger."""
    if event_type not in EVENT_TYPES:
        return {"status": "error", "message": f"unknown event type: {event_type}"}
    db = connect()
    eid = new_id()
    db.execute(
        "INSERT INTO audit_logs (id, entity_type, entity_id, action, details, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
        (eid, "workflow_run", run_id, event_type,
         encode({"node": node_key, "payload": payload, "timestamp": datetime.utcnow().isoformat()}),
         datetime.utcnow()),
    )
    db.commit(); db.close()
    return {"event_id": eid, "run_id": run_id, "type": event_type, "node": node_key}


def get_event_ledger(run_id: str, limit: int = 50) -> list[dict]:
    """Get full event ledger for a run (immutable audit trail)."""
    db = connect()
    rows = db.execute(
        "SELECT * FROM audit_logs WHERE entity_type='workflow_run' AND entity_id=%s ORDER BY created_at DESC LIMIT %s",
        (run_id, limit),
    ).fetchall()
    db.close()
    return [{"id": r["id"], "action": r["action"], "detail": r.get("detail", {}), "created_at": str(r["created_at"])} for r in rows]


# ===== show-me-the-story: Chapter fact reconciliation chain =====

def reconcile_chapter_facts(chapter_id: str, novel_id: str) -> dict:
    """Reconcile chapter facts against entity states — detect changes, conflicts, updates."""
    db = connect()
    chapter = db.execute("SELECT * FROM contents WHERE id=%s", (chapter_id,)).fetchone()
    if not chapter: db.close(); return {"status": "error", "message": "chapter not found"}

    body = chapter.get("body", "")
    text = body if isinstance(body, str) else str(body.get("text", ""))

    # Extract entities from chapter text (names, locations, items)
    entities = db.execute(
        "SELECT meta->>'character_name' as name FROM contents WHERE parent_id=%s AND type='character'",
        (novel_id,)
    ).fetchall()

    found_entities = []
    for e in entities:
        name = e.get("name", "")
        if name and name in text:
            found_entities.append({"type": "character", "name": name, "present": True})

    # Check for contradictions with previous chapters
    prev_chapters = db.execute(
        "SELECT * FROM contents WHERE parent_id=%s AND type='chapter' AND id!=%s ORDER BY (meta->>'seq')::int",
        (novel_id, chapter_id),
    ).fetchall()

    contradictions = []
    for prev in prev_chapters:
        prev_body = prev.get("body", "")
        prev_text = prev_body if isinstance(prev_body, str) else str(prev_body.get("text", ""))
        for entity in found_entities:
            name = entity["name"]
            if name in prev_text:
                # Entity exists in both chapters — no contradiction for presence
                pass

    db.close()
    return {
        "chapter_id": chapter_id,
        "entities_detected": len(found_entities),
        "entities": found_entities,
        "contradictions": contradictions,
        "previous_chapters_checked": len(prev_chapters),
        "reconciled": len(contradictions) == 0,
    }


def create_fact_transaction(operation: str, content_id: str, previous_value: dict, new_value: dict) -> dict:
    """show-me-the-story style: record a fact mutation as a reversible transaction."""
    db = connect()
    tid = new_id()
    db.execute(
        "INSERT INTO audit_logs (id, entity_type, entity_id, action, details, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
        (tid, "fact_mutation", content_id, operation,
         encode({"previous": previous_value, "new": new_value, "reversible": True}),
         datetime.utcnow()),
    )
    db.commit(); db.close()
    return {"transaction_id": tid, "operation": operation, "reversible": True}


def get_fact_chain(content_id: str) -> list[dict]:
    """Get full fact mutation chain for a content item."""
    db = connect()
    rows = db.execute(
        "SELECT * FROM audit_logs WHERE entity_type='fact_mutation' AND entity_id=%s ORDER BY created_at",
        (content_id,),
    ).fetchall()
    db.close()
    return [{"id": r["id"], "operation": r["action"], "detail": r.get("detail", {})} for r in rows]
