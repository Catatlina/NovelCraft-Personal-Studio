"""NC-SC-004: generation batch recovery — persist failure cause for resume."""
from alembic import op


revision = "nc_sc004_batch_recovery"
down_revision = "nc_fusion_account_tracking"


def upgrade():
    op.execute("ALTER TABLE generation_batches ADD COLUMN IF NOT EXISTS error TEXT")


def downgrade():
    op.execute("ALTER TABLE generation_batches DROP COLUMN IF EXISTS error")
