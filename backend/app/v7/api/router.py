"""
V7 API Router — 统一入口
=========================

Registers all V7 API routers under /api/v7 prefix.
"""
from fastapi import APIRouter

from .brain import router as brain_router
from .trace import router as trace_router
from .director import router as director_router
from .cost import router as cost_router
from .prompt import router as prompt_router
from .genres import router as genres_router
from .series import router as series_router
from .branch_generator import router as branch_router

router = APIRouter(prefix="/api/v7", tags=["v7"])

# Brain API
router.include_router(brain_router, prefix="/brain", tags=["brain"])

# Trace API
router.include_router(trace_router, prefix="/trace", tags=["trace"])

# Director API
router.include_router(director_router, prefix="/director", tags=["director"])

# Cost API
router.include_router(cost_router, prefix="/cost", tags=["cost"])

# Prompt API
router.include_router(prompt_router, prefix="/prompt", tags=["prompt"])

# Genres API
router.include_router(genres_router, prefix="/genres", tags=["genres"])

# Series API
router.include_router(series_router, prefix="/series", tags=["series"])

# Branch Generator API
router.include_router(branch_router, prefix="/branches", tags=["branches"])
