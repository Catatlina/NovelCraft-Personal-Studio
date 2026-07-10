"""M5: Collaboration — user roles, project sharing, operation log."""
from __future__ import annotations

from app.db import connect, encode, new_id

ROLES = ["owner", "editor", "viewer"]

def invite_user(project_id: str, email: str, role: str = "editor", invited_by: str | None = None) -> dict:
    if role not in ROLES:
        return {"error": f"invalid role: {role}"}
    db = connect()
    user = db.execute("SELECT id FROM users WHERE email = %s", (email,)).fetchone()
    if not user:
        db.close()
        return {"error": f"user not found: {email}"}
    db.execute(
        """INSERT INTO project_members (id, project_id, user_id, role)
           VALUES (%s,%s,%s,%s) ON CONFLICT(project_id, user_id) DO UPDATE SET role=%s""",
        (new_id(), project_id, user["id"], role, role),
    )
    db.execute(
        "INSERT INTO operation_logs (id, project_id, user_id, action, target, detail) VALUES (%s,%s,%s,%s,%s,%s)",
        (new_id(), project_id, invited_by or user["id"], "invite_member", email, encode({"role": role})),
    )
    db.commit()
    db.close()
    return {"status": "invited", "email": email, "role": role}


def list_members(project_id: str) -> list[dict]:
    db = connect()
    rows = db.execute(
        """SELECT u.email, u.display_name, pm.role, pm.created_at
           FROM project_members pm JOIN users u ON pm.user_id = u.id
           WHERE pm.project_id = %s ORDER BY pm.created_at""",
        (project_id,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def log_operation(project_id: str, user_id: str, action: str, target: str, detail: dict | None = None):
    db = connect()
    db.execute(
        "INSERT INTO operation_logs (id, project_id, user_id, action, target, detail) VALUES (%s,%s,%s,%s,%s,%s)",
        (new_id(), project_id, user_id, action, target, encode(detail or {})),
    )
    db.commit()
    db.close()


def get_operation_logs(project_id: str, limit: int = 50) -> list[dict]:
    db = connect()
    rows = db.execute(
        """SELECT u.email, ol.action, ol.target, ol.detail, ol.created_at
           FROM operation_logs ol LEFT JOIN users u ON ol.user_id = u.id
           WHERE ol.project_id = %s ORDER BY ol.created_at DESC LIMIT %s""",
        (project_id, limit),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]
