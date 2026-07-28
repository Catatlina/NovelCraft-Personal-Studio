"""
星禾AI工作台 · AI Engine Router — 统一AI调用API
"""

import json
from fastapi import APIRouter, Depends, Request, Body, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..core.authz import get_current_user
from ..core.errors import public_message
from ..config import settings
from .. import gateway as gw

router = APIRouter(prefix="/api/v1/engine", tags=["AI Engine"])


class ChatRequest(BaseModel):
    messages: list[dict] = Body(...)
    model: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int = 2000


@router.post("/chat")
async def chat(request: ChatRequest, user=Depends(get_current_user)):
    """通用AI对话（SSE流式）"""
    prompt_text = "\n".join(
        f"{m.get('role','user')}: {m.get('content','')}" for m in request.messages
    )

    async def stream():
        yield f"data: {json.dumps({'type':'start','model':request.model})}\n\n"
        try:
            for delta in gw._deepseek_stream(prompt_text, request.model, {"temperature": request.temperature, "max_tokens": request.max_tokens}, {"input": 0, "output": 0}):
                if isinstance(delta, str):
                    yield f"data: {json.dumps({'type':'delta','content':delta})}\n\n"
                elif isinstance(delta, dict) and "error" in delta:
                    yield f"data: {json.dumps({'type':'error','message':delta['error']})}\n\n"
            yield f"data: {json.dumps({'type':'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','message':str(e)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/models")
def list_models(user=Depends(get_current_user)):
    """列出可用AI模型"""
    configured = bool(settings.deepseek_api_key)
    return {
        "code": "SUCCESS",
        "data": {
            "models": [
                {
                    "id": settings.deepseek_model,
                    "provider": "deepseek",
                    "status": "available" if configured else "unconfigured",
                },
            ]
        },
    }


@router.get("/usage")
def get_usage(user=Depends(get_current_user)):
    """获取Token使用统计"""
    db = None
    try:
        from ..db import connect
        db = connect(); cur = db.cursor()
        cur.execute(
            "SELECT COALESCE(SUM(input_tokens)+SUM(output_tokens),0) as total_tokens,"
            " COALESCE(SUM(cost_cny),0) as total_cost FROM ai_calls WHERE user_id=%s"
            " AND created_at >= date_trunc('month', NOW())", (user["id"],)
        )
        row = cur.fetchone(); cur.close()
        total_tokens = int(row[0]) if row else 0
        total_cost = float(row[1]) if row else 0
        cur2 = db.cursor()
        cur2.execute("SELECT monthly_budget_cny FROM subscriptions s JOIN plans p ON s.plan_id=p.id WHERE s.user_id=%s AND s.status='active'", (user["id"],))
        budget_row = cur2.fetchone(); cur2.close()
        budget = float(budget_row[0]) if budget_row else 0
        return {"code": "SUCCESS", "data": {"used_tokens": total_tokens, "used_cost_cny": round(total_cost, 4), "budget_cny": budget}}
    except Exception as exc:
        raise HTTPException(503, public_message(exc, "用量统计暂时不可用")) from exc
    finally:
        if db is not None:
            db.close()


@router.get("/healthz")
def engine_health():
    """健康检查"""
    configured = bool(settings.deepseek_api_key)
    return {
        "code": "SUCCESS",
        "data": {
            "status": "ok" if configured else "degraded",
            "providers": [{"id": "deepseek", "configured": configured}],
        },
    }
