"""插件市场 API"""
from fastapi import APIRouter, Depends
from app.platform.modules.manager import (
    get_all_modules, get_enabled_modules, install_module, uninstall_module, toggle_module, MODULES,
)
from app.schemas import ApiResponse
from app.core.authz import get_current_user

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
def api_install(module_id: str, user: dict = Depends(get_current_user)) -> ApiResponse:
    ok = install_module(module_id)
    return ApiResponse(code=0 if ok else 1, message="installed" if ok else "not found", data={"id": module_id})


@router.post("/{module_id}/uninstall")
def api_uninstall(module_id: str, user: dict = Depends(get_current_user)) -> ApiResponse:
    ok = uninstall_module(module_id)
    return ApiResponse(code=0 if ok else 1, message="uninstalled" if ok else "cannot uninstall builtin", data={"id": module_id})


@router.post("/{module_id}/toggle")
def api_toggle(module_id: str, enabled: bool = True, user: dict = Depends(get_current_user)) -> ApiResponse:
    ok = toggle_module(module_id, enabled)
    return ApiResponse(code=0 if ok else 1, message="toggled" if ok else "failed", data={"id": module_id, "enabled": enabled})
