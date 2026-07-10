"""JWT + password authentication."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import connect

SECRET_KEY = os.getenv("NOVELCRAFT_JWT_SECRET", "dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TTL = timedelta(minutes=30)
REFRESH_TTL = timedelta(days=7)
import bcrypt as _bcrypt

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(user_id: str, ttl: timedelta, token_type: str = "access") -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": user_id, "type": token_type, "iat": now, "exp": now + ttl},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def create_access_token(user_id: str) -> str:
    return create_token(user_id, ACCESS_TTL, "access")


def create_refresh_token(user_id: str) -> str:
    return create_token(user_id, REFRESH_TTL, "refresh")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token")


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)):
    """FastAPI dependency: extracts user from Bearer token. Skips auth if no token for M1 dev mode."""
    if credentials is None:
        # M1 dev mode: return default user
        return get_default_user()
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token is not an access token")
    user_id = payload.get("sub")
    db = connect()
    user = db.execute("SELECT * FROM users WHERE id = %s AND is_deleted = FALSE", (user_id,)).fetchone()
    db.close()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user


def require_project_role(project_id: str, roles: list[str]):
    """Factory: returns a FastAPI dependency that checks project membership."""
    async def checker(user: dict = Depends(get_current_user)):
        db = connect()
        member = db.execute(
            "SELECT * FROM project_members WHERE project_id = %s AND user_id = %s",
            (project_id, user["id"]),
        ).fetchone()
        db.close()
        if member and member["role"] not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
        return user
    return checker


def get_default_user():
    """M1 dev mode: returns the seed user without requiring auth."""
    db = connect()
    user = db.execute("SELECT * FROM users WHERE is_deleted = FALSE LIMIT 1").fetchone()
    db.close()
    if user is None:
        raise HTTPException(status_code=500, detail="no users in database")
    return user
