"""ranking health and dedup

Revision ID: c84e2a91d5b7
Revises: b73d14f0c2a1
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c84e2a91d5b7"
down_revision: Union[str, None] = "b73d14f0c2a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE ranking_sources ADD COLUMN last_attempt_at TIMESTAMPTZ;
        ALTER TABLE ranking_sources ADD COLUMN consecutive_failures INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE ranking_snapshots ADD COLUMN retry_of_snapshot_id UUID REFERENCES ranking_snapshots(id) ON DELETE SET NULL;
        ALTER TABLE ranking_items ADD COLUMN fetched_at TIMESTAMPTZ NOT NULL DEFAULT now();
        ALTER TABLE ranking_items ADD COLUMN external_id VARCHAR(100);
        ALTER TABLE ranking_items ADD COLUMN dedupe_key VARCHAR(64);
        UPDATE ranking_items SET dedupe_key = md5(snapshot_id::text || ':' || rank_no::text) WHERE dedupe_key IS NULL;
        ALTER TABLE ranking_items ALTER COLUMN dedupe_key SET NOT NULL;
        ALTER TABLE ranking_items DROP CONSTRAINT ranking_items_snapshot_id_rank_no_key;
        ALTER TABLE ranking_items ADD CONSTRAINT ranking_items_snapshot_dedupe_key_key UNIQUE(snapshot_id, dedupe_key);
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE ranking_items DROP CONSTRAINT IF EXISTS ranking_items_snapshot_dedupe_key_key;
        ALTER TABLE ranking_items ADD CONSTRAINT ranking_items_snapshot_id_rank_no_key UNIQUE(snapshot_id, rank_no);
        ALTER TABLE ranking_items DROP COLUMN IF EXISTS dedupe_key;
        ALTER TABLE ranking_items DROP COLUMN IF EXISTS external_id;
        ALTER TABLE ranking_items DROP COLUMN IF EXISTS fetched_at;
        ALTER TABLE ranking_snapshots DROP COLUMN IF EXISTS retry_of_snapshot_id;
        ALTER TABLE ranking_sources DROP COLUMN IF EXISTS consecutive_failures;
        ALTER TABLE ranking_sources DROP COLUMN IF EXISTS last_attempt_at;
    """)
