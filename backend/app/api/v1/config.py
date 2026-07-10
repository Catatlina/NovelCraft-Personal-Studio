"""AI Configuration API — manage providers, models, API keys, budgets."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.db import connect, encode, decode, new_id
from app.core.security import get_current_user

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    allowed = {email.strip().lower() for email in os.getenv("NOVELCRAFT_ADMIN_EMAILS", "").split(",") if email.strip()}
    if allowed and user["email"].lower() in allowed:
        return user
    if not allowed and os.getenv("NOVELCRAFT_ENV", "").startswith("dev"):
        return user
    raise HTTPException(status_code=403, detail="admin access required")


def ensure_project_member(project_id: str, user: dict, roles: set[str] | None = None) -> None:
    db = connect()
    member = db.execute(
        "SELECT role FROM project_members WHERE project_id = %s AND user_id = %s",
        (project_id, user["id"]),
    ).fetchone()
    db.close()
    if not member:
        raise HTTPException(status_code=403, detail="not a project member")
    if roles and member["role"] not in roles:
        raise HTTPException(status_code=403, detail="insufficient permissions")


class ProviderSettings(BaseModel):
    provider: str = Field(pattern="^(deepseek|claude|openai|gemini|mock)$")
    api_key: str = ""
    base_url: str = ""
    default_model: str = ""


class ModelRouteUpdate(BaseModel):
    provider: str
    model: str
    params: dict = {}
    fallbacks: list[dict] = []


@router.get("/providers")
def list_providers(user: dict = Depends(get_current_user)):
    """List all configured AI providers with masked keys."""
    providers = [
        {"name": "deepseek", "key_configured": bool(os.getenv("DEEPSEEK_API_KEY","")),
         "base_url": "https://api.deepseek.com", "default_model": "deepseek-chat"},
        {"name": "claude", "key_configured": bool(os.getenv("CLAUDE_API_KEY","")),
         "base_url": "https://api.anthropic.com", "default_model": "claude-sonnet-4-20250514"},
        {"name": "openai", "key_configured": bool(os.getenv("OPENAI_API_KEY","")),
         "base_url": "https://api.openai.com", "default_model": "gpt-4o"},
        {"name": "gemini", "key_configured": bool(os.getenv("GEMINI_API_KEY","")),
         "base_url": "https://generativelanguage.googleapis.com", "default_model": "gemini-2.0-flash"},
    ]
    return {"code": 0, "message": "ok", "data": providers}


@router.get("/model-routes")
def list_routes(user: dict = Depends(get_current_user)):
    db = connect()
    rows = db.execute("SELECT * FROM model_routes ORDER BY task_type").fetchall()
    db.close()
    items = []
    for r in rows:
        d = dict(r)
        d["params"] = decode(d.get("params"), {})
        d["fallback_json"] = decode(d.get("fallback_json"), [])
        items.append(d)
    return {"code": 0, "message": "ok", "data": items}


@router.put("/model-routes/{task_type}")
def update_route(task_type: str, payload: ModelRouteUpdate, user: dict = Depends(require_admin)):
    db = connect()
    db.execute(
        """INSERT INTO model_routes (id, task_type, provider, model, params, fallback_json)
           VALUES (%s, %s, %s, %s, %s, %s)
           ON CONFLICT(task_type) DO UPDATE SET
           provider=EXCLUDED.provider, model=EXCLUDED.model,
           params=EXCLUDED.params, fallback_json=EXCLUDED.fallback_json, updated_at=now()""",
        (new_id(), task_type, payload.provider, payload.model,
         encode(payload.params), encode(payload.fallbacks)),
    )
    db.commit()
    row = db.execute("SELECT * FROM model_routes WHERE task_type = %s", (task_type,)).fetchone()
    db.close()
    d = dict(row)
    d["params"] = decode(d.get("params"), {})
    return {"code": 0, "message": "ok", "data": d}


@router.get("/budgets")
def list_budgets(project_id: str = "", user: dict = Depends(get_current_user)):
    db = connect()
    if project_id:
        db.close()
        ensure_project_member(project_id, user)
        db = connect()
        rows = db.execute("SELECT * FROM budgets WHERE project_id = %s ORDER BY scope", (project_id,)).fetchall()
    else:
        rows = db.execute(
            """
            SELECT b.* FROM budgets b
            JOIN project_members pm ON b.project_id = pm.project_id
            WHERE pm.user_id = %s
            ORDER BY b.project_id, b.scope
            """,
            (user["id"],),
        ).fetchall()
    db.close()
    return {"code": 0, "message": "ok", "data": [dict(r) for r in rows]}


@router.put("/budgets/{project_id}/{scope}")
def update_budget(
    project_id: str,
    scope: str,
    limit_cny: float = 2.0,
    user: dict = Depends(get_current_user),
):
    ensure_project_member(project_id, user, {"owner"})
    db = connect()
    db.execute(
        """INSERT INTO budgets (id, project_id, scope, limit_cny, spent_cny)
           VALUES (%s, %s, %s, %s, 0)
           ON CONFLICT(project_id, scope) DO UPDATE SET limit_cny=EXCLUDED.limit_cny, updated_at=now()""",
        (new_id(), project_id, scope, limit_cny),
    )
    db.commit()
    row = db.execute("SELECT * FROM budgets WHERE project_id = %s AND scope = %s", (project_id, scope)).fetchone()
    db.close()
    return {"code": 0, "message": "ok", "data": dict(row)}


@router.get("/prompts")
def list_prompts(user: dict = Depends(get_current_user)):
    db = connect()
    rows = db.execute("SELECT * FROM prompts ORDER BY name, version DESC").fetchall()
    db.close()
    items = []
    for r in rows:
        d = dict(r)
        d["golden_cases"] = decode(d.get("golden_cases"), [])
        items.append(d)
    return {"code": 0, "message": "ok", "data": items}


@router.get("/settings")
def list_settings(user: dict = Depends(require_admin)):
    """Read all settings (keys masked)."""
    db = connect()
    rows = db.execute("SELECT key, value, description, updated_at FROM settings ORDER BY key").fetchall()
    db.close()
    items = []
    for r in rows:
        d = dict(r)
        if "api_key" in d["key"] and d["value"]:
            d["value"] = d["value"][:8] + "..." + d["value"][-4:] if len(d["value"]) > 12 else "***"
        items.append(d)
    return {"code": 0, "message": "ok", "data": items}


@router.put("/settings/{key}")
def update_setting(key: str, value: str, user: dict = Depends(require_admin)) -> dict:
    """Update a single setting."""
    db = connect()
    db.execute(
        "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT(key) DO UPDATE SET value=%s, updated_at=now()",
        (key, value, value),
    )
    db.commit()
    row = db.execute("SELECT * FROM settings WHERE key = %s", (key,)).fetchone()
    db.close()
    d = dict(row)
    if "api_key" in d["key"] and d["value"]:
        d["value"] = d["value"][:8] + "..." + d["value"][-4:]
    return {"code": 0, "message": "ok", "data": d}


@router.get("/env-check")
def env_check(user: dict = Depends(require_admin)):
    """Check which env vars are configured vs DB settings."""
    import os
    db = connect()
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    db.close()
    db_settings = {r["key"]: r["value"] for r in rows}
    checks = []
    for provider in ["deepseek", "claude", "openai", "gemini"]:
        env_key = os.getenv(f"{provider.upper()}_API_KEY", "")
        db_val = db_settings.get(f"{provider}_api_key", "")
        checks.append({
            "provider": provider,
            "env_configured": bool(env_key),
            "db_configured": bool(db_val),
            "effective_source": "env" if env_key else ("db" if db_val else "none"),
        })
    return {"code": 0, "message": "ok", "data": checks}


@router.get("/workflows")
def list_workflows(project_id: str = "", user: dict = Depends(get_current_user)):
    db = connect()
    if project_id:
        db.close()
        ensure_project_member(project_id, user)
        db = connect()
        rows = db.execute("SELECT * FROM workflows WHERE project_id = %s ORDER BY created_at DESC", (project_id,)).fetchall()
    else:
        rows = db.execute(
            """
            SELECT w.* FROM workflows w
            JOIN project_members pm ON w.project_id = pm.project_id
            WHERE pm.user_id = %s
            ORDER BY w.created_at DESC LIMIT 20
            """,
            (user["id"],),
        ).fetchall()
    db.close()
    return {"code": 0, "message": "ok", "data": [dict(r) for r in rows]}


@router.put("/workflows/{name}")
def save_workflow(
    name: str,
    nodes: list[dict],
    project_id: str = "",
    user: dict = Depends(get_current_user),
):
    if project_id:
        ensure_project_member(project_id, user, {"owner", "editor"})
    else:
        require_admin(user)
    db = connect()
    db.execute(
        """INSERT INTO workflows (id, project_id, name, config)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT(project_id, name) DO UPDATE SET config=EXCLUDED.config, updated_at=now()""",
        (new_id(), project_id or None, name, encode({"nodes": nodes})),
    )
    db.commit()
    row = db.execute("SELECT * FROM workflows WHERE name = %s", (name,)).fetchone()
    db.close()
    return {"code": 0, "message": "ok", "data": dict(row or {})}
