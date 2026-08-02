"""Persist the V7 novel -> V6 project boundary.

Revision ID: nc_v7_novel_project_mapping
Revises: nc_v6_v7_runtime_ledger
"""
from typing import Sequence, Union

from alembic import op


revision: str = "nc_v7_novel_project_mapping"
down_revision: Union[str, None] = "nc_v6_v7_runtime_ledger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS v7_novel_project_links (
            novel_id UUID PRIMARY KEY REFERENCES contents(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            source VARCHAR(40) NOT NULL DEFAULT 'v6_contents',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (novel_id, project_id)
        );
        CREATE INDEX IF NOT EXISTS v7_novel_project_links_project_idx
            ON v7_novel_project_links(project_id);

        INSERT INTO v7_novel_project_links (novel_id, project_id, source)
        SELECT id, project_id, 'v6_contents'
        FROM contents
        WHERE type = 'novel' AND is_deleted = FALSE AND project_id IS NOT NULL
        ON CONFLICT (novel_id) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS v7_novel_project_links")
