"""
星禾AI工作台 · AI Engine — 统一AI调用入口

所有模块的AI调用必须通过此Engine，禁止直接调用Provider。
负责：模型管理、Token统计、成本追踪、上下文管理。
"""

from .router import router

__all__ = ["router"]
