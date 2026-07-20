"""TASK-027: DAG workflow execution endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.db import connect, row_to_dict, new_id, encode
from app.core.authz import ok

router = APIRouter(prefix="/api/v1/admin/workflows", tags=["workflows"])


@router.post("/{name}/execute")
def execute_workflow(name: str, project_id: str, novel_id: str,
                     user: dict = Depends(get_current_user)):
    """Execute a saved workflow. Bootstrap uses its versioned executor; custom DAGs
    are dispatched by seeding run_nodes from the workflow definition and dispatching
    via celery."""
    conn = connect()
    member = conn.execute(
        "SELECT role FROM project_members WHERE project_id = %s AND user_id = %s",
        (project_id, user["id"]),
    ).fetchone()
    if not member or member["role"] not in {"owner", "editor"}:
        conn.close()
        raise HTTPException(status_code=403, detail="insufficient permissions")
    wf = row_to_dict(conn.execute(
        """SELECT * FROM workflows
           WHERE name=%s AND is_deleted=FALSE AND (project_id=%s OR project_id IS NULL)
           ORDER BY (project_id IS NOT NULL) DESC LIMIT 1""",
        (name, project_id),
    ).fetchone())
    novel = row_to_dict(conn.execute(
        "SELECT id FROM contents WHERE id = %s AND project_id = %s AND type = 'novel'",
        (novel_id, project_id)).fetchone())
    if not novel:
        conn.close()
        raise HTTPException(status_code=404, detail="novel not found in project")

    # ---- Bootstrap: versioned system executor ----
    if name == "bootstrap":
        conn.close()
        from app.workers.tasks import create_run
        run_id = create_run(project_id, novel_id)
        return ok({"run_id": run_id, "workflow": name, "status": "dispatched"})

    # ---- Custom DAG: execute from workflow definition ----
    if not wf:
        conn.close()
        raise HTTPException(status_code=404, detail=f"workflow '{name}' not found in project")

    definition = wf.get("definition", {})
    nodes = definition.get("nodes", []) if isinstance(definition, dict) else []
    if not nodes:
        conn.close()
        return ok({"run_id": None, "workflow": name, "status": "failed",
                    "message": "No nodes in workflow definition"})

    # Create a workflow run
    novel_meta = novel.get("meta", {}) if isinstance(novel.get("meta"), dict) else {}
    context = {"novel_id": novel_id, "idea": novel_meta.get("idea", ""), **novel_meta}
    run_id = new_id()
    conn.execute(
        "INSERT INTO workflow_runs "
        "(id, project_id, novel_id, workflow_key, status, current_node_key, context) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (run_id, project_id, novel_id, name, "pending", "n1", encode(context)),
    )

    # Seed run_nodes from workflow definition
    for i, node in enumerate(nodes):
        node_key = node.get("key", f"n{i+1}")
        conn.execute(
            "INSERT INTO run_nodes (id, run_id, node_key, kind, agent, title, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (new_id(), run_id, node_key,
             node.get("kind", "agent"),
             node.get("agent"),
             node.get("title", node.get("label", f"Node {i+1}")),
             "pending"),
        )
    conn.commit()
    conn.close()

    # Dispatch via celery
    from app.workers.tasks import dispatch_bootstrap_run
    dispatch_bootstrap_run(run_id, "n1")

    return ok({"run_id": run_id, "workflow": name, "status": "dispatched",
               "total_nodes": len(nodes)})
