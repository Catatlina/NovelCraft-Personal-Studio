"""Auth endpoints: register, login, refresh, logout."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.db import connect, new_id

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)
    display_name: str = Field(default="", max_length=100)


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/register")
def register(payload: RegisterRequest, response: Response):
    db = connect()
    existing = db.execute("SELECT id FROM users WHERE email = %s", (payload.email,)).fetchone()
    if existing:
        db.close()
        raise HTTPException(status_code=409, detail="email already registered")

    user_id = new_id()
    password_hash = hash_password(payload.password)
    db.execute(
        "INSERT INTO users (id, email, password_hash, display_name) VALUES (%s, %s, %s, %s)",
        (user_id, payload.email, password_hash, payload.display_name),
    )
    # Auto-create a project for new users
    project_id = new_id()
    db.execute(
        "INSERT INTO projects (id, name, description, owner_id) VALUES (%s, %s, %s, %s)",
        (project_id, f"{payload.display_name or payload.email} 的工作室", "默认创作项目", user_id),
    )
    db.execute(
        "INSERT INTO project_members (id, project_id, user_id, role) VALUES (%s, %s, %s, %s)",
        (new_id(), project_id, user_id, "owner"),
    )
    db.execute(
        "INSERT INTO budgets (id, project_id, scope, limit_cny, spent_cny) VALUES (%s, %s, %s, %s, %s)",
        (new_id(), project_id, "bootstrap", 2.0, 0),
    )
    db.commit()

    access = create_access_token(user_id)
    refresh = create_refresh_token(user_id)
    return {"code": 0, "message": "ok", "data": {
        "user": {"id": user_id, "email": payload.email, "display_name": payload.display_name},
        "access_token": access,
        "refresh_token": refresh,
    }}


@router.post("/login")
def login(payload: LoginRequest, response: Response):
    db = connect()
    user = db.execute("SELECT * FROM users WHERE email = %s AND is_deleted = FALSE", (payload.email,)).fetchone()
    db.close()
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="invalid email or password")

    access = create_access_token(user["id"])
    refresh = create_refresh_token(user["id"])
    return {"code": 0, "message": "ok", "data": {
        "user": {"id": user["id"], "email": user["email"], "display_name": user["display_name"]},
        "access_token": access,
        "refresh_token": refresh,
    }}


@router.post("/refresh")
def refresh_token(payload: RefreshRequest):
    claims = decode_token(payload.refresh_token)
    if claims.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="token is not a refresh token")
    user_id = claims["sub"]
    access = create_access_token(user_id)
    return {"code": 0, "message": "ok", "data": {"access_token": access}}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return {"code": 0, "message": "ok", "data": {
        "id": user["id"], "email": user["email"], "display_name": user["display_name"],
    }}
