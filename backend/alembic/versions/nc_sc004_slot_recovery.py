"""NC-SC-004: deterministic batch slots and recoverable quality state."""
from alembic import op


revision = "nc_sc004_slot_recovery"
down_revision = "nc_sc004_review_gate"


def upgrade():
    op.execute("""
        ALTER TABLE generation_batches ADD COLUMN IF NOT EXISTS start_seq INTEGER;
        ALTER TABLE generation_batches ADD COLUMN IF NOT EXISTS current_ordinal INTEGER;
        ALTER TABLE generation_batches ADD COLUMN IF NOT EXISTS quality_status VARCHAR(30) NOT NULL DEFAULT 'legacy_unverified';
    """)


def downgrade():
    op.execute("""
        ALTER TABLE generation_batches DROP COLUMN IF EXISTS quality_status;
        ALTER TABLE generation_batches DROP COLUMN IF EXISTS current_ordinal;
        ALTER TABLE generation_batches DROP COLUMN IF EXISTS start_seq;
    """)
