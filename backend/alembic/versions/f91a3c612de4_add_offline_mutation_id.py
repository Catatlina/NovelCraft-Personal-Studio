"""Add idempotency keys for offline content synchronization.

Revision ID: f91a3c612de4
Revises: ee2b46a77cf1
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f91a3c612de4"
down_revision: Union[str, None] = "ee2b46a77cf1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE versions ADD COLUMN IF NOT EXISTS client_mutation_id VARCHAR(100)")
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS versions_client_mutation_uq
        ON versions(client_mutation_id)
        WHERE client_mutation_id IS NOT NULL
    """)
    op.execute("ALTER TABLE ai_calls ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id)")
    op.execute("""
        UPDATE ai_calls ac SET project_id = wr.project_id
        FROM workflow_runs wr
        WHERE ac.run_id = wr.id AND ac.project_id IS NULL
    """)
    op.execute("ALTER TABLE ai_calls ADD COLUMN IF NOT EXISTS client_mutation_id VARCHAR(100)")
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ai_calls_client_mutation_uq
        ON ai_calls(project_id, client_mutation_id)
        WHERE client_mutation_id IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ai_calls_client_mutation_uq")
    op.execute("ALTER TABLE ai_calls DROP COLUMN IF EXISTS client_mutation_id")
    op.execute("ALTER TABLE ai_calls DROP COLUMN IF EXISTS project_id")
    op.execute("DROP INDEX IF EXISTS versions_client_mutation_uq")
    op.execute("ALTER TABLE versions DROP COLUMN IF EXISTS client_mutation_id")
