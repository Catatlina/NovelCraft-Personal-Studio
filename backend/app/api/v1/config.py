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
    if not allowed:
        raise HTTPException(status_code=403, detail="NOVELCRAFT_ADMIN_EMAILS must be set in production")
    raise HTTPException(status_code=403, detail="admin access required")


def require_admin_reads(user: dict = Depends(get_current_user)) -> dict:
    """QA-003: admin-namespace read guard.

    When NOVELCRAFT_ADMIN_EMAILS is configured, reads are restricted to those
    admins like the write endpoints. A single-user personal instance without
    the variable keeps authenticated read access (the data is non-secret
    prompt/route configuration), so upgrading does not lock the owner out.
    """
    allowed = {email.strip().lower() for email in os.getenv("NOVELCRAFT_ADMIN_EMAILS", "").split(",") if email.strip()}
    if allowed and user["email"].lower() not in allowed:
        raise HTTPException(status_code=403, detail="admin access required")
    return user


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
    provider: str = Field(pattern="^(deepseek|claude|openai|gemini)$")
    api_key: str = ""
    base_url: str = ""
    default_model: str = ""


class ModelRouteUpdate(BaseModel):
    provider: str = Field(pattern="^(deepseek|claude|openai|gemini)$")
    model: str
    params: dict = {}
    fallbacks: list[dict] = Field(default_factory=list, max_length=0)


class WorkflowSaveRequest(BaseModel):
    project_id: str
    nodes: list[dict] = Field(min_length=1, max_length=100)


class BudgetLimitRequest(BaseModel):
    limit_cny: float = Field(ge=0.000001, le=10000)


class SettingUpdateRequest(BaseModel):
    value: str = Field(max_length=4000)


@router.get("/providers")
def list_providers(user: dict = Depends(require_admin_reads)):
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
def list_routes(user: dict = Depends(require_admin_reads)):
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
    payload: BudgetLimitRequest,
    user: dict = Depends(get_current_user),
):
    ensure_project_member(project_id, user, {"owner"})
    db = connect()
    db.execute(
        """INSERT INTO budgets (id, project_id, scope, limit_cny, spent_cny)
           VALUES (%s, %s, %s, %s, 0)
           ON CONFLICT(project_id, scope) DO UPDATE SET limit_cny=EXCLUDED.limit_cny, updated_at=now()""",
        (new_id(), project_id, scope, payload.limit_cny),
    )
    db.commit()
    row = db.execute("SELECT * FROM budgets WHERE project_id = %s AND scope = %s", (project_id, scope)).fetchone()
    db.close()
    return {"code": 0, "message": "ok", "data": dict(row)}


@router.get("/prompts")
def list_prompts(user: dict = Depends(require_admin_reads)):
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
def list_settings(user: dict = Depends(require_admin_reads)):
    """Read all settings (keys masked). QA-003: reads use the read guard so a
    single-user instance without NOVELCRAFT_ADMIN_EMAILS is not locked out."""
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
def update_setting(key: str, payload: SettingUpdateRequest, user: dict = Depends(require_admin)) -> dict:
    """Update non-runtime metadata. Provider runtime configuration is env/BYOK only."""
    runtime_keys = {f"{provider}_{suffix}" for provider in ("deepseek", "claude", "openai", "gemini")
                    for suffix in ("api_key", "base_url", "model")}
    runtime_keys |= {"request_timeout_seconds", "bootstrap_budget_cny"}
    if key.lower() in runtime_keys:
        raise HTTPException(409, "运行时 AI 配置请使用环境变量（服务重启生效）或浏览器 BYOK 会话配置")
    db = connect()
    db.execute(
        "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT(key) DO UPDATE SET value=%s, updated_at=now()",
        (key, payload.value, payload.value),
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
        checks.append({
            "provider": provider,
            "env_configured": bool(env_key),
            "db_configured": bool(db_settings.get(f"{provider}_api_key", "")),
            "effective_source": "env" if env_key else "none",
            "note": "DB 中的旧值不参与运行时调用，请迁移到环境变量后删除",
        })
    return {"code": 0, "message": "ok", "data": checks}


@router.get("/workflows")
def list_workflows(project_id: str = "", user: dict = Depends(get_current_user)):
    db = connect()
    if project_id:
        db.close()
        ensure_project_member(project_id, user)
        db = connect()
        rows = db.execute(
            """SELECT * FROM workflows
               WHERE (project_id = %s OR (project_id IS NULL AND is_preset = TRUE))
                 AND is_deleted = FALSE
               ORDER BY project_id NULLS LAST, updated_at DESC""",
            (project_id,),
        ).fetchall()
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
    payload: WorkflowSaveRequest,
    user: dict = Depends(get_current_user),
):
    project_id = payload.project_id
    ensure_project_member(project_id, user, {"owner", "editor"})
    if name == "bootstrap":
        raise HTTPException(
            status_code=409,
            detail={"code": "SYSTEM_WORKFLOW_READ_ONLY",
                    "message": "bootstrap is a system workflow; save a named draft instead"},
        )
    db = connect()
    db.execute(
        """INSERT INTO workflows (id, project_id, name, definition)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT(project_id, name) WHERE project_id IS NOT NULL AND is_deleted=FALSE
           DO UPDATE SET definition=EXCLUDED.definition, updated_at=now()""",
        (new_id(), project_id, name, encode({"nodes": payload.nodes})),
    )
    db.commit()
    row = db.execute(
        "SELECT * FROM workflows WHERE project_id=%s AND name=%s AND is_deleted=FALSE",
        (project_id, name),
    ).fetchone()
    db.close()
    return {"code": 0, "message": "ok", "data": dict(row or {})}
