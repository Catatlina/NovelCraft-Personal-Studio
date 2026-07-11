"""ranking capture provenance and metadata validation

Revision ID: e16a42c731d9
Revises: d95f31a6e8c2
"""
from typing import Sequence, Union

from alembic import op

revision: str = "e16a42c731d9"
down_revision: Union[str, None] = "d95f31a6e8c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE ranking_snapshots ADD COLUMN capture_status VARCHAR(30);
        UPDATE ranking_snapshots SET capture_status=CASE WHEN status='failed' THEN 'failed' ELSE 'succeeded' END;
        ALTER TABLE ranking_snapshots ALTER COLUMN capture_status SET DEFAULT 'succeeded';
        ALTER TABLE ranking_snapshots ALTER COLUMN capture_status SET NOT NULL;
        ALTER TABLE ranking_snapshots ADD CONSTRAINT ranking_snapshots_capture_status_check
            CHECK (capture_status IN ('succeeded','partial','needs_review','ocr_required','user_action_required','failed'));
        ALTER TABLE ranking_snapshots ADD COLUMN collector VARCHAR(40) NOT NULL DEFAULT 'unknown';
        ALTER TABLE ranking_snapshots ADD COLUMN confidence NUMERIC(4,3);
        ALTER TABLE ranking_snapshots ADD CONSTRAINT ranking_snapshots_confidence_check
            CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1));
        ALTER TABLE ranking_snapshots ADD COLUMN evidence JSONB NOT NULL DEFAULT '{}';
        ALTER TABLE ranking_snapshots ADD COLUMN validation_summary JSONB NOT NULL DEFAULT '{}';

        ALTER TABLE ranking_items ADD COLUMN metadata_status VARCHAR(24) NOT NULL DEFAULT 'unvalidated';
        ALTER TABLE ranking_items ADD COLUMN metadata_checked_at TIMESTAMPTZ;
        ALTER TABLE ranking_items ADD CONSTRAINT ranking_items_metadata_status_check
            CHECK (metadata_status IN ('unvalidated','confirmed','partial_match','ambiguous','conflict','not_found','unavailable'));
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE ranking_items DROP CONSTRAINT IF EXISTS ranking_items_metadata_status_check;
        ALTER TABLE ranking_items DROP COLUMN IF EXISTS metadata_checked_at;
        ALTER TABLE ranking_items DROP COLUMN IF EXISTS metadata_status;
        ALTER TABLE ranking_snapshots DROP COLUMN IF EXISTS validation_summary;
        ALTER TABLE ranking_snapshots DROP COLUMN IF EXISTS evidence;
        ALTER TABLE ranking_snapshots DROP CONSTRAINT IF EXISTS ranking_snapshots_confidence_check;
        ALTER TABLE ranking_snapshots DROP COLUMN IF EXISTS confidence;
        ALTER TABLE ranking_snapshots DROP COLUMN IF EXISTS collector;
        ALTER TABLE ranking_snapshots DROP CONSTRAINT IF EXISTS ranking_snapshots_capture_status_check;
        ALTER TABLE ranking_snapshots DROP COLUMN IF EXISTS capture_status;
    """)
