"""
星禾AI工作台 · Agent API
"""
from fastapi import APIRouter, Depends, Query
from ..core.authz import get_current_user
from ..platform.agents.manager import AgentManager

router = APIRouter(prefix="/api/v1/agents", tags=["Agents"])


@router.get("")
def list_agents(user=Depends(get_current_user)):
    """列出所有可用 Agents"""
    agents = AgentManager.list_agents()
    return {"code": "SUCCESS", "data": {"items": agents}}


@router.get("/runs")
def list_all_runs(limit: int = 20, user=Depends(get_current_user)):
    """所有 Agent 运行历史"""
    runs = AgentManager.list_runs(user_id=user["id"], limit=limit)
    return {"code": "SUCCESS", "data": {"items": runs}}


@router.get("/{agent_id}")
def get_agent(agent_id: str, user=Depends(get_current_user)):
    """获取 Agent 详情"""
    agent = AgentManager.get_agent(agent_id)
    if not agent:
        return {"code": "NOT_FOUND", "message": "Agent 不存在"}
    return {"code": "SUCCESS", "data": agent}


@router.post("/{agent_id}/run")
def run_agent(agent_id: str, project_id: str = Query(None), user=Depends(get_current_user)):
    """运行 Agent"""
    run_id = AgentManager.start_run(agent_id, user["id"], project_id)
    AgentManager.update_run_status(run_id, "running", 0)
    return {"code": "SUCCESS", "data": {"run_id": run_id, "status": "running"}}


@router.get("/{agent_id}/runs")
def list_runs(agent_id: str, limit: int = 20, user=Depends(get_current_user)):
    """Agent 运行历史"""
    runs = AgentManager.list_runs(agent_id=agent_id, user_id=user["id"], limit=limit)
    return {"code": "SUCCESS", "data": {"items": runs}}
