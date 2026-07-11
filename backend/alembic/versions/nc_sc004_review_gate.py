"""NC-SC-004: chapter review gate and truthful batch counters."""
from alembic import op


revision = "nc_sc004_review_gate"
down_revision = "nc_sc004_batch_recovery"


def upgrade():
    op.execute("""
        ALTER TABLE reviews ADD COLUMN IF NOT EXISTS generation_key VARCHAR(240);
        CREATE UNIQUE INDEX IF NOT EXISTS reviews_generation_uq
            ON reviews(content_id,generation_key) WHERE generation_key IS NOT NULL;
        ALTER TABLE generation_batches ADD COLUMN IF NOT EXISTS generated_count INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE generation_batches ADD COLUMN IF NOT EXISTS reviewed_count INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE generation_batches ADD COLUMN IF NOT EXISTS accepted_count INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE generation_batches ADD COLUMN IF NOT EXISTS needs_review_count INTEGER NOT NULL DEFAULT 0;
    """)


def downgrade():
    op.execute("""
        ALTER TABLE generation_batches DROP COLUMN IF EXISTS needs_review_count;
        ALTER TABLE generation_batches DROP COLUMN IF EXISTS accepted_count;
        ALTER TABLE generation_batches DROP COLUMN IF EXISTS reviewed_count;
        ALTER TABLE generation_batches DROP COLUMN IF EXISTS generated_count;
        DROP INDEX IF EXISTS reviews_generation_uq;
        ALTER TABLE reviews DROP COLUMN IF EXISTS generation_key;
    """)
