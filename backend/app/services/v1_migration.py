"""V1 test DB generator + migration script for TASK-004."""
import sqlite3, os, uuid

def create_v1_test_db(path: str = "/tmp/novelcraft_v1_test.db"):
    """Create a simulated V1 SQLite database for migration testing."""
    db = sqlite3.connect(path)
    
    db.execute("""CREATE TABLE IF NOT EXISTS novels (
        id TEXT PRIMARY KEY, title TEXT, author TEXT, genre TEXT, 
        style TEXT, target_words INTEGER, status TEXT, created_at TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS chapters (
        id TEXT PRIMARY KEY, novel_id TEXT, seq INTEGER, 
        title TEXT, body TEXT, status TEXT, created_at TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS characters (
        id TEXT PRIMARY KEY, novel_id TEXT, name TEXT, role TEXT,
        description TEXT, meta TEXT
    )""")
    
    # Insert 3 test novels
    n1, n2, n3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    for nid, title, genre in [(n1, "重生之都市王者", "都市"), (n2, "仙道独尊", "仙侠"), (n3, "星际殖民时代", "科幻")]:
        db.execute("INSERT INTO novels VALUES(?,?,?,?,?,?,?,?)",
                   (nid, title, "test_author", genre, "爽文", 1000000, "draft", "2024-01-01"))
        for i in range(1, 6):
            db.execute("INSERT INTO chapters VALUES(?,?,?,?,?,?,?)",
                       (str(uuid.uuid4()), nid, i, f"第{i}章 测试章节", f"这是第{i}章的测试内容...", "draft", "2024-01-01"))
        db.execute("INSERT INTO characters VALUES(?,?,?,?,?,?)",
                   (str(uuid.uuid4()), nid, "主角", "protagonist", "主角描述", '{"level": 1}'))
    db.commit()
    db.close()
    return path


def migrate_v1_to_v2(v1_path: str, project_id: str = "") -> dict:
    """Migrate V1 SQLite data to V2 PostgreSQL contents/knowledge_items."""
    from app.db import connect, new_id, encode
    v1 = sqlite3.connect(v1_path)
    v1.row_factory = sqlite3.Row
    
    if not project_id or project_id.strip() == "":
        project_id = str(uuid.uuid4())
        # Create project entry first (FK constraint)
        pdb = connect()
        pdb.execute("INSERT INTO projects (id, name, owner_id) VALUES (%s, %s, %s)",
                    (project_id, "V1 Migration Import", "00000000-0000-0000-0000-000000000000"))
        pdb.commit()
        pdb.close()
    
    novels = [dict(r) for r in v1.execute("SELECT * FROM novels").fetchall()]
    stats = {"novels": 0, "chapters": 0, "characters": 0}
    
    pg = connect()
    for novel in novels:
        nid = new_id()
        pg.execute(
            "INSERT INTO contents (id, project_id, type, title, body, meta, status) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (nid, project_id, "novel", novel["title"], encode({"text": novel.get("title","")}),
             encode({"source_type": "v1_migration", "genre": novel.get("genre",""), "author": novel.get("author","")}),
             "draft"),
        )
        stats["novels"] += 1
        
        # Migrate chapters
        chapters = v1.execute("SELECT * FROM chapters WHERE novel_id = ?", (novel["id"],)).fetchall()
        for ch in chapters:
            cid = new_id()
            pg.execute(
                "INSERT INTO contents (id, project_id, parent_id, type, title, body, meta, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (cid, project_id, nid, "chapter", ch["title"],
                 encode({"text": ch.get("body","")}),
                 encode({"seq": ch.get("seq",0), "v1_id": ch["id"]}),
                 "draft"),
            )
            stats["chapters"] += 1
        
        # Migrate characters to knowledge
        chars = v1.execute("SELECT * FROM characters WHERE novel_id = ?", (novel["id"],)).fetchall()
        for char in chars:
            pg.execute(
                "INSERT INTO knowledge_items (id, kind, title, body, meta) VALUES (%s,%s,%s,%s,%s)",
                (new_id(), "character", char["name"], char.get("description",""),
                 encode({"v1_id": char["id"], "role": char.get("role",""), "novel_id": nid})),
            )
            stats["characters"] += 1
    
    pg.commit(); pg.close()
    v1.close()
    return stats
