"""bootstrap idempotency and dispatch recovery

Revision ID: f27bc1058a40
Revises: e16a42c731d9
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f27bc1058a40"
down_revision: Union[str, None] = "e16a42c731d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE workflow_runs ADD COLUMN idempotency_key VARCHAR(200);
        ALTER TABLE workflow_runs ADD COLUMN dispatch_attempts INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE workflow_runs ADD COLUMN last_dispatched_at TIMESTAMPTZ;
        ALTER TABLE workflow_runs ADD COLUMN dispatch_error TEXT;
        CREATE UNIQUE INDEX workflow_runs_idempotency_uq
            ON workflow_runs(project_id,idempotency_key) WHERE idempotency_key IS NOT NULL;

        ALTER TABLE contents ADD COLUMN generation_key VARCHAR(240);
        CREATE UNIQUE INDEX contents_generation_uq
            ON contents(project_id,generation_key) WHERE generation_key IS NOT NULL AND is_deleted=FALSE;

        ALTER TABLE knowledge_items ADD COLUMN generation_key VARCHAR(240);
        CREATE UNIQUE INDEX knowledge_items_generation_uq
            ON knowledge_items(content_id,generation_key) WHERE generation_key IS NOT NULL AND is_deleted=FALSE;
    """)


def downgrade() -> None:
    op.execute("""
        DROP INDEX IF EXISTS knowledge_items_generation_uq;
        ALTER TABLE knowledge_items DROP COLUMN IF EXISTS generation_key;
        DROP INDEX IF EXISTS contents_generation_uq;
        ALTER TABLE contents DROP COLUMN IF EXISTS generation_key;
        DROP INDEX IF EXISTS workflow_runs_idempotency_uq;
        ALTER TABLE workflow_runs DROP COLUMN IF EXISTS dispatch_error;
        ALTER TABLE workflow_runs DROP COLUMN IF EXISTS last_dispatched_at;
        ALTER TABLE workflow_runs DROP COLUMN IF EXISTS dispatch_attempts;
        ALTER TABLE workflow_runs DROP COLUMN IF EXISTS idempotency_key;
    """)
