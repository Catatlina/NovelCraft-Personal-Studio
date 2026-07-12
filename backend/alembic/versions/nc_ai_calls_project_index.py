"""NC-OPS: Add concurrent index on ai_calls.project_id for query performance."""
from alembic import op


revision = "nc_ai_calls_project_index"
down_revision = "nc_settings_table"


def upgrade():
    conn = op.get_bind()
    conn.exec_driver_sql("COMMIT")
    conn.exec_driver_sql(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ai_calls_project ON ai_calls(project_id)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_ai_calls_project")
