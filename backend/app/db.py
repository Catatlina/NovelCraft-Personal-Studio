from __future__ import annotations

import json
import os
import uuid
from typing import Any

import psycopg2
import psycopg2.extras

DB_URL = os.getenv("DATABASE_URL", "postgresql://genius@localhost/novelcraft_dev")


def new_id(prefix: str = "") -> str:
    return str(uuid.uuid4())


def encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def decode(value: Any, default: Any = None) -> Any:
    """Decode JSON string or return value as-is (psycopg2 auto-decodes JSONB to dicts)."""
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value


class DB:
    """Thin psycopg2 wrapper matching sqlite3 Connection interface used by app code."""

    def __init__(self, conn: psycopg2.extensions.connection):
        self._conn = conn
        self._cur = conn.cursor()

    def execute(self, sql: str, params: tuple = ()) -> DB:
        self._cur.execute(sql, params)
        return self

    def fetchone(self) -> dict[str, Any] | None:
        row = self._cur.fetchone()
        if row is None:
            return None
        if isinstance(row, dict):
            return row
        # RealDictRow or tuple fallback
        cols = [d[0] for d in self._cur.description] if self._cur.description else []
        return dict(zip(cols, row)) if cols else dict(row)

    def fetchall(self) -> list[dict[str, Any]]:
        rows = self._cur.fetchall()
        if not rows:
            return []
        first = rows[0]
        if isinstance(first, dict):
            return list(rows)
        cols = [d[0] for d in self._cur.description] if self._cur.description else []
        return [dict(zip(cols, r)) for r in rows]

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._cur.close()
        self._conn.close()

    def executescript(self, sql: str) -> None:
        """For compatibility only — split on semicolons and execute each."""
        for stmt in sql.split(";"):
            stmt = stmt.strip()
            if stmt and not stmt.startswith("--"):
                self._cur.execute(stmt)


def connect() -> DB:
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    return DB(conn)


def init_db() -> None:
    """Ensure seed data exists (tables already created by Alembic)."""
    db = connect()
    existing = db.execute("SELECT id FROM projects LIMIT 1").fetchone()
    if existing is None:
        # Create default user
        user_id = new_id()
        from .core.security import hash_password
        db.execute(
            "INSERT INTO users (id, email, password_hash, display_name) VALUES (%s, %s, %s, %s)",
            (user_id, "admin@novelcraft.local", hash_password("admin123"), "管理员"),
        )
        project_id = new_id()
        db.execute(
            "INSERT INTO projects (id, name, description, owner_id) VALUES (%s, %s, %s, %s)",
            (project_id, "NovelCraft Studio", "默认创作项目", user_id),
        )
        db.execute(
            "INSERT INTO budgets (id, project_id, scope, limit_cny, spent_cny) VALUES (%s, %s, %s, %s, %s)",
            (new_id("bdg"), project_id, "bootstrap", 2.0, 0),
        )
    from .prompt_registry import PROMPT_SEEDS
    GOLDEN_CASES = {
        "bootstrap.gen_titles": [{"idea":"AI觉醒","genre":"科幻","expected_titles":3},{"idea":"重生80年代","genre":"都市","expected_titles":3},{"idea":"修仙废柴逆袭","genre":"仙侠","expected_titles":3}],
        "bootstrap.gen_synopsis": [{"title":"测试","genre":"科幻","expected_length":200}]*3,
        "bootstrap.gen_worldview": [{"title":"测试","genre":"科幻","expected_elements":["科技体系"]}]*3,
        "bootstrap.gen_characters": [{"title":"测试","genre":"科幻","min_characters":3}]*3,
        "bootstrap.gen_outline": [{"title":"测试","genre":"科幻","expected_volumes":3}]*3,
        "bootstrap.gen_chapter1": [{"title":"测试","style":"硬核","min_words":500}]*3,
        "bootstrap.review_7dim": [{"expected_dimensions":7,"min_score":60}]*3,
        "editor.polish": [{"input":"他走在街上。","preserves_meaning":True}]*3,
    }
    for name, version, model, template in PROMPT_SEEDS:
        cases = GOLDEN_CASES.get(name, [{"input": {}, "expected_shape": "json"}])
        db.execute(
            """
            INSERT INTO prompts (id, name, version, model, template, golden_cases)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT(name, version, model) DO NOTHING
            """,
            (new_id("prm"), name, version, model, template, encode(cases)),
        )
    task_types = [
        "gen_titles", "gen_synopsis", "gen_worldview", "gen_characters",
        "gen_outline", "gen_chapter1", "review_7dim",
        "editor_polish", "editor_rewrite", "editor_continue",
        "editor_expand", "editor_condense", "editor_deai",
        "summarize_chapter", "summarize_volume", "summarize_book",
        "gen_next_chapter", "extract_entities", "extract_foreshadowing", "expand_outline",
        "extract_timeline", "extract_arcs",
        "gen_short_titles", "gen_short_story", "review_short",
        "gen_video_script", "fetch_hotspots", "gen_daily_brief",
        "translate_segment", "cultural_localize",
    ]
    for task_type in task_types:
        db.execute(
            """
            INSERT INTO model_routes (id, task_type, provider, model, params, fallback_json)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT(task_type) DO NOTHING
            """,
            (new_id(), task_type, "deepseek", "deepseek-chat", encode({"temperature": 0.7}), encode([])),
        )
    db.commit()
    db.close()


def row_to_dict(row: dict[str, Any] | None) -> dict[str, Any] | None:
    return row
