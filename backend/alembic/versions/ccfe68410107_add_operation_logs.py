"""add_operation_logs

Revision ID: ccfe68410107
Revises: a70d10a931fb
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa

revision = "ccfe68410107"
down_revision = "a70d10a931fb"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS operation_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id),
            user_id UUID NOT NULL REFERENCES users(id),
            action VARCHAR(50) NOT NULL,
            target VARCHAR(200),
            detail JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS op_logs_project_idx ON operation_logs(project_id);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS operation_logs;")
