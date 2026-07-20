"""P1-T4 跨租户鉴权矩阵测试 (T01)。

数据驱动地校验 ``app.core.authz`` 的统一鉴权（T01 引入的收敛点）：枚举若干
端点的 ``method / path / 角色`` 组合，断言匿名 -> 401、非成员 -> 403、成员/属主
-> 200，并额外覆盖"编辑器试图访问 owner-only 端点 -> 403"的角色层级。

本测试**依赖可用 PostgreSQL 测试库**（含 users / projects / project_members
表），因为它要构造真实的跨租户成员关系来验证鉴权矩阵。它使用 T01 引入的
**规范 DI 依赖工厂** ``require_project_member_dep(role=...)`` 与真实的
``get_current_user``（401 路径），挂载到最小 FastAPI 应用上，再用真实 JWT
令牌驱动 ``TestClient``。

⚠️ 仅在指向测试库时运行；执行前后会写入并清理 3 个占位用户 + 1 个项目 +
成员关系，不会对生产库执行。若本地无可用数据库，整个模块会被跳过（不伪造通过）。

运行：``pytest backend/tests/test_authz_matrix.py``
"""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.authz import ProjectContext, require_project_member_dep
from app.core.security import create_access_token, get_current_user
from app.db import connect, new_id


# ── 可用性探针：无可用 DB 则整模块跳过（绝不伪造通过）──────────────────────
def _db_available() -> bool:
    try:
        c = connect()
        c.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_available(),
    reason=(
        "需部署后在含 DB 环境运行：本测试依赖可用 PostgreSQL（users / projects / "
        "project_members 表）以构造跨租户成员关系，校验统一鉴权矩阵。本地无可用数据库时跳过。"
    ),
)


_TAG = f"qa_authz_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def seeded():
    """写入 owner / member(editor) / outsider 三个用户与一个项目，并返回令牌。

    注意：连接不在测试之间长期持有——设置阶段写入并提交后立即关闭，拆除阶段
    再重新连库清理。这样可避免 conftest 的 autouse ``_reset_db_pool`` 在每个测试
    前后关闭连接池导致本 fixture 持有的连接失效。
    """
    conn = connect()
    try:
        owner_id = new_id("u")
        member_id = new_id("u")
        outsider_id = new_id("u")
        project_id = new_id("p")

        users = [
            (owner_id, f"{_TAG}_owner@test.local"),
            (member_id, f"{_TAG}_member@test.local"),
            (outsider_id, f"{_TAG}_outsider@test.local"),
        ]
        for uid, email in users:
            conn.execute(
                """INSERT INTO users (id, email, password_hash, display_name, token_version, is_deleted)
                   VALUES (%s, %s, 'x', %s, 0, false)
                   ON CONFLICT (id) DO NOTHING""",
                (uid, email, email.split("@")[0]),
            )
        conn.execute(
            """INSERT INTO projects (id, name, description, owner_id, is_deleted)
               VALUES (%s, %s, '', %s, false)
               ON CONFLICT (id) DO NOTHING""",
            (project_id, f"{_TAG}-proj", owner_id),
        )
        conn.execute(
            """INSERT INTO project_members (id, project_id, user_id, role)
               VALUES (%s, %s, %s, 'owner') ON CONFLICT DO NOTHING""",
            (new_id("pm"), project_id, owner_id),
        )
        conn.execute(
            """INSERT INTO project_members (id, project_id, user_id, role)
               VALUES (%s, %s, %s, 'editor') ON CONFLICT DO NOTHING""",
            (new_id("pm"), project_id, member_id),
        )
        conn.commit()
    finally:
        conn.close()

    tokens = {
        "owner": create_access_token(owner_id),
        "member": create_access_token(member_id),
        "outsider": create_access_token(outsider_id),
    }
    data = {"project_id": project_id, "tokens": tokens}
    yield data

    # 清理：仅删除本测试写入的占位数据
    conn = connect()
    try:
        conn.execute("DELETE FROM project_members WHERE project_id = %s", (project_id,))
        conn.execute("DELETE FROM projects WHERE id = %s", (project_id,))
        for uid in (owner_id, member_id, outsider_id):
            conn.execute("DELETE FROM users WHERE id = %s", (uid,))
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def _build_app():
    """最小应用：使用 T01 规范依赖工厂挂载代表性端点。"""
    app = FastAPI()

    @app.get("/api/v1/projects/{project_id}/contents")
    def member_path_route(ctx: ProjectContext = Depends(require_project_member_dep(role="member"))):
        return {"ok": True, "role": ctx.role, "project_id": ctx.project_id}

    @app.get("/api/v1/contents")
    def member_query_route(ctx: ProjectContext = Depends(require_project_member_dep(role="member"))):
        return {"ok": True, "role": ctx.role, "project_id": ctx.project_id}

    @app.post("/api/v1/projects/{project_id}/novels")
    def owner_path_route(ctx: ProjectContext = Depends(require_project_member_dep(role="owner"))):
        return {"ok": True, "role": ctx.role, "project_id": ctx.project_id}

    return app


@pytest.fixture(scope="module")
def client():
    with TestClient(_build_app()) as c:
        yield c


def _auth_headers(token: str | None) -> dict:
    return {"Authorization": f"Bearer {token}"} if token else {}


# 端点定义：(method, path_template, 所需最低角色)
ENDPOINTS = [
    ("GET", "/api/v1/projects/{project_id}/contents", "member"),
    ("GET", "/api/v1/contents?project_id={project_id}", "member"),
    ("POST", "/api/v1/projects/{project_id}/novels", "owner"),
]

# 角色 -> 在 seeded 中的令牌键（None 表示匿名）
ACTORS = ["anonymous", "outsider", "member", "owner"]


def _expected_status(required_role: str, actor: str) -> int:
    """根据所需角色与请求者角色计算期望状态码。"""
    if actor == "anonymous":
        return 401
    ranks = {"viewer": 0, "editor": 1, "owner": 2}
    actor_rank = {"outsider": -1, "member": ranks["editor"], "owner": ranks["owner"]}[actor]
    min_rank = {"member": 0, "owner": 2}[required_role]
    if actor_rank < 0:
        return 403  # 非成员
    if actor_rank < min_rank:
        return 403  # 角色不足（编辑器访问 owner-only）
    return 200


@pytest.mark.parametrize("method,path_template,required_role", ENDPOINTS)
@pytest.mark.parametrize("actor", ACTORS)
def test_authz_matrix(client, seeded, method, path_template, required_role, actor):
    project_id = seeded["project_id"]
    url = path_template.format(project_id=project_id)
    token = None if actor == "anonymous" else seeded["tokens"].get(actor)
    headers = _auth_headers(token)

    if method == "GET":
        resp = client.get(url, headers=headers)
    else:
        resp = client.post(url, headers=headers, json={})

    expected = _expected_status(required_role, actor)
    assert resp.status_code == expected, (
        f"{method} {path_template} as {actor}: "
        f"expected {expected}, got {resp.status_code} body={resp.text[:200]}"
    )


def test_authz_matrix_contract_counts(client, seeded):
    """冒烟：确保矩阵覆盖了 401 / 403 / 200 三种结果，避免断言恒真。"""
    seen = set()
    for method, path_template, required_role in ENDPOINTS:
        for actor in ACTORS:
            project_id = seeded["project_id"]
            url = path_template.format(project_id=project_id)
            token = None if actor == "anonymous" else seeded["tokens"].get(actor)
            headers = _auth_headers(token)
            resp = client.get(url, headers=headers) if method == "GET" else client.post(
                url, headers=headers, json={}
            )
            seen.add(resp.status_code)
    assert seen == {401, 403, 200}, f"矩阵未覆盖全部状态码，实际覆盖: {seen}"
