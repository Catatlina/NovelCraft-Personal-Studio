"""
星禾AI工作台 · Skill API
"""
from fastapi import APIRouter, Depends
from app.core.authz import get_current_user
from app.platform.skills.manager import SkillManager

router = APIRouter(prefix="/api/v1/skills", tags=["Skills"])


@router.get("")
def list_skills(user=Depends(get_current_user)):
    """列出所有可用 Skills（含安装状态）"""
    skills = SkillManager.list_skills(user_id=user["id"])
    return {"code": "SUCCESS", "data": {"items": skills}}


@router.post("/{skill_id}/install")
def install_skill(skill_id: str, user=Depends(get_current_user)):
    """安装 Skill"""
    SkillManager.install(user["id"], skill_id)
    return {"code": "SUCCESS", "message": "安装成功"}


@router.put("/{skill_id}/toggle")
def toggle_skill(skill_id: str, active: bool = True, user=Depends(get_current_user)):
    """启用/禁用 Skill"""
    SkillManager.toggle(user["id"], skill_id, active)
    return {"code": "SUCCESS", "message": "已启用" if active else "已禁用"}


@router.delete("/{skill_id}")
def uninstall_skill(skill_id: str, user=Depends(get_current_user)):
    """卸载 Skill"""
    SkillManager.uninstall(user["id"], skill_id)
    return {"code": "SUCCESS", "message": "已卸载"}
