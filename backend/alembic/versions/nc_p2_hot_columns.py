"""P2-T3 / Q11: promote hot JSONB fields on ``contents`` to first-class columns.

``contents.meta->>'seq'``, ``meta->>'auto_serial'`` and the batch id participate
in MAX()/ORDER BY and equality filters on long novels / large fleets, but JSONB
extractions have no usable index and degrade linearly. Promote them to real
columns (``seq``, ``batch_id``, ``auto_serial``) and add supporting indexes so
the reads in ``app/workers/tasks.py`` stay O(log n).

Backward compatible: the application continues to write ``meta->>'seq'`` as a
fallback and reads prefer the new column, falling back to ``meta`` when NULL,
so pre-migration rows keep working.
"""
from alembic import op


revision = "nc_p2_hot_columns"
down_revision = ("nc_p0_metering_billing", "nc_audit_workflow_scope")
branch_labels = None
depends_on = None


def upgrade():
    # seq: chapter ordering within a novel (nullable → old rows untouched).
    op.execute("ALTER TABLE contents ADD COLUMN IF NOT EXISTS seq INTEGER")
    # batch_id: which generation batch produced the chapter (nullable).
    op.execute("ALTER TABLE contents ADD COLUMN IF NOT EXISTS batch_id VARCHAR(64)")
    # auto_serial: novel-level flag enabling automatic serialization.
    op.execute(
        "ALTER TABLE contents ADD COLUMN IF NOT EXISTS auto_serial BOOLEAN "
        "NOT NULL DEFAULT FALSE"
    )

    # Indexes: per-project ordered chapter scan + auto-serial fleet filter.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_contents_project_seq "
        "ON contents(project_id, seq)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_contents_auto_serial "
        "ON contents(auto_serial) WHERE auto_serial IS TRUE"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_contents_auto_serial")
    op.execute("DROP INDEX IF EXISTS idx_contents_project_seq")
    op.execute("ALTER TABLE contents DROP COLUMN IF EXISTS auto_serial")
    op.execute("ALTER TABLE contents DROP COLUMN IF EXISTS batch_id")
    op.execute("ALTER TABLE contents DROP COLUMN IF EXISTS seq")
