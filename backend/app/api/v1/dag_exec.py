"""TASK-027: DAG workflow execution endpoint."""
from __future__ import annotations

import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.db import connect, decode, encode, row_to_dict

router = APIRouter(prefix="/api/v1/admin/workflows", tags=["workflows"])


def ok(data: dict) -> dict:
    return {"code": 0, "message": "ok", "data": data}


@router.post("/{name}/execute")
def execute_workflow(name: str, user: dict = Depends(get_current_user)):
    """Execute a saved DAG workflow."""
    conn = connect()
    wf = row_to_dict(conn.execute("SELECT * FROM workflows WHERE name = %s", (name,)).fetchone())
    conn.close()
    if not wf:
        raise HTTPException(status_code=404, detail=f"workflow '{name}' not found")
    meta = wf.get("meta")
    nodes = decode(meta if isinstance(meta, str) else "{}", {})
    nl = nodes.get("nodes", [])
    if not nl:
        raise HTTPException(status_code=400, detail="no nodes in workflow")
    from app.workers.tasks import execute_bootstrap
    run_id = str(_uuid.uuid4())
    conn2 = connect()
    conn2.execute(
        "INSERT INTO workflow_runs (id, project_id, novel_id, workflow_name, status, context, current_node_key) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (run_id, "", "", name, "running", encode(nodes), nl[0].get("key","") if nl else ""),
    )
    conn2.commit(); conn2.close()
    execute_bootstrap.delay(run_id, nl[0].get("key","n1") if nl else "n1")
    return ok({"run_id": run_id, "workflow": name, "status": "dispatched"})
