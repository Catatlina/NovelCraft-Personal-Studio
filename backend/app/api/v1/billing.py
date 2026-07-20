"""Billing endpoints (P0-T2): plans, current subscription/usage, manual upgrade.

No payment gateway is integrated in the MVP — ``upgrade`` only switches the
plan record. Quota enforcement lives in ``app.core.billing``.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from ...core.billing import get_active_subscription, get_subscription_usage
from ...core.security import get_current_user
from ...db import connect, new_id, row_to_dict
from ...schemas import ApiResponse

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


class UpgradeRequest(BaseModel):
    plan_id: str = Field(min_length=1, max_length=64)


def _public_plan_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row.get("description") or "",
        "price_monthly_cny": float(row.get("price_monthly_cny") or 0),
        "price_yearly_cny": float(row.get("price_yearly_cny") or 0),
        "features": row.get("features") or [],
        "max_projects": row["max_projects"],
        "max_words_per_month": row["max_words_per_month"],
        "ai_models": list(row.get("ai_models") or ["deepseek"]),
        "priority_support": bool(row.get("priority_support")),
    }


@router.get("/plans")
def list_plans() -> ApiResponse:
    """Public plan catalog for the pricing/upgrade UI."""
    db = connect()
    try:
        rows = db.execute(
            "SELECT * FROM plans WHERE is_public = TRUE ORDER BY price_monthly_cny ASC"
        ).fetchall()
    finally:
        db.close()
    return ApiResponse(data=[_public_plan_row(dict(r)) for r in rows])


@router.get("/subscription")
def get_subscription(user: dict = Depends(get_current_user)) -> ApiResponse:
    """Current plan + current-month usage for the authenticated user."""
    sub = get_active_subscription(user["id"])
    usage = get_subscription_usage(user["id"])
    return ApiResponse(data={"plan": sub, "usage": usage})


@router.post("/subscription/upgrade")
def upgrade_subscription(
    payload: UpgradeRequest = Body(...),
    user: dict = Depends(get_current_user),
) -> ApiResponse:
    """Switch the user's plan (MVP: no payment). Downgrade/upgrade both allowed."""
    db = connect()
    try:
        plan = row_to_dict(
            db.execute(
                "SELECT * FROM plans WHERE id = %s AND is_public = TRUE", (payload.plan_id,)
            ).fetchone()
        )
        if plan is None:
            raise HTTPException(status_code=404, detail={"code": "PLAN_NOT_FOUND", "message": "套餐不存在"})
        existing = row_to_dict(
            db.execute(
                "SELECT * FROM subscriptions WHERE user_id = %s ORDER BY created_at DESC LIMIT 1",
                (user["id"],),
            ).fetchone()
        )
        if existing:
            db.execute(
                "UPDATE subscriptions SET plan_id = %s, status = 'active', "
                "started_at = now(), expires_at = NULL, auto_renew = TRUE WHERE id = %s",
                (plan["id"], existing["id"]),
            )
            sub_id = existing["id"]
        else:
            sub_id = new_id()
            db.execute(
                "INSERT INTO subscriptions (id, user_id, plan_id, status, started_at, expires_at, auto_renew) "
                "VALUES (%s, %s, %s, 'active', now(), NULL, TRUE)",
                (sub_id, user["id"], plan["id"]),
            )
        db.commit()
        sub = row_to_dict(
            db.execute("SELECT * FROM subscriptions WHERE id = %s", (sub_id,)).fetchone()
        )
    finally:
        db.close()
    return ApiResponse(data=dict(sub))
