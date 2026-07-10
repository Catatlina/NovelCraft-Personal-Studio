"""TASK-037+039: Hotspot API + Prompt A/B testing."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.services.hotspot_collector import fetch_hotspots, store_hotspots, analyze_hotspots

router = APIRouter(prefix="/api/v1", tags=["hotspots", "prompt_lab"])


@router.get("/hotspots")
def get_hotspots(user: dict = Depends(get_current_user)):
    """TASK-037: Fetch and return current hotspots with creative angles."""
    items = fetch_hotspots()
    store_hotspots(items)
    angles = analyze_hotspots(items)
    return {"code": 0, "message": "ok", "data": {"hotspots": items, "creative_angles": angles}}


@router.post("/prompts/lab")
def prompt_lab_compare(
    prompt_name: str,
    variables: dict,
    models: list[str] = ["deepseek-chat"],
    user: dict = Depends(get_current_user),
):
    """TASK-039: A/B comparison — run same prompt across multiple models."""
    from app.gateway import complete
    results = []
    for model in models:
        try:
            output = complete(
                run_id=None, node_key=None, project_id="",
                task_type=f"lab_{prompt_name}", prompt_name=prompt_name,
                variables=variables,
            )
            results.append({"model": model, "status": "success", "output": output})
        except Exception as e:
            results.append({"model": model, "status": "error", "error": str(e)})
    return {"code": 0, "message": "ok", "data": {"prompt": prompt_name, "results": results}}
