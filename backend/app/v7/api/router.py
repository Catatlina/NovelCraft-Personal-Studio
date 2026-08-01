"""
V7 API Router — 统一入口
=========================

Registers all V7 API routers under /api/v7 prefix.
"""
from fastapi import APIRouter

from .brain import router as brain_router
from .trace import router as trace_router
from .director import router as director_router

router = APIRouter(prefix="/api/v7", tags=["v7"])

# Brain API
router.include_router(brain_router, prefix="/brain", tags=["brain"])

# Trace API
router.include_router(trace_router, prefix="/trace", tags=["trace"])

# Director API
router.include_router(director_router, prefix="/director", tags=["director"])
