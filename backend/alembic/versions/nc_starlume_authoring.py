"""Starlume AI human-led authoring control plane.

The migration is intentionally additive.  Existing ``contents``, ``versions``,
``knowledge_items``, ``model_routes`` and publishing tables remain the source
of truth; these tables only retain the new collaboration/session evidence that
cannot be represented safely in those legacy surfaces.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "nc_starlume_authoring"
down_revision: Union[str, None] = "nc_v11_disclosure_payoff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS authoring_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            novel_id UUID REFERENCES contents(id) ON DELETE CASCADE,
            content_id UUID REFERENCES contents(id) ON DELETE CASCADE,
            author_id UUID NOT NULL REFERENCES users(id),
            role_key VARCHAR(60) NOT NULL DEFAULT 'scene_expander',
            base_version_id UUID REFERENCES versions(id),
            status VARCHAR(24) NOT NULL DEFAULT 'active'
                CHECK (status IN ('active','closed','stale')),
            metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS authoring_sessions_content_idx
            ON authoring_sessions(content_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS authoring_sessions_author_idx
            ON authoring_sessions(author_id, updated_at DESC);

        CREATE TABLE IF NOT EXISTS authoring_messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id UUID NOT NULL REFERENCES authoring_sessions(id) ON DELETE CASCADE,
            sequence_no INTEGER NOT NULL,
            role VARCHAR(16) NOT NULL CHECK (role IN ('user','assistant','system','tool')),
            message_kind VARCHAR(32) NOT NULL DEFAULT 'chat',
            content TEXT NOT NULL,
            provider VARCHAR(50),
            model VARCHAR(120),
            ai_call_id UUID,
            candidate JSONB NOT NULL DEFAULT '{}',
            metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(session_id, sequence_no)
        );
        CREATE INDEX IF NOT EXISTS authoring_messages_session_idx
            ON authoring_messages(session_id, sequence_no);

        CREATE TABLE IF NOT EXISTS writing_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            novel_id UUID REFERENCES contents(id) ON DELETE CASCADE,
            content_id UUID REFERENCES contents(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id),
            event_type VARCHAR(32) NOT NULL
                CHECK (event_type IN ('manual_input','delete','paste','ai_accept','ai_reject','ai_revert','active_window','save')),
            source VARCHAR(24) NOT NULL DEFAULT 'editor',
            started_at TIMESTAMPTZ,
            ended_at TIMESTAMPTZ,
            duration_ms INTEGER NOT NULL DEFAULT 0,
            chars_added INTEGER NOT NULL DEFAULT 0,
            chars_removed INTEGER NOT NULL DEFAULT 0,
            payload JSONB NOT NULL DEFAULT '{}',
            client_event_id VARCHAR(100),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS writing_events_client_uq
            ON writing_events(user_id, client_event_id)
            WHERE client_event_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS writing_events_content_idx
            ON writing_events(content_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS authoring_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            novel_id UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            run_type VARCHAR(40) NOT NULL DEFAULT 'clean_three_chapters',
            status VARCHAR(24) NOT NULL DEFAULT 'planned'
                CHECK (status IN ('planned','cleaned','running','blocked','completed','failed')),
            clean_history_required BOOLEAN NOT NULL DEFAULT TRUE,
            active_chapters_before INTEGER NOT NULL DEFAULT 0,
            active_chapters_after INTEGER NOT NULL DEFAULT 0,
            target_chapters INTEGER NOT NULL DEFAULT 3,
            provider_evidence JSONB NOT NULL DEFAULT '{}',
            blind_reviews JSONB NOT NULL DEFAULT '[]',
            failure_code VARCHAR(80),
            failure_message TEXT,
            created_by UUID NOT NULL REFERENCES users(id),
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS authoring_runs_novel_idx
            ON authoring_runs(novel_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS publication_human_receipts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            variant_id UUID NOT NULL REFERENCES publication_variants(id) ON DELETE CASCADE,
            publish_record_id UUID REFERENCES publish_records(id),
            platform VARCHAR(50) NOT NULL,
            status VARCHAR(24) NOT NULL DEFAULT 'submitted'
                CHECK (status IN ('submitted','accepted','rejected','unknown')),
            external_url TEXT,
            external_id VARCHAR(300),
            receipt_text TEXT,
            submitted_by UUID NOT NULL REFERENCES users(id),
            submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            metadata JSONB NOT NULL DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS publication_receipts_variant_idx
            ON publication_human_receipts(variant_id, submitted_at DESC);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS publication_human_receipts;
        DROP TABLE IF EXISTS authoring_runs;
        DROP INDEX IF EXISTS writing_events_content_idx;
        DROP INDEX IF EXISTS writing_events_client_uq;
        DROP TABLE IF EXISTS writing_events;
        DROP INDEX IF EXISTS authoring_messages_session_idx;
        DROP TABLE IF EXISTS authoring_messages;
        DROP INDEX IF EXISTS authoring_sessions_author_idx;
        DROP INDEX IF EXISTS authoring_sessions_content_idx;
        DROP TABLE IF EXISTS authoring_sessions;
        """
    )
