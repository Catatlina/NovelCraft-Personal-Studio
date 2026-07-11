"""TASK-037: Hotspot API with web adapter."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.services.hotspot_collector import fetch_hotspots, store_hotspots, analyze_hotspots, get_hotspot_trend_report

router = APIRouter(prefix="/api/v1", tags=["hotspots"])


@router.get("/hotspots")
def get_hotspots(user: dict = Depends(get_current_user)):
    """TASK-037: Fetch and return current hotspots with creative angles."""
    items = fetch_hotspots()
    if items:
        store_hotspots(items)
    angles = analyze_hotspots(items)
    return {"code": 0, "message": "ok", "data": {"hotspots": items, "creative_angles": angles}}
