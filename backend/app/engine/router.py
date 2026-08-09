"""Project-scoped streaming chat through the canonical AI gateway."""

import asyncio
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..core.authz import get_current_user
from ..core.authz import require_project_membership
from ..core.errors import public_message
from ..config import settings
from ..gateway import complete_stream

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/engine", tags=["AI Engine"])


class ChatRequest(BaseModel):
    project_id: str = Field(min_length=1, max_length=64)
    messages: list[dict] = Field(min_length=1, max_length=40)
    temperature: float = Field(default=0.7, ge=0.0, le=1.5)
    max_tokens: int = Field(default=2000, ge=256, le=8192)
    client_mutation_id: str | None = Field(default=None, max_length=100)


@router.post("/chat")
async def chat(request: ChatRequest, user=Depends(get_current_user)):
    """Project-scoped chat with quota, ledger, and provider-failure semantics."""
    require_project_membership(request.project_id, user)
    if any(
        not isinstance(message, dict)
        or message.get("role") not in {"system", "user", "assistant"}
        or not isinstance(message.get("content"), str)
        or not message["content"].strip()
        or len(message["content"]) > 12000
        for message in request.messages
    ):
        raise HTTPException(status_code=422, detail="messages contain invalid or oversized entries")

    prompt_text = "\n".join(
        f"{m.get('role','user')}: {m.get('content','')}" for m in request.messages
    )

    async def stream():
        yield f"data: {json.dumps({'type':'start'})}\n\n"
        iterator = complete_stream(
            project_id=request.project_id,
            user_id=user["id"],
            task_type="engine_chat",
            prompt_name="engine.chat",
            variables={
                "prompt": prompt_text,
                "_temperature": request.temperature,
                "_max_tokens": request.max_tokens,
            },
            client_mutation_id=request.client_mutation_id,
        )
        try:
            while True:
                def next_chunk():
                    try:
                        return True, next(iterator)
                    except StopIteration:
                        return False, None

                has_value, delta = await asyncio.to_thread(next_chunk)
                if not has_value:
                    break
                yield f"data: {json.dumps({'type':'delta','content':delta}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type':'done'})}\n\n"
        except Exception:
            logger.exception("engine chat failed")
            yield f"data: {json.dumps({'type':'error','code':'AI_PROVIDER_FAILED','message':'AI 服务暂时不可用，请稍后重试'}, ensure_ascii=False)}\n\n"

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
