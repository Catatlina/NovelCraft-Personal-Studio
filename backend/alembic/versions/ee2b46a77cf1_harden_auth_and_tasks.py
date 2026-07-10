"""Harden auth sessions and add cancellable generation batches.

Revision ID: ee2b46a77cf1
Revises: ccfe68410107
"""
from typing import Sequence, Union

from alembic import op

revision: str = "ee2b46a77cf1"
down_revision: Union[str, None] = "ccfe68410107"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0")
    op.execute("""
        CREATE TABLE IF NOT EXISTS generation_batches (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id),
            novel_id UUID NOT NULL REFERENCES contents(id),
            requested_count INTEGER NOT NULL CHECK (requested_count BETWEEN 1 AND 50),
            completed_count INTEGER NOT NULL DEFAULT 0,
            status VARCHAR(30) NOT NULL DEFAULT 'pending',
            cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
            celery_task_id VARCHAR(255),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS generation_batches_project_idx ON generation_batches(project_id)")
    op.execute("""
        CREATE INDEX IF NOT EXISTS knowledge_vectors_embedding_hnsw
        ON knowledge_vectors USING hnsw (embedding vector_cosine_ops)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS generation_batches")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS token_version")
