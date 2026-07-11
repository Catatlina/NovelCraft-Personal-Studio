"""TASK-045: Overseas translation + localization endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
router = APIRouter(prefix="/api/v1/overseas", tags=["overseas"])


@router.get("/languages")
def supported_languages():
    """List supported target languages."""
    return {"code": 0, "message": "ok", "data": [
        {"code": "en", "name": "English"},
        {"code": "ja", "name": "Japanese"},
        {"code": "ko", "name": "Korean"},
        {"code": "es", "name": "Spanish"},
        {"code": "fr", "name": "French"},
        {"code": "de", "name": "German"},
        {"code": "pt", "name": "Portuguese"},
    ]}
