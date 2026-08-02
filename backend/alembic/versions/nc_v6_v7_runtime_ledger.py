"""Shared V6/V7 provider execution ledger and provenance.

Revision ID: nc_v6_v7_runtime_ledger
Revises: v7_001_init
"""
from typing import Sequence, Union

from alembic import op


revision: str = "nc_v6_v7_runtime_ledger"
down_revision: Union[str, None] = "v7_001_init"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
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
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ai_execution_ledger")
