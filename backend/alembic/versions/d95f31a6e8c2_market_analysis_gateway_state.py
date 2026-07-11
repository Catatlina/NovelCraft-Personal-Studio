"""market analysis gateway state

Revision ID: d95f31a6e8c2
Revises: c84e2a91d5b7
"""
from typing import Sequence, Union

from alembic import op

revision: str = "d95f31a6e8c2"
down_revision: Union[str, None] = "c84e2a91d5b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE market_analyses ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT 'legacy_rules_only';
        ALTER TABLE market_analyses ADD COLUMN analysis_mode VARCHAR(20) NOT NULL DEFAULT 'rules';
        ALTER TABLE market_analyses ADD COLUMN prompt_name VARCHAR(200);
        ALTER TABLE market_analyses ADD COLUMN prompt_version VARCHAR(30);
        ALTER TABLE market_analyses ADD COLUMN input_hash VARCHAR(64);
        ALTER TABLE market_analyses ADD COLUMN error TEXT;
        ALTER TABLE market_analyses ADD COLUMN completed_at TIMESTAMPTZ;
        ALTER TABLE topic_candidates ADD COLUMN target_audience TEXT NOT NULL DEFAULT '';
        ALTER TABLE topic_candidates ADD COLUMN differentiators JSONB NOT NULL DEFAULT '[]';
        ALTER TABLE topic_candidates ADD COLUMN market_evidence JSONB NOT NULL DEFAULT '[]';
        ALTER TABLE topic_candidates ADD COLUMN risk TEXT NOT NULL DEFAULT '';
        ALTER TABLE topic_candidates ADD COLUMN originality_notes TEXT NOT NULL DEFAULT '';
        CREATE INDEX market_analyses_snapshot_status_idx ON market_analyses(snapshot_id, status, created_at DESC);
    """)


def downgrade() -> None:
    op.execute("""
        DROP INDEX IF EXISTS market_analyses_snapshot_status_idx;
        ALTER TABLE topic_candidates DROP COLUMN IF EXISTS originality_notes;
        ALTER TABLE topic_candidates DROP COLUMN IF EXISTS risk;
        ALTER TABLE topic_candidates DROP COLUMN IF EXISTS market_evidence;
        ALTER TABLE topic_candidates DROP COLUMN IF EXISTS differentiators;
        ALTER TABLE topic_candidates DROP COLUMN IF EXISTS target_audience;
        ALTER TABLE market_analyses DROP COLUMN IF EXISTS completed_at;
        ALTER TABLE market_analyses DROP COLUMN IF EXISTS error;
        ALTER TABLE market_analyses DROP COLUMN IF EXISTS input_hash;
        ALTER TABLE market_analyses DROP COLUMN IF EXISTS prompt_version;
        ALTER TABLE market_analyses DROP COLUMN IF EXISTS prompt_name;
        ALTER TABLE market_analyses DROP COLUMN IF EXISTS analysis_mode;
        ALTER TABLE market_analyses DROP COLUMN IF EXISTS status;
    """)
