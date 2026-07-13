"""Database-backed reliability contracts for NC-SC-003 planning runs."""
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def test_idempotency_migration_uses_nullable_partial_unique_keys():
    sql = (ROOT / "backend/alembic/versions/f27bc1058a40_bootstrap_idempotency.py").read_text(encoding="utf-8")
    assert "workflow_runs ADD COLUMN idempotency_key" in sql
    assert "contents ADD COLUMN generation_key" in sql
    assert "knowledge_items ADD COLUMN generation_key" in sql
    assert sql.count("WHERE") >= 3
    assert "UPDATE workflow_runs SET idempotency_key" not in sql


class _Cursor:
    def __init__(self, one=None):
        self.one = one

    def fetchone(self):
        return self.one


class _Db:
    def __init__(self, one=None):
        self.one = one
        self.statements = []
        self.committed = False

    def execute(self, sql, params=()):
        self.statements.append((" ".join(sql.split()), params))
        return _Cursor(self.one)

    def commit(self):
        self.committed = True

    def close(self):
        pass


def test_dispatch_failure_is_persisted_and_raised(monkeypatch):
    from app.workers import tasks

    db = _Db()
    monkeypatch.setattr(tasks, "connect", lambda: db)
    monkeypatch.setattr(tasks.execute_bootstrap, "delay", lambda *_args: (_ for _ in ()).throw(RuntimeError("broker offline")))

    with pytest.raises(RuntimeError, match="broker offline"):
        tasks.dispatch_bootstrap_run("run-1", "n3")

    assert db.committed
    assert any("status='dispatch_failed'" in sql and params == ("broker offline", "run-1")
               for sql, params in db.statements)


def test_existing_undispatched_idempotent_run_is_redriven(monkeypatch):
    from app.workers import tasks

    existing = {"id": "run-existing", "status": "pending", "last_dispatched_at": None, "current_node_key": "n3"}
    db = _Db(existing)
    redrives = []
    monkeypatch.setattr(tasks, "connect", lambda: db)
    monkeypatch.setattr(tasks, "dispatch_bootstrap_run", lambda *args: redrives.append(args))

    run_id = tasks.create_run("project-1", "novel-1", idempotency_key="ranking-topic:t1:book-plan:v1")

    assert run_id == "run-existing"
    assert redrives == [("run-existing", "n3", "", "", "")]
    assert not any(sql.startswith("INSERT INTO workflow_runs") for sql, _ in db.statements)


def test_generated_business_outputs_use_stable_keys_and_conflict_handling():
    source = (ROOT / "backend/app/workers/tasks.py").read_text(encoding="utf-8")
    assert "run:{run_id}:node:{node_key}:worldview:v2" in source
    assert "run:{run_id}:node:{node_key}:character:{index}:v2" in source
    # V2 chapters key by stable novel+seq slot, not by run
    assert "novel:{novel_id}:chapter:{chapter_seq}:bootstrap:v2" in source
    assert source.count("ON CONFLICT") >= 3
    assert 'client_mutation_id = f"bootstrap:{run_id}:{node_key}:v2"' in source
