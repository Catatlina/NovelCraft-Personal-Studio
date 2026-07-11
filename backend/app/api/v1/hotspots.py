"""TASK-037: Hotspot API with web adapter."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.services.hotspot_collector import fetch_hotspots, store_hotspots, analyze_hotspots, get_hotspot_trend_report

router = APIRouter(prefix="/api/v1", tags=["hotspots"])


@router.get("/hotspots")
def get_hotspots(user: dict = Depends(get_current_user)):
    """TASK-037: Fetch current hotspots. Source failures are explicit, never an empty 200."""
    items, source_status = fetch_hotspots()
    if items:
        store_hotspots(items)
    if not items and source_status and all(status.startswith("error") for status in source_status.values()):
        raise HTTPException(status_code=502, detail={
            "code": "HOTSPOT_SOURCES_FAILED", "sources": source_status,
        })
    angles = analyze_hotspots(items)
    return {"code": 0, "message": "ok",
            "data": {"hotspots": items, "creative_angles": angles, "sources": source_status}}


@router.get("/hotspots/trend-report")
def hotspot_trend_report(user: dict = Depends(get_current_user)):
    return {"code": 0, "message": "ok", "data": get_hotspot_trend_report()}
