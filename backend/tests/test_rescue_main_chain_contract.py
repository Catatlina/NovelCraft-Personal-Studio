"""T2 rescue gate for login -> project -> library -> chapter -> save."""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def test_login_project_library_chapter_save_round_trip():
    from app.core.rate_limit import limiter
    from app.db import connect, encode, new_id
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"rescue-{uuid.uuid4().hex[:10]}@nc.dev"
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "test1234"},
    )
    assert registered.status_code == 200
    token = registered.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    projects = client.get("/api/v1/projects", headers=headers)
    assert projects.status_code == 200
    project_id = projects.json()["data"][0]["id"]

    novel_id, chapter_id = new_id(), new_id()
    db = connect()
    db.execute(
        """INSERT INTO contents (id,project_id,type,title,body,meta,status)
           VALUES (%s,%s,'novel','抢救测试小说',%s,%s,'draft')""",
        (novel_id, project_id, encode({"type": "doc", "content": []}), encode({})),
    )
    db.execute(
        """INSERT INTO contents (id,project_id,parent_id,type,title,body,meta,status)
           VALUES (%s,%s,%s,'chapter','第一章',%s,%s,'draft')""",
        (
            chapter_id,
            project_id,
            novel_id,
            encode({"type": "doc", "content": [{"type": "paragraph", "text": "旧正文"}]}),
            encode({"seq": 1}),
        ),
    )
    db.commit()
    db.close()

    library = client.get(
        "/api/v1/library/books",
        headers=headers,
        params={"project_id": project_id},
    )
    assert library.status_code == 200
    assert any(book["id"] == novel_id for book in library.json()["data"])

    chapters = client.get(
        "/api/v1/contents",
        headers=headers,
        params={"project_id": project_id, "parent_id": novel_id},
    )
    assert chapters.status_code == 200
    assert chapters.json()["data"][0]["id"] == chapter_id

    new_body = {
        "type": "doc",
        "content": [{"type": "paragraph", "text": "保存后的正文"}],
    }
    saved = client.put(
        f"/api/v1/contents/{chapter_id}",
        headers=headers,
        json={"body": new_body, "label": "rescue_contract"},
    )
    assert saved.status_code == 200
    assert saved.json()["data"]["body"] == new_body

    reopened = client.get(f"/api/v1/contents/{chapter_id}", headers=headers)
    assert reopened.status_code == 200
    assert reopened.json()["data"]["body"] == new_body
