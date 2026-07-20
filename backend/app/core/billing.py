"""Subscription + quota enforcement (P0-T2).

Turns the seeded Free/Pro/Enterprise plans into *enforced* limits:

- ``get_active_subscription`` resolves the user's effective plan, degrading
  expired or missing subscriptions to the Free plan.
- ``enforce_quota`` raises ``HTTPException`` with the documented status codes
  when a plan limit is exceeded (project count -> 403, monthly words -> 402,
  disallowed model -> 403).
- ``monthly_window`` returns the current natural-month window (configurable
  later for a rolling 30-day window).
- ``get_subscription_usage`` aggregates the user's current-month usage.

No payment gateway is involved (MVP): plans are switched manually.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app.db import connect, row_to_dict
from app.config import settings

FREE_PLAN_ID = "plan_free"


def monthly_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return ``[start, end)`` of the current natural month.

    ``now`` is injectable for testing. The reset period is the calendar month;
    a rolling 30-day window can replace this later via configuration.
    """
    now = now or datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _free_subscription() -> dict[str, Any]:
    """Fallback plan dict when the user has no active subscription."""
    db = connect()
    try:
        plan = row_to_dict(
            db.execute("SELECT * FROM plans WHERE id = %s", (FREE_PLAN_ID,)).fetchone()
        )
    finally:
        db.close()
    if plan is None:
        # Defensive: seed row missing. Synthesize a minimal, finite Free plan.
        return {
            "plan_id": FREE_PLAN_ID,
            "name": "Free",
            "max_projects": 3,
            "max_words_per_month": 100000,
            "ai_models": ["deepseek"],
            "monthly_budget_cny": float(settings.default_monthly_budget_cny),
            "priority_support": False,
        }
    return {
        "plan_id": plan["id"],
        "name": plan["name"],
        "max_projects": plan["max_projects"],
        "max_words_per_month": plan["max_words_per_month"],
        "ai_models": list(plan["ai_models"] or ["deepseek"]),
        "monthly_budget_cny": float(plan.get("monthly_budget_cny") or settings.default_monthly_budget_cny),
        "priority_support": bool(plan["priority_support"]),
    }


def get_active_subscription(user_id: str) -> dict[str, Any]:
    """Return the effective subscription/plan for ``user_id``.

    Expired or non-active subscriptions degrade to the Free plan so that a
    lapsed Pro/Enterprise user is throttled rather than granted unlimited access.
    """
    db = connect()
    try:
        sub = db.execute(
            """
            SELECT s.id AS subscription_id, s.status AS sub_status, s.expires_at,
                   p.id AS plan_id, p.name, p.max_projects, p.max_words_per_month,
                   p.ai_models, p.priority_support, p.monthly_budget_cny
            FROM subscriptions s
            JOIN plans p ON p.id = s.plan_id
            WHERE s.user_id = %s
            ORDER BY s.created_at DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if sub is None:
            return _free_subscription()
        sub = row_to_dict(sub)
        expires = sub.get("expires_at")
        if expires is not None and expires <= datetime.now(timezone.utc):
            return _free_subscription()
        if sub.get("sub_status") != "active":
            return _free_subscription()
        return {
            "plan_id": sub["plan_id"],
            "name": sub["name"],
            "max_projects": sub["max_projects"],
            "max_words_per_month": sub["max_words_per_month"],
            "ai_models": list(sub["ai_models"] or ["deepseek"]),
            "monthly_budget_cny": float(sub.get("monthly_budget_cny") or settings.default_monthly_budget_cny),
            "priority_support": bool(sub["priority_support"]),
        }
    finally:
        db.close()


def get_subscription_usage(user_id: str) -> dict[str, Any]:
    """Current-month usage for ``user_id``: projects owned, words generated, cost."""
    start, end = monthly_window()
    db = connect()
    try:
        projects = db.execute(
            "SELECT COUNT(*) AS c FROM projects WHERE owner_id = %s", (user_id,)
        ).fetchone()["c"]
        agg = row_to_dict(db.execute(
            """
            SELECT COALESCE(SUM(prompt_tokens), 0)::bigint AS prompt_tokens,
                   COALESCE(SUM(completion_tokens), 0)::bigint AS completion_tokens,
                   COALESCE(SUM(cost_cny), 0)::float AS cost_cny,
                   COUNT(*) AS calls
            FROM ai_calls
            WHERE user_id = %s AND created_at >= %s AND created_at < %s
            """,
            (user_id, start, end),
        ).fetchone())
        return {
            "month": start.strftime("%Y-%m"),
            # Proxy: for Chinese prose, completion tokens ≈ generated words.
            "words_used": int(agg["completion_tokens"] or 0),
            "prompt_tokens": int(agg["prompt_tokens"] or 0),
            "completion_tokens": int(agg["completion_tokens"] or 0),
            "cost_used": float(agg["cost_cny"] or 0),
            "calls": int(agg["calls"] or 0),
            "projects_count": int(projects),
        }
    finally:
        db.close()


def enforce_quota(
    user_id: str,
    project_id: str | None,
    kind: str,
    model: str | None = None,
) -> None:
    """Enforce a plan limit. Raises ``HTTPException`` with documented codes.

    - ``max_projects``       -> 403
    - ``max_words_per_month`` -> 402
    - ``model`` (not in plan) -> 403
    """
    sub = get_active_subscription(user_id)
    if kind == "max_projects":
        usage = get_subscription_usage(user_id)
        limit = int(sub["max_projects"])
        if usage["projects_count"] >= limit:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "PLAN_QUOTA_EXCEEDED",
                    "message": f"项目数已达 {sub['name']} 套餐上限（{limit}）",
                    "limit": limit,
                    "used": usage["projects_count"],
                },
            )
    elif kind == "max_words_per_month":
        usage = get_subscription_usage(user_id)
        limit = int(sub["max_words_per_month"])
        if usage["words_used"] >= limit:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "PLAN_QUOTA_EXCEEDED",
                    "message": f"本月生成字数已达 {sub['name']} 套餐上限（{limit}）",
                    "limit": limit,
                    "used": usage["words_used"],
                },
            )
    elif kind == "model":
        if model:
            allowed = list(sub.get("ai_models") or [])
            if model not in allowed:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": "PLAN_MODEL_NOT_ALLOWED",
                        "message": f"模型 {model} 不在 {sub['name']} 套餐允许范围",
                        "allowed": allowed,
                    },
                )
    # Unknown kind is a no-op (defensive).
