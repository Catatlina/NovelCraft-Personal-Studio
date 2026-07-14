"""NC-FUS-004 推进到待验收：checkpoint 持久化、前后对账、重复数据检测/治理（幂等）、迁移演练。"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _auth_project():
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()
    client = TestClient(app)
    email = f"fus4-{uuid.uuid4().hex[:8]}@nc.dev"
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "test1234"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = client.get("/api/v1/projects", headers=headers).json()["data"][0]["id"]
    return client, headers, project_id


def test_checkpoint_persists_and_reconciliation_detects_inserted_rows():
    from app.db import connect, encode, new_id
    from app.services.fusion_governance import (
        compare_migration_checkpoints, create_fusion_migration_checkpoint,
        list_migration_checkpoints)

    _, _, project_id = _auth_project()
    before = create_fusion_migration_checkpoint(name="对账前")
    assert before["checkpoint_id"]
    assert before["table_counts"].get("contents", 0) >= 0

    db = connect()
    db.execute(
        "INSERT INTO contents (id,project_id,type,title,body,meta,status) VALUES (%s,%s,'note','对账新增行',%s,%s,'draft')",
        (new_id(), project_id, encode({}), encode({})),
    )
    db.commit(); db.close()

    after = create_fusion_migration_checkpoint(name="对账后")
    diff = compare_migration_checkpoints(before["checkpoint_id"], after["checkpoint_id"])
    assert diff["status"] == "ok"
    assert diff["changes"]["contents"]["delta"] >= 1
    assert diff["balanced"] is False

    listed = list_migration_checkpoints(limit=5)
    names = [c["name"] for c in listed]
    assert "对账后" in names and "对账前" in names

    missing = compare_migration_checkpoints(before["checkpoint_id"], str(uuid.uuid4()))
    assert missing["status"] == "error"


def test_duplicate_detection_and_cleanup_is_idempotent():
    from app.db import connect, encode, new_id
    from app.services.fusion_governance import cleanup_duplicate_data, detect_duplicate_data

    _, _, project_id = _auth_project()
    novel_id = new_id()
    db = connect()
    db.execute(
        "INSERT INTO contents (id,project_id,type,title,body,meta,status) VALUES (%s,%s,'novel','重复治理小说',%s,%s,'draft')",
        (novel_id, project_id, encode({"type": "doc", "content": []}), encode({})),
    )
    dup_ids = []
    for i in range(2):
        cid = new_id()
        dup_ids.append(cid)
        db.execute(
            "INSERT INTO contents (id,project_id,parent_id,type,title,body,meta,status,created_at) "
            "VALUES (%s,%s,%s,'chapter','第七章',%s,%s,'draft', now() + (%s * interval '1 second'))",
            (cid, project_id, novel_id, encode({"type": "doc", "content": []}), encode({"seq": 7}), i),
        )
    db.commit(); db.close()

    detection = detect_duplicate_data()
    chapter_probe = detection["probes"]["chapter_seq"]
    target = next((g for g in chapter_probe["groups"] if g["group_key"] == novel_id), None)
    assert target is not None and target["count"] == 2
    # canonical = earliest row; the later duplicate is the one to retire
    assert target["extra_ids"] == [dup_ids[1]]

    result = cleanup_duplicate_data("chapter_seq")
    assert result["status"] == "ok" and dup_ids[1] in result["retired_ids"]

    db = connect()
    survivor = db.execute("SELECT id FROM contents WHERE parent_id=%s AND is_deleted=FALSE", (novel_id,)).fetchall()
    retired = db.execute("SELECT is_deleted FROM contents WHERE id=%s", (dup_ids[1],)).fetchone()
    ledger = db.execute(
        "SELECT COUNT(*) AS c FROM audit_logs WHERE entity_type='duplicate_cleanup' AND entity_id=%s",
        (dup_ids[1],),
    ).fetchone()
    db.close()
    assert [r["id"] for r in survivor] == [dup_ids[0]]  # earliest kept
    assert retired["is_deleted"] is True
    assert ledger["c"] == 1  # retirement recorded in the audit ledger

    # Idempotent: a second cleanup finds nothing for this novel
    rerun = cleanup_duplicate_data("chapter_seq")
    assert dup_ids[1] not in rerun["retired_ids"]
    assert cleanup_duplicate_data("nosuch_probe")["status"] == "error"


def test_migration_drill_passes_and_leaves_business_tables_unchanged():
    client, headers, _ = _auth_project()
    drill = client.post("/api/v1/fusion/migration/drill", headers=headers)
    assert drill.status_code == 200
    data = drill.json()["data"]
    assert data["reconciliation"]["status"] == "ok"
    assert data["business_tables_unchanged"] is True
    assert data["integrity"]["integrity_pass"] is True
    assert data["passed"] is True

    # Drill is repeatable — a second run also passes (idempotent rehearsal)
    again = client.post("/api/v1/fusion/migration/drill", headers=headers).json()["data"]
    assert again["passed"] is True


def test_migration_endpoints_roundtrip():
    client, headers, _ = _auth_project()
    created = client.post("/api/v1/fusion/migration/checkpoint", headers=headers,
                          params={"name": "api检查点"}).json()["data"]
    assert created["checkpoint_id"]
    listed = client.get("/api/v1/fusion/migration/checkpoints", headers=headers).json()["data"]
    assert any(c["checkpoint_id"] == created["checkpoint_id"] for c in listed)
    dupes = client.get("/api/v1/fusion/migration/duplicates", headers=headers)
    assert dupes.status_code == 200
    assert "probes" in dupes.json()["data"]
