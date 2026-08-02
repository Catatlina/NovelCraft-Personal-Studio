"""Shared V6/V7 AI execution provenance and cost ledger.

This is the common runtime boundary.  The legacy V6 gateway and the async V7
gateway may use different session APIs, but every provider attempt is written
to the same ``ai_execution_ledger`` schema with the same prompt hash, version,
usage, cost and failure semantics.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import text


SHARED_LEDGER_TABLE = "ai_execution_ledger"

SHARED_LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS ai_execution_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_key VARCHAR(300) NOT NULL UNIQUE,
    gateway_version VARCHAR(20) NOT NULL,
    project_id VARCHAR(128),
    novel_id VARCHAR(128),
    run_id VARCHAR(128),
    step_id VARCHAR(128),
    task_type VARCHAR(200) NOT NULL,
    prompt_name VARCHAR(200) NOT NULL,
    prompt_version VARCHAR(100),
    prompt_hash VARCHAR(64) NOT NULL,
    provider VARCHAR(100) NOT NULL,
    model VARCHAR(100) NOT NULL,
    status VARCHAR(30) NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    cost_cny NUMERIC(20, 8) NOT NULL DEFAULT 0,
    latency_ms INTEGER,
    client_mutation_id VARCHAR(255),
    error TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ai_execution_ledger_project_idx
    ON ai_execution_ledger(project_id);
CREATE INDEX IF NOT EXISTS ai_execution_ledger_novel_idx
    ON ai_execution_ledger(novel_id);
CREATE INDEX IF NOT EXISTS ai_execution_ledger_run_idx
    ON ai_execution_ledger(run_id);
CREATE INDEX IF NOT EXISTS ai_execution_ledger_prompt_idx
    ON ai_execution_ledger(prompt_name, prompt_version);
CREATE INDEX IF NOT EXISTS ai_execution_ledger_created_idx
    ON ai_execution_ledger(created_at);
"""


def prompt_hash(
    rendered_prompt: str,
    *,
    system_prompt: str = "",
    history: list[dict[str, str]] | None = None,
) -> str:
    """Hash the exact provider input, including system/history context."""
    payload = json.dumps(
        {
            "system_prompt": system_prompt,
            "history": history or [],
            "rendered_prompt": rendered_prompt,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalise_prompt_version(value: str | int | None) -> str:
    """Return an explicit version label for every execution."""
    value = str(value or "runtime-1").strip()
    return value or "runtime-1"


def execution_key(
    gateway_version: str,
    *,
    scope: str,
    client_mutation_id: str | None = None,
    attempt: int | None = None,
) -> str:
    """Build a bounded, replay-safe key for one billable provider attempt."""
    suffix = client_mutation_id or uuid.uuid4().hex
    if attempt is not None:
        suffix = f"{suffix}:attempt:{attempt}"
    raw = f"{gateway_version}:{scope}:{suffix}"
    if len(raw) <= 300:
        return raw
    return f"{gateway_version}:{hashlib.sha256(raw.encode()).hexdigest()}"


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def ensure_shared_ledger_schema(conn: Any) -> None:
    """Create the shared table for development databases not yet migrated."""
    conn.execute(SHARED_LEDGER_DDL)


def _ledger_conditions(
    *,
    novel_id: str | uuid.UUID | None = None,
    project_id: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Build the common, half-open time and scope filter for ledger queries."""
    conditions = ["status = 'succeeded'"]
    params: dict[str, Any] = {}
    if novel_id is not None:
        conditions.append("novel_id = :novel_id")
        params["novel_id"] = str(novel_id)
    if project_id is not None:
        conditions.append("project_id = :project_id")
        params["project_id"] = str(project_id)
    if start_date:
        conditions.append("created_at >= :start_date")
        params["start_date"] = start_date
    if end_date:
        # Avoid PostgreSQL's ``:param::date`` syntax here: SQLAlchemy's text
        # parser can interpret the second colon as part of the bind name.
        conditions.append("created_at < :end_date_exclusive")
        params["end_date_exclusive"] = end_date + timedelta(days=1)
    return conditions, params


def record_sync_execution(
    conn: Any,
    *,
    execution_key: str,
    gateway_version: str,
    project_id: str | None,
    novel_id: str | None,
    run_id: str | None,
    step_id: str | None,
    task_type: str,
    prompt_name: str,
    prompt_version: str | None,
    rendered_prompt: str,
    prompt_hash_value: str | None = None,
    provider: str,
    model: str,
    status: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost_cny: float = 0.0,
    latency_ms: int | None = None,
    client_mutation_id: str | None = None,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Write one V6 execution into the shared ledger in the caller's txn."""
    from ..db import encode

    conn.execute(
        f"""
        INSERT INTO {SHARED_LEDGER_TABLE} (
            execution_key, gateway_version, project_id, novel_id, run_id, step_id,
            task_type, prompt_name, prompt_version, prompt_hash, provider, model,
            status, prompt_tokens, completion_tokens, cost_cny, latency_ms,
            client_mutation_id, error, metadata
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (execution_key) DO UPDATE SET
            gateway_version = EXCLUDED.gateway_version,
            project_id = EXCLUDED.project_id,
            novel_id = EXCLUDED.novel_id,
            run_id = EXCLUDED.run_id,
            step_id = EXCLUDED.step_id,
            task_type = EXCLUDED.task_type,
            prompt_name = EXCLUDED.prompt_name,
            prompt_version = EXCLUDED.prompt_version,
            prompt_hash = EXCLUDED.prompt_hash,
            provider = EXCLUDED.provider,
            model = EXCLUDED.model,
            status = EXCLUDED.status,
            prompt_tokens = EXCLUDED.prompt_tokens,
            completion_tokens = EXCLUDED.completion_tokens,
            cost_cny = EXCLUDED.cost_cny,
            latency_ms = EXCLUDED.latency_ms,
            client_mutation_id = EXCLUDED.client_mutation_id,
            error = EXCLUDED.error,
            metadata = EXCLUDED.metadata,
            updated_at = now()
        """,
        (
            execution_key,
            gateway_version,
            _as_text(project_id),
            _as_text(novel_id),
            _as_text(run_id),
            _as_text(step_id),
            task_type,
            prompt_name,
            normalise_prompt_version(prompt_version),
            prompt_hash_value or prompt_hash(rendered_prompt),
            provider,
            model,
            status,
            int(prompt_tokens or 0),
            int(completion_tokens or 0),
            float(cost_cny or 0.0),
            latency_ms,
            client_mutation_id,
            error,
            encode(metadata or {}),
        ),
    )


async def record_async_execution(
    db: Any,
    *,
    execution_key: str,
    gateway_version: str,
    project_id: str | None,
    novel_id: str | None,
    run_id: str | None,
    step_id: str | None,
    task_type: str,
    prompt_name: str,
    prompt_version: str | None,
    rendered_prompt: str,
    prompt_hash_value: str | None = None,
    provider: str,
    model: str,
    status: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost_cny: float = 0.0,
    latency_ms: int | None = None,
    client_mutation_id: str | None = None,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Write one V7 execution into the same ledger in the open txn."""
    await db.execute(
        text(
            f"""
            INSERT INTO {SHARED_LEDGER_TABLE} (
                id, execution_key, gateway_version, project_id, novel_id, run_id, step_id,
                task_type, prompt_name, prompt_version, prompt_hash, provider, model,
                status, prompt_tokens, completion_tokens, cost_cny, latency_ms,
                client_mutation_id, error, metadata
            ) VALUES (
                :id, :execution_key, :gateway_version, :project_id, :novel_id, :run_id, :step_id,
                :task_type, :prompt_name, :prompt_version, :prompt_hash, :provider, :model,
                :status, :prompt_tokens, :completion_tokens, :cost_cny, :latency_ms,
                :client_mutation_id, :error, CAST(:metadata_json AS JSONB)
            )
            ON CONFLICT (execution_key) DO UPDATE SET
                gateway_version = EXCLUDED.gateway_version,
                project_id = EXCLUDED.project_id,
                novel_id = EXCLUDED.novel_id,
                run_id = EXCLUDED.run_id,
                step_id = EXCLUDED.step_id,
                task_type = EXCLUDED.task_type,
                prompt_name = EXCLUDED.prompt_name,
                prompt_version = EXCLUDED.prompt_version,
                prompt_hash = EXCLUDED.prompt_hash,
                provider = EXCLUDED.provider,
                model = EXCLUDED.model,
                status = EXCLUDED.status,
                prompt_tokens = EXCLUDED.prompt_tokens,
                completion_tokens = EXCLUDED.completion_tokens,
                cost_cny = EXCLUDED.cost_cny,
                latency_ms = EXCLUDED.latency_ms,
                client_mutation_id = EXCLUDED.client_mutation_id,
                error = EXCLUDED.error,
                metadata = EXCLUDED.metadata,
                updated_at = now()
            """
        ),
        {
            "id": uuid.uuid4(),
            "execution_key": execution_key,
            "gateway_version": gateway_version,
            "project_id": _as_text(project_id),
            "novel_id": _as_text(novel_id),
            "run_id": _as_text(run_id),
            "step_id": _as_text(step_id),
            "task_type": task_type,
            "prompt_name": prompt_name,
            "prompt_version": normalise_prompt_version(prompt_version),
            "prompt_hash": prompt_hash_value or prompt_hash(rendered_prompt),
            "provider": provider,
            "model": model,
            "status": status,
            "prompt_tokens": int(prompt_tokens or 0),
            "completion_tokens": int(completion_tokens or 0),
            "cost_cny": float(cost_cny or 0.0),
            "latency_ms": latency_ms,
            "client_mutation_id": client_mutation_id,
            "error": error,
            "metadata_json": json.dumps(metadata or {}, ensure_ascii=False),
        },
    )
    flush = getattr(db, "flush", None)
    if flush:
        await flush()


async def async_ledger_summary(
    db: Any,
    *,
    novel_id: str | uuid.UUID | None = None,
    project_id: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """Return source-of-truth spend without double-counting trace tables."""
    conditions, params = _ledger_conditions(
        novel_id=novel_id,
        project_id=project_id,
        start_date=start_date,
        end_date=end_date,
    )
    result = await db.execute(
        text(
            f"""
            SELECT COUNT(*) AS calls,
                   COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                   COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                   COALESCE(SUM(cost_cny), 0) AS cost_cny
            FROM {SHARED_LEDGER_TABLE}
            WHERE {' AND '.join(conditions)}
            """
        ),
        params,
    )
    row = result.mappings().one()
    return {
        "calls": int(row["calls"] or 0),
        "prompt_tokens": int(row["prompt_tokens"] or 0),
        "completion_tokens": int(row["completion_tokens"] or 0),
        "tokens": int(row["prompt_tokens"] or 0) + int(row["completion_tokens"] or 0),
        "cost_cny": round(float(row["cost_cny"] or 0.0), 8),
        "source": SHARED_LEDGER_TABLE,
        "gateway_versions": await _gateway_totals(db, conditions, params),
    }


async def _gateway_totals(
    db: Any, conditions: list[str], params: dict[str, Any]
) -> list[dict[str, Any]]:
    result = await db.execute(
        text(
            f"""
            SELECT gateway_version, COUNT(*) AS calls,
                   COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                   COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                   COALESCE(SUM(cost_cny), 0) AS cost_cny
            FROM {SHARED_LEDGER_TABLE}
            WHERE {' AND '.join(conditions)}
            GROUP BY gateway_version ORDER BY gateway_version
            """
        ),
        params,
    )
    return [
        {
            "gateway_version": row["gateway_version"],
            "calls": int(row["calls"] or 0),
            "prompt_tokens": int(row["prompt_tokens"] or 0),
            "completion_tokens": int(row["completion_tokens"] or 0),
            "cost_cny": round(float(row["cost_cny"] or 0.0), 8),
        }
        for row in result.mappings().all()
    ]


async def async_ledger_by_date(
    db: Any,
    *,
    novel_id: str | uuid.UUID | None = None,
    project_id: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """Group source-of-truth spend by UTC calendar date."""
    conditions, params = _ledger_conditions(
        novel_id=novel_id,
        project_id=project_id,
        start_date=start_date,
        end_date=end_date,
    )
    result = await db.execute(
        text(
            f"""
            SELECT (created_at AT TIME ZONE 'UTC')::date AS ledger_date,
                   COUNT(*) AS calls,
                   COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                   COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                   COALESCE(SUM(cost_cny), 0) AS cost_cny
            FROM {SHARED_LEDGER_TABLE}
            WHERE {' AND '.join(conditions)}
            GROUP BY ledger_date ORDER BY ledger_date
            """
        ),
        params,
    )
    rows = []
    for row in result.mappings().all():
        ledger_date = row["ledger_date"]
        rows.append(
            {
                "date": ledger_date.isoformat() if hasattr(ledger_date, "isoformat") else str(ledger_date),
                "calls": int(row["calls"] or 0),
                "prompt_tokens": int(row["prompt_tokens"] or 0),
                "completion_tokens": int(row["completion_tokens"] or 0),
                "tokens": int(row["prompt_tokens"] or 0) + int(row["completion_tokens"] or 0),
                "cost_cny": round(float(row["cost_cny"] or 0.0), 8),
            }
        )
    return rows


async def async_ledger_by_task_type(
    db: Any,
    *,
    novel_id: str | uuid.UUID | None = None,
    project_id: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """Group source-of-truth spend by the stable task/prompt identity."""
    conditions, params = _ledger_conditions(
        novel_id=novel_id,
        project_id=project_id,
        start_date=start_date,
        end_date=end_date,
    )
    result = await db.execute(
        text(
            f"""
            SELECT task_type, COUNT(*) AS calls,
                   COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                   COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                   COALESCE(SUM(cost_cny), 0) AS cost_cny
            FROM {SHARED_LEDGER_TABLE}
            WHERE {' AND '.join(conditions)}
            GROUP BY task_type ORDER BY task_type
            """
        ),
        params,
    )
    return [
        {
            "task_type": row["task_type"],
            "calls": int(row["calls"] or 0),
            "prompt_tokens": int(row["prompt_tokens"] or 0),
            "completion_tokens": int(row["completion_tokens"] or 0),
            "tokens": int(row["prompt_tokens"] or 0) + int(row["completion_tokens"] or 0),
            "cost_cny": round(float(row["cost_cny"] or 0.0), 8),
        }
        for row in result.mappings().all()
    ]
