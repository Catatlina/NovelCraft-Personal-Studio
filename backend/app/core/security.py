"""Security utilities — JWT + password hashing + authorization."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.db import connect

bearer_scheme = HTTPBearer(auto_error=False)
JWT_ALGORITHM = "HS256"
JWT_SECRET = os.getenv("NOVELCRAFT_JWT_SECRET", "dev-secret-change-in-production")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_token(user_id: str, token_type: str = "access", expires_delta: timedelta | None = None) -> str:
    if expires_delta is None:
        expires_delta = timedelta(hours=1) if token_type == "access" else timedelta(days=7)
    payload = {
        "sub": user_id,
        "type": token_type,
        "exp": datetime.now(timezone.utc) + expires_delta,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")


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
