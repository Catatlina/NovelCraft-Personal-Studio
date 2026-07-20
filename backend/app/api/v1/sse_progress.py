"""SSE endpoint for real-time run progress updates.
Usage: GET /api/v1/runs/{run_id}/stream
"""
import asyncio
import json
import time
from app.db import connect, row_to_dict


async def run_progress_stream(run_id: str):
    """SSE generator that yields run status updates."""
    last_status = None
    for _ in range(120):  # max 2 minutes
        db = connect()
        try:
            row = db.execute(
                "SELECT id, status, current_node_key, context FROM workflow_runs WHERE id=%s",
                (run_id,),
            ).fetchone()
            if not row:
                yield f"data: {json.dumps({'event': 'error', 'message': 'run not found'})}\n\n"
                return
            run = row_to_dict(row)
            nodes = [
                row_to_dict(n)
                for n in db.execute(
                    "SELECT node_key, kind, title, status, output FROM run_nodes WHERE run_id=%s ORDER BY node_key",
                    (run_id,),
                ).fetchall()
            ]
            state = {"status": run["status"], "current_node": run.get("current_node_key"), "nodes": nodes}
            if state != last_status:
                last_status = state
                yield f"data: {json.dumps(state, ensure_ascii=False)}\n\n"
            if run["status"] in ("succeeded", "failed", "cancelled"):
                yield f"data: {json.dumps({'event': 'done', 'status': run['status']})}\n\n"
                return
        finally:
            db.close()
        await asyncio.sleep(2)
    yield f"data: {json.dumps({'event': 'timeout'})}\n\n"
