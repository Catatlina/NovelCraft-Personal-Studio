from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.workflow import EVENT_LOGS, RUN_TASKS


def setup_client(tmp_path):
    db.DB_PATH = tmp_path / "test.sqlite3"
    EVENT_LOGS.clear()
    RUN_TASKS.clear()
    db.init_db()
    return TestClient(app)


def create_novel(client: TestClient) -> tuple[str, str]:
    project = client.get("/api/v1/projects").json()["data"][0]
    response = client.post(
        f"/api/v1/projects/{project['id']}/novels",
        json={
            "idea": "一个写作者发现被删除的章节正在现实里发生。",
            "genre": "都市奇幻",
            "style": "克制悬疑",
            "target_words": 800000,
        },
    )
    assert response.status_code == 200
    return project["id"], response.json()["data"]["id"]


def wait_for_status(client: TestClient, run_id: str, status: str, timeout: float = 8.0):
    deadline = time.time() + timeout
    last_payload = None
    while time.time() < deadline:
        last_payload = client.get(f"/api/v1/runs/{run_id}").json()["data"]
        if last_payload["status"] == status:
            return last_payload
        time.sleep(0.15)
    raise AssertionError(f"run did not reach {status}: {last_payload}")


def test_bootstrap_generates_first_chapter_and_ai_trace(tmp_path):
    client = setup_client(tmp_path)
    project_id, novel_id = create_novel(client)

    run_id = client.post(f"/api/v1/novels/{novel_id}/bootstrap", json={}).json()["data"]["run_id"]
    waiting = wait_for_status(client, run_id, "waiting_human")
    selected_title = waiting["context"]["title_candidates"][0]

    confirm = client.post(f"/api/v1/runs/{run_id}/nodes/n2/confirm", json={"selected_title": selected_title})
    assert confirm.status_code == 200
    done = wait_for_status(client, run_id, "succeeded")

    assert [node["status"] for node in done["nodes"]] == ["succeeded"] * 8
    chapters = client.get(f"/api/v1/contents?project_id={project_id}&parent_id={novel_id}").json()["data"]
    assert len(chapters) == 1
    calls = client.get(f"/api/v1/ai-calls?run_id={run_id}").json()["data"]
    assert len(calls) == 7
    assert calls[0]["provider"] == "local-mock"


def test_bootstrap_stops_when_budget_is_exceeded(tmp_path):
    client = setup_client(tmp_path)
    project_id, novel_id = create_novel(client)
    client.put(f"/api/v1/admin/budgets/{project_id}/bootstrap", json={"limit_cny": 0.0001})

    run_id = client.post(f"/api/v1/novels/{novel_id}/bootstrap", json={}).json()["data"]["run_id"]
    pending = wait_for_status(client, run_id, "pending_budget")

    assert pending["current_node_key"] == "n1"
    first = pending["nodes"][0]
    assert first["status"] == "pending_budget"
