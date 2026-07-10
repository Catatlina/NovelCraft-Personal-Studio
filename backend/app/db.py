from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from .prompt_registry import PROMPT_SEEDS

DB_PATH = Path(__file__).resolve().parents[1] / "novelcraft.sqlite3"


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def decode(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default
    return json.loads(value)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = connect()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS contents (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            parent_id TEXT,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL DEFAULT '{}',
            meta TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );

        CREATE TABLE IF NOT EXISTS knowledge_items (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            content_id TEXT,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            meta TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );

        CREATE TABLE IF NOT EXISTS versions (
            id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            parent_version_id TEXT,
            label TEXT NOT NULL,
            snapshot TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS workflow_runs (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            novel_id TEXT NOT NULL,
            workflow_key TEXT NOT NULL,
            status TEXT NOT NULL,
            current_node_key TEXT,
            context TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(novel_id) REFERENCES contents(id)
        );

        CREATE TABLE IF NOT EXISTS run_nodes (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            node_key TEXT NOT NULL,
            kind TEXT NOT NULL,
            agent TEXT,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempt INTEGER NOT NULL DEFAULT 0,
            output TEXT NOT NULL DEFAULT '{}',
            error TEXT,
            started_at TEXT,
            finished_at TEXT,
            UNIQUE(run_id, node_key),
            FOREIGN KEY(run_id) REFERENCES workflow_runs(id)
        );

        CREATE TABLE IF NOT EXISTS ai_calls (
            id TEXT PRIMARY KEY,
            run_id TEXT,
            node_key TEXT,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_name TEXT NOT NULL,
            task_type TEXT NOT NULL,
            input TEXT NOT NULL,
            output TEXT NOT NULL,
            prompt_tokens INTEGER NOT NULL,
            completion_tokens INTEGER NOT NULL,
            cost_cny REAL NOT NULL,
            latency_ms INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS budgets (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            scope TEXT NOT NULL,
            limit_cny REAL NOT NULL,
            spent_cny REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_id, scope),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );

        CREATE TABLE IF NOT EXISTS prompts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            version TEXT NOT NULL,
            model TEXT NOT NULL,
            template TEXT NOT NULL,
            golden_cases TEXT NOT NULL DEFAULT '[]',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, version, model)
        );

        CREATE TABLE IF NOT EXISTS model_routes (
            id TEXT PRIMARY KEY,
            task_type TEXT NOT NULL UNIQUE,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            params TEXT NOT NULL DEFAULT '{}',
            fallback_json TEXT NOT NULL DEFAULT '[]',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    existing = conn.execute("SELECT id FROM projects LIMIT 1").fetchone()
    if existing is None:
        project_id = new_id("prj")
        conn.execute(
            "INSERT INTO projects (id, name, description) VALUES (?, ?, ?)",
            (project_id, "NovelCraft Studio", "默认创作项目"),
        )
        conn.execute(
            "INSERT INTO budgets (id, project_id, scope, limit_cny, spent_cny) VALUES (?, ?, ?, ?, ?)",
            (new_id("bdg"), project_id, "bootstrap", 2.0, 0),
        )
    seed_prompts_and_routes(conn)
    conn.commit()
    conn.close()


def seed_prompts_and_routes(conn: sqlite3.Connection) -> None:
    for name, version, model, template in PROMPT_SEEDS:
        conn.execute(
            """
            INSERT INTO prompts (id, name, version, model, template, golden_cases)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(name, version, model) DO NOTHING
            """,
            (new_id("prm"), name, version, model, template, encode([{"input": {}, "expected_shape": "json"}])),
        )
    task_types = [
        "gen_titles",
        "gen_synopsis",
        "gen_worldview",
        "gen_characters",
        "gen_outline",
        "gen_chapter1",
        "review_7dim",
        "editor_polish",
        "editor_rewrite",
        "editor_continue",
    ]
    for task_type in task_types:
        conn.execute(
            """
            INSERT INTO model_routes (id, task_type, provider, model, params, fallback_json)
            VALUES (?, ?, 'mock', 'mock-deepseek-chat', ?, ?)
            ON CONFLICT(task_type) DO NOTHING
            """,
            (new_id("rte"), task_type, encode({"temperature": 0.7}), encode([])),
        )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)
