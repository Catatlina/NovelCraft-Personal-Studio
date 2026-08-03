from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _auth_project():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"history-{uuid.uuid4().hex[:8]}@nc.dev"
    token = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "test1234"},
    ).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    return client, headers, project_id


def test_generation_history_merges_v6_and_v7_runs():
    from app.db import connect, encode, new_id

    client, headers, project_id = _auth_project()
    novel_id = client.post(
        f"/api/v1/projects/{project_id}/novels",
        headers=headers,
        json={
            "idea": "一名守界人发现家族欠下的债会在现实中兑现。",
            "genre": "玄幻",
            "style": "紧凑、动作优先",
            "target_words": 800000,
        },
    ).json()["data"]["id"]
    v6_id, v7_id = new_id(), new_id()

    db = connect()
    db.execute(
        """INSERT INTO workflow_runs
           (id, project_id, novel_id, workflow_key, status, context, created_at, updated_at)
           VALUES (%s,%s,%s,'bootstrap','succeeded',%s,now() - interval '2 minutes',now() - interval '2 minutes')""",
        (v6_id, project_id, novel_id, encode({"source": "test"})),
    )
    db.execute(
        """INSERT INTO run_nodes
           (id, run_id, node_key, kind, title, status, output)
           VALUES (%s,%s,'write_chapter_draft','agent','章节初稿','succeeded',%s)""",
        (new_id(), v6_id, encode({})),
    )
    db.execute(
        """INSERT INTO v7_agent_runs
           (id, novel_id, run_type, status, chapter_number, step_count,
            total_tokens, total_cost, created_at, updated_at)
           VALUES (%s,%s,'chapter_generation','completed',3,7,1200,0.12,
                   now() - interval '1 minute',now() - interval '1 minute')""",
        (v7_id, novel_id),
    )
    db.commit()
    db.close()

    response = client.get(
        "/api/v1/history",
        headers=headers,
        params={"project_id": project_id},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] == 2
    assert {item["engine"] for item in payload["items"]} == {"v6", "v7"}
    assert payload["items"][0]["engine"] == "v7"
    assert payload["items"][0]["chapter_number"] == 3
    assert payload["items"][0]["step_count"] == 7
    assert payload["items"][1]["engine"] == "v6"
    assert payload["items"][1]["step_count"] == 1

    filtered = client.get(
        "/api/v1/history",
        headers=headers,
        params={"project_id": project_id, "novel_id": novel_id, "limit": 1},
    )
    assert filtered.status_code == 200
    assert filtered.json()["data"]["total"] == 2
    assert len(filtered.json()["data"]["items"]) == 1

    second_page = client.get(
        "/api/v1/history",
        headers=headers,
        params={"project_id": project_id, "novel_id": novel_id, "limit": 1, "offset": 1},
    )
    assert second_page.status_code == 200
    assert second_page.json()["data"]["items"][0]["engine"] == "v6"


def test_generation_history_requires_project_membership():
    client, _headers, project_id = _auth_project()
    other_client, other_headers, _other_project_id = _auth_project()
    del other_client

    response = client.get(
        "/api/v1/history",
        headers=other_headers,
        params={"project_id": project_id},
    )
    assert response.status_code == 403
