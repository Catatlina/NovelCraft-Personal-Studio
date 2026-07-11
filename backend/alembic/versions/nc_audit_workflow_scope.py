"""Audit remediation: make saved workflows project-scoped."""
from alembic import op


revision = "nc_audit_workflow_scope"
down_revision = "nc_ops_index_repair"


def upgrade():
    op.execute("""
        ALTER TABLE workflows
            ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE CASCADE;
        CREATE UNIQUE INDEX IF NOT EXISTS workflows_project_name_uq
            ON workflows(project_id, name)
            WHERE project_id IS NOT NULL AND is_deleted = FALSE;
        CREATE INDEX IF NOT EXISTS workflows_project_updated_idx
            ON workflows(project_id, updated_at DESC)
            WHERE is_deleted = FALSE;
    """)


def downgrade():
    op.execute("""
        DROP INDEX IF EXISTS workflows_project_updated_idx;
        DROP INDEX IF EXISTS workflows_project_name_uq;
        ALTER TABLE workflows DROP COLUMN IF EXISTS project_id;
    """)
