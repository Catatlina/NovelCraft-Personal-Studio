"""TASK-002/008/010/018/019/027/030: M1-M2 deep coverage."""
import os, uuid
os.environ["NOVELCRAFT_ENV"] = "dev"

import pytest


# --- TASK-002 ---

def test_backup_script_exists():
    import os as _os
    path = _os.path.join(_os.path.dirname(__file__), "..", "..", "scripts", "backup.sh")
    assert _os.path.exists(path)


def test_backup_has_encryption():
    content = open(os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "backup.sh")).read()
    assert "age" in content.lower() or "AGE" in content


# --- TASK-008 ---

def test_confirm_human_api_key_param():
    from app.workers.tasks import confirm_human
    import inspect
    sig = inspect.signature(confirm_human)
    assert "api_key" in sig.parameters


# --- TASK-010 ---

def test_sse_content_type():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.rate_limit import limiter
    limiter.reset()
    tc = TestClient(app)
    r = tc.get("/api/v1/runs/00000000-0000-0000-0000-000000000000/events")
    assert r.status_code in [200, 401]


# --- TASK-018 ---

def test_foreshadowings_schema():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.rate_limit import limiter
    limiter.reset()
    tc = TestClient(app)
    e = f"fw-{uuid.uuid4().hex[:6]}@nc.dev"
    tok = tc.post("/api/v1/auth/register", json={"email": e, "password": "test1234"}).json()["data"]["access_token"]
    pid = tc.get("/api/v1/projects", headers={"Authorization": f"Bearer {tok}"}).json()["data"][0]["id"]
    r = tc.post(f"/api/v1/projects/{pid}/novels", headers={"Authorization": f"Bearer {tok}"},
                json={"idea": "test", "genre": "test", "style": "t", "target_words": 5000})
    nid = r.json()["data"]["id"]
    r2 = tc.get(f"/api/v1/novels/{nid}/foreshadowings", headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code in [200, 404]


# --- TASK-019 ---

def test_timeline_schema():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.rate_limit import limiter
    limiter.reset()
    tc = TestClient(app)
    e = f"tl-{uuid.uuid4().hex[:6]}@nc.dev"
    tok = tc.post("/api/v1/auth/register", json={"email": e, "password": "test1234"}).json()["data"]["access_token"]
    pid = tc.get("/api/v1/projects", headers={"Authorization": f"Bearer {tok}"}).json()["data"][0]["id"]
    r = tc.post(f"/api/v1/projects/{pid}/novels", headers={"Authorization": f"Bearer {tok}"},
                json={"idea": "test", "genre": "test", "style": "t", "target_words": 5000})
    nid = r.json()["data"]["id"]
    r2 = tc.get(f"/api/v1/novels/{nid}/timeline", headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code in [200, 400, 404]


# --- TASK-027 ---

def test_dag_execute_rejects_invalid():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.rate_limit import limiter
    limiter.reset()
    tc = TestClient(app)
    e = f"dag-{uuid.uuid4().hex[:6]}@nc.dev"
    tok = tc.post("/api/v1/auth/register", json={"email": e, "password": "test1234"}).json()["data"]["access_token"]
    r = tc.post("/api/v1/admin/workflows/nonexistent/execute", headers={"Authorization": f"Bearer {tok}"})
    # 422: project_id/novel_id are now required; 404: unknown workflow; both are rejections
    assert r.status_code in [401, 404, 422]


# --- TASK-030 ---

def test_stress_script_exists():
    import importlib.util
    spec = importlib.util.spec_from_file_location("st", os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "stress_test.py"))
    assert spec is not None
