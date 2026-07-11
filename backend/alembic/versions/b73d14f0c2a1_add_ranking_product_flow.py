"""add ranking product flow

Revision ID: b73d14f0c2a1
Revises: a42fd18be770
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b73d14f0c2a1"
down_revision: Union[str, None] = "a42fd18be770"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE ranking_sources (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            source_key VARCHAR(50) NOT NULL,
            display_name VARCHAR(100) NOT NULL,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            last_success_at TIMESTAMPTZ,
            last_error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(project_id, source_key)
        );
        CREATE TABLE ranking_snapshots (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            source_id UUID NOT NULL REFERENCES ranking_sources(id) ON DELETE CASCADE,
            status VARCHAR(20) NOT NULL,
            item_count INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX ranking_snapshots_project_captured_idx
            ON ranking_snapshots(project_id, captured_at DESC);
        CREATE TABLE ranking_items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            snapshot_id UUID NOT NULL REFERENCES ranking_snapshots(id) ON DELETE CASCADE,
            rank_no INTEGER NOT NULL,
            title VARCHAR(500) NOT NULL,
            author VARCHAR(200) NOT NULL DEFAULT '',
            category VARCHAR(100) NOT NULL DEFAULT '',
            source_url TEXT,
            metrics JSONB NOT NULL DEFAULT '{}',
            UNIQUE(snapshot_id, rank_no)
        );
        CREATE TABLE market_analyses (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            snapshot_id UUID NOT NULL REFERENCES ranking_snapshots(id) ON DELETE CASCADE,
            summary TEXT NOT NULL,
            signals JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE topic_candidates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            analysis_id UUID NOT NULL REFERENCES market_analyses(id) ON DELETE CASCADE,
            title VARCHAR(500) NOT NULL,
            premise TEXT NOT NULL,
            genre VARCHAR(100) NOT NULL DEFAULT '',
            market_score NUMERIC(5,2) NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'candidate',
            novel_id UUID REFERENCES contents(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)


def downgrade() -> None:
    op.execute("""
        DROP TABLE IF EXISTS topic_candidates;
        DROP TABLE IF EXISTS market_analyses;
        DROP TABLE IF EXISTS ranking_items;
        DROP TABLE IF EXISTS ranking_snapshots;
        DROP TABLE IF EXISTS ranking_sources;
    """)
