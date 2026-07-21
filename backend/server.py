"""
星禾 AI 工作台 · Starlume AI Backend Prototype
FastAPI 后端原型 — 对接前端 Apple 风格 Dashboard

端点清单:
  POST /api/v1/auth/register
  POST /api/v1/auth/login
  GET  /api/v1/stats/overview
  GET  /api/v1/projects
  POST /api/v1/projects
  GET  /api/v1/agents
  GET  /api/v1/skills
  GET  /api/v1/tasks
  GET  /api/v1/modules/health
  GET  /api/v1/hotspots
  GET  /api/v1/healthz
  GET  /api/v1/contents
  POST /api/v1/projects/{id}/novels
  POST /api/v1/novels/{id}/bootstrap

运行方式:
  pip install fastapi uvicorn
  python server.py
"""

import uuid
import hashlib
import secrets
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

# ═══════════════════════════════════════
#  App Init
# ═══════════════════════════════════════

app = FastAPI(title="星禾 AI 工作台 API", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════
#  In-Memory Store (原型用)
# ═══════════════════════════════════════

users: dict = {}       # email -> user_obj
tokens: dict = {}      # token -> email
projects: list = []
contents: list = []

# ═══════════════════════════════════════
#  Models
# ═══════════════════════════════════════

class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str = ""

class LoginRequest(BaseModel):
    email: str
    password: str

class ProjectCreate(BaseModel):
    name: str = "新项目"
    description: str = ""
    genre: str = "创作"

class NovelCreate(BaseModel):
    idea: str = Field(min_length=4, max_length=10000)
    genre: str = "东方玄幻"
    style: str = "克制、悬疑、强画面感"

class BatchChapterRequest(BaseModel):
    chapter_count: int = Field(default=10, ge=1, le=50)

# ═══════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════

def ok(data=None):
    return {"code": 0, "message": "ok", "data": data}

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def new_id(prefix: str = "") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def create_token(email: str) -> str:
    token = secrets.token_urlsafe(32)
    tokens[token] = {"email": email, "created_at": datetime.now(timezone.utc).isoformat()}
    return token

def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": 401, "message": "未登录"})
    token = auth[7:].strip()
    data = tokens.get(token)
    if not data:
        raise HTTPException(status_code=401, detail={"code": 401, "message": "token 无效或已过期"})
    user = users.get(data["email"])
    if not user:
        raise HTTPException(status_code=401, detail={"code": 401, "message": "用户不存在"})
    return user

# ═══════════════════════════════════════
#  Auth Endpoints
# ═══════════════════════════════════════

@app.post("/api/v1/auth/register")
def register(payload: RegisterRequest):
    if payload.email in users:
        raise HTTPException(status_code=409, detail={"code": 409, "message": "邮箱已注册"})
    user = {
        "id": new_id("usr"),
        "email": payload.email,
        "display_name": payload.display_name or payload.email.split("@")[0],
        "password_hash": hash_password(payload.password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    users[payload.email] = user
    token = create_token(payload.email)
    return ok({
        "access_token": token,
        "user": {"id": user["id"], "email": user["email"], "display_name": user["display_name"]},
    })

@app.post("/api/v1/auth/login")
def login(payload: LoginRequest):
    user = users.get(payload.email)
    if not user or user["password_hash"] != hash_password(payload.password):
        raise HTTPException(status_code=401, detail={"code": 401, "message": "邮箱或密码错误"})
    token = create_token(payload.email)
    return ok({
        "access_token": token,
        "user": {"id": user["id"], "email": user["email"], "display_name": user["display_name"]},
    })

# ═══════════════════════════════════════
#  Core Endpoints
# ═══════════════════════════════════════

@app.get("/api/v1/healthz")
def healthz():
    return ok({
        "status": "ok",
        "ai_provider": "deepseek",
        "ai_key_configured": True,
        "database": "ok",
        "redis": "ok",
        "worker": "ok: 1 online",
    })

@app.get("/api/v1/stats/overview")
def stats_overview(user: dict = Depends(get_current_user)):
    return ok({
        "ai_calls": 1247,
        "contents": len(contents) + 12,
        "cost_cny": 3.82,
        "tokens": 2840000,
        "db_size": "42 MB",
    })

@app.get("/api/v1/projects")
def list_projects(user: dict = Depends(get_current_user)):
    user_projects = [p for p in projects if p.get("owner_id") == user["id"]]
    if not user_projects:
        # 原型演示数据
        return ok([
            {"id": "proj_001", "name": "星落长河", "genre": "仙侠", "progress": 67, "chapters": 24,
             "words": 88000, "status": "连载中", "updated_at": "2026-07-20T10:30:00Z", "owner_id": user["id"]},
            {"id": "proj_002", "name": "都市猎魔人", "genre": "都市", "progress": 32, "chapters": 8,
             "words": 21000, "status": "草稿", "updated_at": "2026-07-18T14:00:00Z", "owner_id": user["id"]},
        ])
    return ok(user_projects)

@app.post("/api/v1/projects")
def create_project(payload: ProjectCreate, user: dict = Depends(get_current_user)):
    pid = new_id("proj")
    proj = {
        "id": pid, "name": payload.name, "description": payload.description,
        "genre": payload.genre, "progress": 0, "chapters": 0, "words": 0,
        "status": "草稿", "updated_at": datetime.now(timezone.utc).isoformat(),
        "owner_id": user["id"],
    }
    projects.append(proj)
    return ok(proj)

@app.post("/api/v1/projects/{project_id}/novels")
def create_novel(project_id: str, payload: NovelCreate, user: dict = Depends(get_current_user)):
    nid = new_id("nov")
    novel = {
        "id": nid, "project_id": project_id, "type": "novel",
        "title": "待命名作品", "body": {"type": "doc", "content": []},
        "meta": {"idea": payload.idea, "genre": payload.genre, "style": payload.style},
        "status": "draft", "created_at": datetime.now(timezone.utc).isoformat(),
    }
    contents.append(novel)
    return ok(novel)

@app.get("/api/v1/contents")
def list_contents(project_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    if project_id:
        return ok([c for c in contents if c.get("project_id") == project_id])
    return ok(contents)

@app.get("/api/v1/agents")
def list_agents(user: dict = Depends(get_current_user)):
    return ok([
        {"id": "agent_novel", "name": "小说创作 Agent", "description": "全自动长篇 AI 创作",
         "status": "active", "task_count": 42, "last_run": "5分钟前"},
        {"id": "agent_ranking", "name": "扫榜分析 Agent", "description": "多平台榜单扫描与分析",
         "status": "active", "task_count": 18, "last_run": "1小时前"},
        {"id": "agent_hotspot", "name": "热点追踪 Agent", "description": "实时热点采集与内容生成",
         "status": "idle", "task_count": 7, "last_run": "3小时前"},
    ])

@app.get("/api/v1/skills")
def list_skills(user: dict = Depends(get_current_user)):
    return ok([
        {"id": "skill_polish", "name": "润色优化", "description": "AI 文本润色与改写",
         "status": "active"},
        {"id": "skill_expand", "name": "内容扩写", "description": "基于大纲扩展章节内容",
         "status": "active"},
        {"id": "skill_translate", "name": "出海翻译", "description": "多语种自动翻译",
         "status": "idle"},
    ])

@app.get("/api/v1/tasks")
def list_tasks(user: dict = Depends(get_current_user)):
    return ok([
        {"id": "t1", "name": "生成第 25 章", "assignee": "小说创作 Agent",
         "note": "预计 3 分钟", "status": "running"},
        {"id": "t2", "name": "扫榜分析 · 起点月票榜", "assignee": "扫榜分析 Agent",
         "note": "已完成", "status": "completed"},
    ])

@app.get("/api/v1/modules/health")
def module_health(user: dict = Depends(get_current_user)):
    return ok([
        {"name": "小说创作引擎", "status": "verified", "uptime": "99.9%", "endpoint": "/api/v1/novel"},
        {"name": "AI 网关", "status": "verified", "uptime": "100%", "endpoint": "/api/v1/engine"},
        {"name": "热点分析", "status": "wip", "uptime": "--", "endpoint": "/api/v1/hotspots"},
        {"name": "Agent 中心", "status": "verified", "uptime": "99.7%", "endpoint": "/api/v1/agents"},
        {"name": "Skill 中心", "status": "verified", "uptime": "100%", "endpoint": "/api/v1/skills"},
        {"name": "知识库", "status": "verified", "uptime": "99.5%", "endpoint": "/api/v1/knowledge"},
    ])

@app.get("/api/v1/hotspots")
def get_hotspots(user: dict = Depends(get_current_user)):
    return ok([
        {"id":"h1","title":"AI 创作版权新规草案公布","source":"国务院","heat":98400,"trend":"up","conf":0.92},
        {"id":"h2","title":"2026 年度网络文学白皮书","source":"作协","heat":87200,"trend":"up","conf":0.88},
        {"id":"h3","title":"B 站 UP 主跨界写网文趋势","source":"Bilibili","heat":65400,"trend":"flat","conf":0.85},
        {"id":"h4","title":"新武侠复兴：年轻读者回归","source":"豆瓣阅读","heat":53100,"trend":"up","conf":0.81},
        {"id":"h5","title":"短剧改编网文 TOP10 出炉","source":"优酷","heat":48700,"trend":"flat","conf":0.79},
    ])

@app.get("/api/v1/versions")
def list_versions(user: dict = Depends(get_current_user)):
    return ok([])

@app.get("/api/v1/plugins")
def list_plugins(user: dict = Depends(get_current_user)):
    return ok([])

@app.get("/api/v1/modules")
def list_modules(user: dict = Depends(get_current_user)):
    return ok([])

# ═══════════════════════════════════════
#  Static Files (前端)
# ═══════════════════════════════════════

import os
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

# ═══════════════════════════════════════
#  Main
# ═══════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    print("\n🚀 星禾 AI 工作台 · Starlume AI")
    print("   后端原型服务器启动中...")
    print("   API: http://localhost:8000/api/v1/healthz")
    print("   前端: http://localhost:8000/\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
