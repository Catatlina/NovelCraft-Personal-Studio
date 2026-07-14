from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _auth_project():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"lib-{uuid.uuid4().hex[:8]}@nc.dev"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    return client, headers, project_id


def test_library_lists_newest_first_and_detail_contains_book_shape():
    from app.db import connect, encode, new_id

    client, headers, project_id = _auth_project()
    old_id, new_book_id = new_id(), new_id()
    chapter1_id, chapter2_id = new_id(), new_id()

    db = connect()
    db.execute(
        """INSERT INTO contents (id,project_id,type,title,body,meta,status,created_at)
           VALUES (%s,%s,'novel','旧书',%s,%s,'draft',now() - interval '1 day')""",
        (old_id, project_id, encode({"type": "doc", "content": []}),
         encode({"idea": "旧简介", "genre": "悬疑"})),
    )
    db.execute(
        """INSERT INTO contents (id,project_id,type,title,body,meta,status,created_at)
           VALUES (%s,%s,'novel','新书',%s,%s,'draft',now())""",
        (new_book_id, project_id, encode({"type": "doc", "content": []}),
         encode({"synopsis": "新书简介", "genre": "科幻", "outline": "三幕式大纲"})),
    )
    db.execute(
        """INSERT INTO contents (id,project_id,parent_id,type,title,body,meta,status,created_at)
           VALUES (%s,%s,%s,'chapter','第一章',%s,%s,'reviewed',now() - interval '1 hour')""",
        (chapter1_id, project_id, new_book_id,
         encode({"type": "doc", "content": [{"type": "paragraph", "text": "第一章正文"}]}),
         encode({"seq": 1})),
    )
    db.execute(
        """INSERT INTO contents (id,project_id,parent_id,type,title,body,meta,status,created_at)
           VALUES (%s,%s,%s,'chapter','第二章',%s,%s,'reviewed',now())""",
        (chapter2_id, project_id, new_book_id,
         encode({"type": "doc", "content": [{"type": "paragraph", "text": "第二章正文"}]}),
         encode({"seq": 2})),
    )
    db.commit()
    db.close()

    listing = client.get("/api/v1/library/books", headers=headers, params={"project_id": project_id})
    assert listing.status_code == 200
    books = listing.json()["data"]
    assert [book["title"] for book in books[:2]] == ["新书", "旧书"]
    assert books[0]["synopsis"] == "新书简介"
    assert books[0]["genre"] == "科幻"
    assert books[0]["latest_chapter_title"] == "第二章"
    assert books[0]["chapter_count"] == 2
    assert books[0]["total_words"] > 0

    detail = client.get(f"/api/v1/library/books/{new_book_id}", headers=headers)
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["book"]["title"] == "新书"
    assert data["synopsis"] == "新书简介"
    assert data["outline"] == "三幕式大纲"
    assert data["latest_chapter"]["title"] == "第二章"
    assert [chapter["title"] for chapter in data["chapters"]] == ["第一章", "第二章"]


def test_library_server_side_search_filter_sort():
    """NC-LIB-002: q/status/sort are applied server-side with whitelisted ORDER BY."""
    from app.db import connect, encode, new_id

    client, headers, project_id = _auth_project()
    a_id, b_id, c_id = new_id(), new_id(), new_id()

    db = connect()
    db.execute(
        """INSERT INTO contents (id,project_id,type,title,body,meta,status,created_at,updated_at)
           VALUES (%s,%s,'novel','深渊猎手',%s,%s,'draft',now() - interval '3 day',now() - interval '3 day')""",
        (a_id, project_id, encode({"type": "doc", "content": []}), encode({"synopsis": "玄幻冒险"})),
    )
    db.execute(
        """INSERT INTO contents (id,project_id,type,title,body,meta,status,created_at,updated_at)
           VALUES (%s,%s,'novel','都市医仙',%s,%s,'completed',now() - interval '2 day',now())""",
        (b_id, project_id, encode({"type": "doc", "content": []}), encode({"idea": "都市异能爽文"})),
    )
    db.execute(
        """INSERT INTO contents (id,project_id,type,title,body,meta,status,created_at,updated_at)
           VALUES (%s,%s,'novel','安静的角落',%s,%s,'draft',now() - interval '1 day',now() - interval '2 day')""",
        (c_id, project_id, encode({"type": "doc", "content": []}), encode({"synopsis": "文艺短篇"})),
    )
    db.commit(); db.close()

    # q searches title and synopsis/idea
    by_title = client.get("/api/v1/library/books", headers=headers,
                          params={"project_id": project_id, "q": "深渊"}).json()["data"]
    assert [b["title"] for b in by_title] == ["深渊猎手"]
    by_synopsis = client.get("/api/v1/library/books", headers=headers,
                             params={"project_id": project_id, "q": "爽文"}).json()["data"]
    assert [b["title"] for b in by_synopsis] == ["都市医仙"]

    # status filter
    completed = client.get("/api/v1/library/books", headers=headers,
                           params={"project_id": project_id, "status": "completed"}).json()["data"]
    assert [b["title"] for b in completed] == ["都市医仙"]

    # sort=updated puts the most recently edited first; sort=title is lexicographic
    updated = client.get("/api/v1/library/books", headers=headers,
                         params={"project_id": project_id, "sort": "updated"}).json()["data"]
    assert updated[0]["title"] == "都市医仙"
    titles = client.get("/api/v1/library/books", headers=headers,
                        params={"project_id": project_id, "sort": "title"}).json()["data"]
    assert [b["title"] for b in titles] == sorted(b["title"] for b in titles)

    # unknown sort key falls back to created DESC instead of erroring/injecting
    fallback = client.get("/api/v1/library/books", headers=headers,
                          params={"project_id": project_id, "sort": "id; DROP TABLE contents"}).json()["data"]
    assert [b["title"] for b in fallback][:3] == ["安静的角落", "都市医仙", "深渊猎手"]
