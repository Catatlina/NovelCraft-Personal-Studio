"""TASK-027: DAG workflow execution endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.db import connect, row_to_dict

router = APIRouter(prefix="/api/v1/admin/workflows", tags=["workflows"])


def ok(data: dict) -> dict:
    return {"code": 0, "message": "ok", "data": data}


@router.post("/{name}/execute")
def execute_workflow(name: str, project_id: str, novel_id: str,
                     user: dict = Depends(get_current_user)):
    """Execute a saved workflow. Only the bootstrap chain has a real executor today;
    other graphs get an explicit 501 instead of being silently run as bootstrap
    (the old behavior inserted project_id='' — a guaranteed UUID error — and
    dispatched execute_bootstrap regardless of the requested workflow)."""
    conn = connect()
    member = conn.execute(
        "SELECT role FROM project_members WHERE project_id = %s AND user_id = %s",
        (project_id, user["id"]),
    ).fetchone()
    if not member or member["role"] not in {"owner", "editor"}:
        conn.close()
        raise HTTPException(status_code=403, detail="insufficient permissions")
    wf = row_to_dict(conn.execute("SELECT * FROM workflows WHERE name = %s", (name,)).fetchone())
    novel = row_to_dict(conn.execute(
        "SELECT id FROM contents WHERE id = %s AND project_id = %s AND type = 'novel'",
        (novel_id, project_id)).fetchone())
    conn.close()
    if not wf:
        raise HTTPException(status_code=404, detail=f"workflow '{name}' not found")
    if not novel:
        raise HTTPException(status_code=404, detail="novel not found in project")
    if name != "bootstrap":
        raise HTTPException(status_code=501, detail={
            "code": "WORKFLOW_EXECUTOR_NOT_IMPLEMENTED",
            "message": f"workflow '{name}' has no dedicated executor; only 'bootstrap' is runnable",
        })
    from app.workers.tasks import create_run
    run_id = create_run(project_id, novel_id)
    return ok({"run_id": run_id, "workflow": name, "status": "dispatched"})
