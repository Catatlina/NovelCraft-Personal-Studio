"""插件市场 API.

The registry is descriptive only until installation is backed by durable
package state. Mutation endpoints therefore fail explicitly instead of
claiming that a module was installed in a process-local dictionary.
"""
from fastapi import APIRouter, Depends, HTTPException
from app.platform.modules.manager import (
    get_all_modules, get_enabled_modules, install_module, uninstall_module, toggle_module, MODULES,
)
from app.schemas import ApiResponse
from app.api.v1.config import require_admin

router = APIRouter(prefix="/api/v1/modules", tags=["Modules"])


@router.get("")
def list_modules(category: str = "") -> ApiResponse:
    cats = get_all_modules()
    result = {}
    for cat, mods in cats.items():
        if category and cat != category:
            continue
        result[cat] = [
            {
                "id": m.id, "name": m.name, "description": m.description,
                "icon": m.icon, "version": m.version, "source": m.source,
                "source_url": m.source_url, "enabled": m.enabled,
                "installed": m.installed, "route": m.route, "category": m.category,
            }
            for m in mods
        ]
    return ApiResponse(code=0, message="ok", data={"categories": result, "total": len(MODULES)})


@router.post("/{module_id}/install")
def api_install(module_id: str, user: dict = Depends(require_admin)) -> ApiResponse:
    raise HTTPException(
        status_code=501,
        detail={"code": "MODULE_INSTALL_NOT_IMPLEMENTED", "message": "插件安装尚未接入持久化执行器"},
    )


@router.post("/{module_id}/uninstall")
def api_uninstall(module_id: str, user: dict = Depends(require_admin)) -> ApiResponse:
    raise HTTPException(
        status_code=501,
        detail={"code": "MODULE_UNINSTALL_NOT_IMPLEMENTED", "message": "插件卸载尚未接入持久化执行器"},
    )


@router.post("/{module_id}/toggle")
def api_toggle(module_id: str, enabled: bool = True, user: dict = Depends(require_admin)) -> ApiResponse:
    module = MODULES.get(module_id)
    if module is None:
        raise HTTPException(status_code=404, detail={"code": "MODULE_NOT_FOUND", "message": "插件不存在"})
    if not module.installed:
        raise HTTPException(
            status_code=409,
            detail={"code": "MODULE_NOT_INSTALLED", "message": "插件尚未安装，不能启用或禁用"},
        )
    if not toggle_module(module_id, enabled):
        raise HTTPException(status_code=500, detail={"code": "MODULE_STATE_WRITE_FAILED", "message": "插件状态写入失败"})
    return ApiResponse(
        code=0,
        message="ok",
        data={
            "id": module.id,
            "enabled": module.enabled,
            "installed": module.installed,
            "persisted": True,
        },
    )
