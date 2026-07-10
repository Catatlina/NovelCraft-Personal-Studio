"""Security utilities — JWT + password hashing + authorization."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.db import connect
from app.config import settings

bearer_scheme = HTTPBearer(auto_error=False)
JWT_ALGORITHM = "HS256"
JWT_SECRET = settings.jwt_secret or "dev-secret-change-in-production"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_token(
    user_id: str,
    token_type: str = "access",
    expires_delta: timedelta | None = None,
    token_version: int = 0,
) -> str:
    if expires_delta is None:
        expires_delta = (
            timedelta(minutes=settings.access_token_minutes)
            if token_type == "access"
            else timedelta(days=settings.refresh_token_days)
        )
    payload = {
        "sub": user_id,
        "type": token_type,
        "exp": datetime.now(timezone.utc) + expires_delta,
        "iat": datetime.now(timezone.utc),
        "jti": uuid.uuid4().hex,
        "tv": token_version,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# Backward-compatible aliases
def create_access_token(user_id: str, token_version: int = 0) -> str:
    return create_token(user_id, "access", token_version=token_version)

def create_refresh_token(user_id: str, token_version: int = 0) -> str:
    token = create_token(user_id, "refresh", token_version=token_version)
    payload = decode_token(token)
    _store_refresh_jti(user_id, payload["jti"])
    return token


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")


def decode_token_payload(token: str, expected_type: str | None = None) -> dict | None:
    """Decode a token and reject wrong types or revoked refresh JTIs."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if expected_type and payload.get("type") != expected_type:
            return None
        if expected_type == "refresh" and not _refresh_jti_is_active(payload.get("sub"), payload.get("jti")):
            return None
        return payload
    except JWTError:
        return None


def revoke_refresh_token(token: str) -> None:
    """Revoke a refresh token without raising for already-invalid tokens."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return
    if payload.get("type") == "refresh":
        _revoke_refresh_jti(payload.get("sub"), payload.get("jti"))


def _redis_client():
    import redis
    return redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), socket_timeout=2)


def _store_refresh_jti(user_id: str, jti: str) -> None:
    try:
        _redis_client().setex(
            f"refresh:{user_id}:{jti}",
            settings.refresh_token_days * 86400,
            "1",
        )
    except Exception:
        if settings.token_blacklist_fail_closed:
            raise HTTPException(status_code=503, detail="token revocation service unavailable")


def _refresh_jti_is_active(user_id: str | None, jti: str | None) -> bool:
    if not user_id or not jti:
        return False
    try:
        client = _redis_client()
        return bool(client.exists(f"refresh:{user_id}:{jti}")) and not bool(client.exists(f"black:{user_id}:{jti}"))
    except Exception:
        return not settings.token_blacklist_fail_closed


def _revoke_refresh_jti(user_id: str | None, jti: str | None) -> None:
    if not user_id or not jti:
        return
    try:
        client = _redis_client()
        client.delete(f"refresh:{user_id}:{jti}")
        client.setex(f"black:{user_id}:{jti}", settings.refresh_token_days * 86400, "1")
    except Exception:
        if settings.token_blacklist_fail_closed:
            raise HTTPException(status_code=503, detail="token revocation service unavailable")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """FastAPI dependency: requires valid Bearer token. No dev-mode bypass."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token is not an access token")
    user_id = payload.get("sub")
    db = connect()
    user = db.execute("SELECT * FROM users WHERE id = %s AND is_deleted = FALSE", (user_id,)).fetchone()
    db.close()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    if payload.get("tv", 0) != user.get("token_version", 0):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token has been revoked")
    return dict(user)


def require_project_role(project_id: str, roles: list[str] | None = None):
    """Factory: FastAPI dependency that checks project membership + optional role.
    
    Blocks non-members (None → 403, not bypass).
    """
    async def checker(user: dict = Depends(get_current_user)):
        db = connect()
        member = db.execute(
            "SELECT * FROM project_members WHERE project_id = %s AND user_id = %s",
            (project_id, user["id"]),
        ).fetchone()
        db.close()
        if member is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not a project member")
        if roles and member["role"] not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
        return user
    return checker
