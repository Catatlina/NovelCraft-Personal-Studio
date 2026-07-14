"""NC-FUS-DEEP: denova event ledger + show-me-the-story fact transaction chain.

denova WorkflowPlan note: the upstream "workflow plan" capability is served by
the product paths PUT /api/v1/config/workflows/{name} (definition CRUD) and
POST /api/v1/admin/workflows/{name}/execute (run_nodes seeding + dispatch).
A standalone WorkflowPlan helper duplicated that chain with no product caller
and was removed per docs/23 (no-caller code must not be reported as integrated).
Likewise the former reconcile_chapter_facts helper duplicated the active
write-after-reconcile pipeline (app.workers.tasks._write_after_reconcile).
"""
from __future__ import annotations
from datetime import datetime, timezone
from app.db import connect, new_id, encode, decode


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
         encode({"node": node_key, "payload": payload, "timestamp": datetime.now(timezone.utc).isoformat()}),
         datetime.now(timezone.utc)),
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
    return [{"id": r["id"], "action": r["action"], "detail": decode(r.get("details"), {}),
             "created_at": str(r["created_at"])} for r in rows]


# ===== show-me-the-story: Chapter fact transaction chain =====

def create_fact_transaction(operation: str, content_id: str, previous_value: dict, new_value: dict) -> dict:
    """show-me-the-story style: record a fact mutation as a reversible transaction."""
    db = connect()
    tid = new_id()
    db.execute(
        "INSERT INTO audit_logs (id, entity_type, entity_id, action, details, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
        (tid, "fact_mutation", content_id, operation,
         encode({"previous": previous_value, "new": new_value, "reversible": True}),
         datetime.now(timezone.utc)),
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
    return [{"id": r["id"], "operation": r["action"], "detail": decode(r.get("details"), {}),
             "created_at": str(r["created_at"])} for r in rows]
