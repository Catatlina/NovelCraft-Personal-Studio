"""Auth endpoints: register, login, refresh, logout."""

import secrets

from fastapi import APIRouter, Body, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token_payload,
    get_current_user,
    hash_password,
    login_is_locked,
    record_login_failure,
    clear_login_failures,
    revoke_refresh_token,
    verify_password,
)
from app.db import connect, new_id
from app.core.rate_limit import limiter
from app.config import settings
from app.core.alerts import alert_login_locked

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=100)


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


def _set_session_cookies(response: Response, refresh: str) -> str:
    csrf = secrets.token_urlsafe(32)
    response.set_cookie(
        "refresh_token", refresh, httponly=True, secure=settings.cookie_secure,
        samesite=settings.cookie_samesite, max_age=settings.refresh_token_days * 86400,
        path="/api/v1/auth",
    )
    response.set_cookie(
        "csrf_token", csrf, httponly=False, secure=settings.cookie_secure,
        samesite=settings.cookie_samesite, max_age=settings.refresh_token_days * 86400,
        path="/",
    )
    return csrf


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie("refresh_token", path="/api/v1/auth")
    response.delete_cookie("csrf_token", path="/")


@router.post("/register")
@limiter.limit("5/minute")
def register(request: Request, response: Response, payload: RegisterRequest = Body(...)):
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
    db.close()

    access = create_access_token(user_id, 0)
    refresh = create_refresh_token(user_id, 0)
    _set_session_cookies(response, refresh)
    return {"code": 0, "message": "ok", "data": {
        "user": {"id": user_id, "email": payload.email, "display_name": payload.display_name},
        "access_token": access,
    }}


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, response: Response, payload: LoginRequest = Body(...)):
    if login_is_locked(payload.email):
        raise HTTPException(status_code=429, detail="account temporarily locked")
    db = connect()
    user = db.execute("SELECT * FROM users WHERE email = %s AND is_deleted = FALSE", (payload.email,)).fetchone()
    db.close()
    if user is None or not verify_password(payload.password, user["password_hash"]):
        failure_count = record_login_failure(payload.email)
        if failure_count >= 5:
            import hashlib
            alert_login_locked(hashlib.sha256(payload.email.lower().encode()).hexdigest()[:12])
        raise HTTPException(status_code=401, detail="invalid email or password")

    clear_login_failures(payload.email)
    token_version = user.get("token_version", 0)
    access = create_access_token(user["id"], token_version)
    refresh = create_refresh_token(user["id"], token_version)
    _set_session_cookies(response, refresh)
    return {"code": 0, "message": "ok", "data": {
        "user": {"id": user["id"], "email": user["email"], "display_name": user["display_name"]},
        "access_token": access,
    }}


@router.post("/refresh")
@limiter.limit("30/minute")
def refresh_token(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = Body(default=None),
    refresh_cookie: str | None = Cookie(default=None, alias="refresh_token"),
):
    token = refresh_cookie or (payload.refresh_token if payload else None)
    if not token:
        raise HTTPException(status_code=401, detail="refresh token required")
    claims = decode_token_payload(token, "refresh")
    if not claims:
        _clear_session_cookies(response)
        raise HTTPException(status_code=401, detail="refresh token is invalid or expired")
    user_id = claims.get("sub")
    db = connect()
    user = db.execute("SELECT * FROM users WHERE id = %s AND is_deleted = FALSE", (user_id,)).fetchone()
    db.close()
    if not user or claims.get("tv", 0) != user.get("token_version", 0):
        _clear_session_cookies(response)
        raise HTTPException(status_code=401, detail="user disabled or token revoked")
    revoke_refresh_token(token)
    version = user.get("token_version", 0)
    access = create_access_token(user_id, version)
    new_refresh = create_refresh_token(user_id, version)
    _set_session_cookies(response, new_refresh)
    return {"code": 0, "message": "ok", "data": {"access_token": access}}


@router.post("/logout")
def logout(
    response: Response,
    payload: RefreshRequest | None = Body(default=None),
    refresh_cookie: str | None = Cookie(default=None, alias="refresh_token"),
):
    token = refresh_cookie or (payload.refresh_token if payload else None)
    if token:
        revoke_refresh_token(token)
    _clear_session_cookies(response)
    return {"code": 0, "message": "ok", "data": {"status": "logged_out"}}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return {"code": 0, "message": "ok", "data": {
        "id": user["id"], "email": user["email"], "display_name": user["display_name"],
    }}
