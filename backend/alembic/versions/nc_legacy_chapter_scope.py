"""Track and reconcile historical chapters without a novel parent.

Revision ID: nc_legacy_chapter_scope
Revises: nc_v7_novel_project_mapping

The migration is deliberately non-destructive.  Existing orphan chapters are
marked as legacy-unlinked and retained in place.  A separate reconciliation
service decides whether a chapter can be attached to a novel using recorded
evidence; it never guesses from prose alone.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "nc_legacy_chapter_scope"
down_revision: Union[str, None] = "nc_v7_novel_project_mapping"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE contents
            ADD COLUMN IF NOT EXISTS scope_status VARCHAR(32);

        UPDATE contents
        SET scope_status = CASE
            WHEN type = 'chapter' AND parent_id IS NULL THEN 'legacy_unlinked'
            ELSE 'canonical'
        END
        WHERE scope_status IS NULL;

        CREATE INDEX IF NOT EXISTS contents_project_scope_status_idx
            ON contents(project_id, type, scope_status);

        CREATE TABLE IF NOT EXISTS legacy_chapter_resolutions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chapter_id UUID NOT NULL UNIQUE REFERENCES contents(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            status VARCHAR(32) NOT NULL DEFAULT 'unscanned',
            confidence NUMERIC(5,4),
            candidates JSONB NOT NULL DEFAULT '[]',
            evidence JSONB NOT NULL DEFAULT '{}',
            selected_novel_id UUID REFERENCES contents(id),
            source VARCHAR(40) NOT NULL DEFAULT 'legacy_reconciler',
            resolved_by UUID REFERENCES users(id),
            resolved_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT legacy_chapter_resolution_status_check
                CHECK (status IN (
                    'unscanned', 'pending', 'auto_bound', 'confirmed',
                    'unlinked', 'rejected'
                ))
        );
        CREATE INDEX IF NOT EXISTS legacy_chapter_resolutions_project_idx
            ON legacy_chapter_resolutions(project_id, status);
        CREATE INDEX IF NOT EXISTS legacy_chapter_resolutions_selected_novel_idx
            ON legacy_chapter_resolutions(selected_novel_id);

        INSERT INTO legacy_chapter_resolutions (chapter_id, project_id, status)
        SELECT id, project_id, 'unscanned'
        FROM contents
        WHERE type = 'chapter'
          AND parent_id IS NULL
          AND is_deleted = FALSE
        ON CONFLICT (chapter_id) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS legacy_chapter_resolutions")
    op.execute("DROP INDEX IF EXISTS contents_project_scope_status_idx")
    op.execute("ALTER TABLE contents DROP COLUMN IF EXISTS scope_status")
