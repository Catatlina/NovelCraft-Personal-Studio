"""Unified authorization + response envelope helpers (P1-T4).

Single source of truth for project/resource membership checks and the success
envelope. Previously these were duplicated across ``main.py``, ``complete_api.py``,
``ranking.py``, ``deai.py``, ``batch_endpoints.py`` and ``dag_exec.py``.

Public surface
--------------
* ``ok(data, message="ok", code=0)`` — success envelope (``ApiResponse``).
* ``ProjectContext`` + ``ROLE_RANK`` — resolved membership context for the
  FastAPI dependency-injection style.
* Synchronous helpers used by existing endpoints that resolve ids from request
  bodies/forms (where a pure ``Depends`` cannot read the id):
  ``require_member``, ``require_project_member``, ``require_content_member``,
  ``require_novel_member``, ``require_project_membership``.
* ``ensure_project_member(conn, ...)`` — synchronous version that reuses an
  already-open connection; used by ``load_content_for_user`` /
  ``load_run_for_user`` and other adapters.
* ``require_project_member_dep`` / ``require_content_member_dep`` /
  ``require_novel_member_dep`` — FastAPI dependency factories returning
  ``ProjectContext`` (canonical DI style for new endpoints).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request

from app.core.security import get_current_user
from app.db import connect
from app.schemas import ApiResponse


# ── Role hierarchy ──────────────────────────────────────────────────────────
# Higher rank => stronger permission.
ROLE_RANK: dict[str, int] = {
    "viewer": 0,
    "editor": 1,
    "owner": 2,
}

# Logical role aliases accepted by the dependency factories. ``admin`` is
# treated as owner-level (see ``_min_rank_for``).
_ROLE_MIN_RANK: dict[str, int] = {
    "member": 0,  # any member (viewer/editor/owner)
    "editor": 1,
    "owner": 2,
    "admin": 2,   # admin is treated as owner-level
}


def _min_rank_for(role: str) -> int:
    """Return the minimum ``ROLE_RANK`` a member must have for ``role``."""
    if role in _ROLE_MIN_RANK:
        return _ROLE_MIN_RANK[role]
    return ROLE_RANK.get(role, 0)


@dataclass(frozen=True)
class ProjectContext:
    """Resolved project membership context for a request."""

    user: dict
    project_id: str
    role: str


def ok(data: Any = None, message: str = "ok", code: int | str = 0) -> ApiResponse:
    """Build a success envelope consistent with the global error handler."""
    return ApiResponse(code=code, message=message, data=data)


# ── Low-level synchronous checks ─────────────────────────────────────────────

def _member_role(db, project_id: str, user_id: str) -> str | None:
    row = db.execute(
        "SELECT role FROM project_members WHERE project_id = %s AND user_id = %s",
        (project_id, user_id),
    ).fetchone()
    return str(row["role"]) if row else None


def require_member(db, project_id: str, user: dict, write: bool = False) -> None:
    """Raise 403 unless ``user`` is a member (and, for write, editor/owner)."""
    role = _member_role(db, project_id, user["id"])
    if role is None:
        raise HTTPException(status_code=403, detail="not a project member")
    if write and role not in {"owner", "editor"}:
        raise HTTPException(status_code=403, detail="insufficient permissions")


def ensure_project_member(
    conn, project_id: str, user: dict, roles: set[str] | None = None
) -> dict:
    """Synchronous membership check using an already-open ``conn`` (no close).

    Used by ``load_content_for_user`` / ``load_run_for_user`` and other adapters
    that manage their own connection lifecycle.
    """
    role = _member_role(conn, project_id, user["id"])
    if role is None:
        raise HTTPException(status_code=403, detail="not a project member")
    if roles and role not in roles:
        raise HTTPException(status_code=403, detail="insufficient permissions")
    return {"role": role}


def require_project_member(project_id: str, user: dict, write: bool = False) -> None:
    """Synchronous membership check for ``project_id`` (opens its own connection)."""
    if not project_id or not str(project_id).strip():
        raise HTTPException(status_code=422, detail="project_id is required")
    db = connect()
    try:
        require_member(db, project_id, user, write=write)
    finally:
        db.close()


def require_project_membership(
    project_id: str, user: dict, roles: set[str] | None = None
) -> None:
    """Synchronous membership check by role set (opens its own connection)."""
    db = connect()
    try:
        ensure_project_member(db, project_id, user, roles=roles)
    finally:
        db.close()


def require_content_member(content_id: str, user: dict, write: bool = False) -> str:
    """Resolve a content row to its project and enforce membership; return project_id."""
    db = connect()
    try:
        row = db.execute(
            "SELECT project_id FROM contents WHERE id=%s AND is_deleted=FALSE", (content_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="content not found")
        project_id = str(row["project_id"])
        require_member(db, project_id, user, write=write)
        return project_id
    finally:
        db.close()


def require_novel_member(novel_id: str, user: dict, write: bool = False) -> None:
    """Resolve a novel to its project and enforce membership."""
    db = connect()
    try:
        novel = db.execute(
            "SELECT project_id FROM contents WHERE id = %s AND type = 'novel'", (novel_id,)
        ).fetchone()
        if not novel:
            raise HTTPException(status_code=404, detail="novel not found")
        require_member(db, novel["project_id"], user, write=write)
    finally:
        db.close()


# ── FastAPI dependency factories (canonical DI style) ───────────────────────

def _resolve_project_id(request: Request) -> str | None:
    """Best-effort project id resolution from path or query params."""
    pid = request.path_params.get("project_id")
    if not pid:
        pid = request.query_params.get("project_id")
    return pid


def require_project_member_dep(role: str = "member"):
    """Dependency factory: enforce project membership, return ``ProjectContext``.

    Parses ``project_id`` from the request path/query and resolves membership
    from the authenticated user. Non-member -> 403, insufficient role -> 403.
    """
    min_rank = _min_rank_for(role)

    def checker(request: Request, user: dict = Depends(get_current_user)) -> ProjectContext:
        project_id = _resolve_project_id(request)
        if not project_id:
            raise HTTPException(status_code=422, detail="project_id is required")
        db = connect()
        try:
            member_role = _member_role(db, project_id, user["id"])
        finally:
            db.close()
        if member_role is None:
            raise HTTPException(status_code=403, detail="not a project member")
        if ROLE_RANK.get(member_role, 0) < min_rank:
            raise HTTPException(status_code=403, detail="insufficient permissions")
        return ProjectContext(user=user, project_id=project_id, role=member_role)

    return checker


def require_content_member_dep(role: str = "member"):
    """Dependency factory: resolve ``content_id`` to a project, enforce membership."""
    min_rank = _min_rank_for(role)

    def checker(content_id: str, user: dict = Depends(get_current_user)) -> ProjectContext:
        db = connect()
        try:
            row = db.execute(
                "SELECT project_id FROM contents WHERE id=%s AND is_deleted=FALSE", (content_id,)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="content not found")
            project_id = str(row["project_id"])
            member_role = _member_role(db, project_id, user["id"])
        finally:
            db.close()
        if member_role is None:
            raise HTTPException(status_code=403, detail="not a project member")
        if ROLE_RANK.get(member_role, 0) < min_rank:
            raise HTTPException(status_code=403, detail="insufficient permissions")
        return ProjectContext(user=user, project_id=project_id, role=member_role)

    return checker


def require_novel_member_dep(role: str = "member"):
    """Dependency factory: resolve ``novel_id`` to a project, enforce membership."""
    min_rank = _min_rank_for(role)

    def checker(novel_id: str, user: dict = Depends(get_current_user)) -> ProjectContext:
        db = connect()
        try:
            novel = db.execute(
                "SELECT project_id FROM contents WHERE id = %s AND type = 'novel'", (novel_id,)
            ).fetchone()
            if not novel:
                raise HTTPException(status_code=404, detail="novel not found")
            project_id = str(novel["project_id"])
            member_role = _member_role(db, project_id, user["id"])
        finally:
            db.close()
        if member_role is None:
            raise HTTPException(status_code=403, detail="not a project member")
        if ROLE_RANK.get(member_role, 0) < min_rank:
            raise HTTPException(status_code=403, detail="insufficient permissions")
        return ProjectContext(user=user, project_id=project_id, role=member_role)

    return checker
