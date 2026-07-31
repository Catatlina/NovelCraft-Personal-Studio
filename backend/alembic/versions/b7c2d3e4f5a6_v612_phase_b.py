"""v6.1.2 schema phase B: context assembly + summaries + cost log

Revision ID: b7c2d3e4f5a6
Revises: f6a1b2c3d4e5
Create Date: 2026-07-31 14:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'f6a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema (Phase B: context + summaries + cost)."""
    # 3.6 context_package
    op.execute("""
        CREATE TABLE IF NOT EXISTS context_package (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            content_id    UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            chapter_seq   INTEGER NOT NULL,
            context_hash  VARCHAR(64),
            included      JSONB NOT NULL DEFAULT '[]'::jsonb,
            token_budget  INTEGER NOT NULL,
            actual_tokens INTEGER,
            layers        JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted    BOOLEAN NOT NULL DEFAULT FALSE,
            CONSTRAINT context_package_content_uq UNIQUE (content_id)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_context_package_content_id ON context_package (content_id);")

    # 3.4 chapter_summaries
    op.execute("""
        CREATE TABLE IF NOT EXISTS chapter_summaries (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            content_id  UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            chapter_seq INTEGER NOT NULL,
            summary_type VARCHAR(20) NOT NULL DEFAULT 'chapter'
                        CHECK (summary_type IN ('chapter','compressed','manual')),
            generated_by VARCHAR(40) NOT NULL DEFAULT 'deepseek',
            summary     TEXT NOT NULL,
            key_chars   JSONB NOT NULL DEFAULT '[]'::jsonb,
            key_decisions TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted  BOOLEAN NOT NULL DEFAULT FALSE,
            CONSTRAINT chapter_summaries_content_uq UNIQUE (content_id)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_chapter_summaries_content_seq ON chapter_summaries (content_id, chapter_seq);")

    # 3.4 arc_summary
    op.execute("""
        CREATE TABLE IF NOT EXISTS arc_summary (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id   UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            novel_id     UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            volume_seq   INTEGER NOT NULL,
            volume_title TEXT,
            summary      TEXT NOT NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted   BOOLEAN NOT NULL DEFAULT FALSE,
            CONSTRAINT arc_summary_vol_uq UNIQUE (novel_id, volume_seq)
        );
    """)

    # 3.11 generation_cost_log
    op.execute("""
        CREATE TABLE IF NOT EXISTS generation_cost_log (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id       UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            content_id       UUID REFERENCES contents(id) ON DELETE CASCADE,
            chapter_seq      INTEGER,
            phase            VARCHAR(20) NOT NULL
                             CHECK (phase IN ('generate','review','repair','humanize','other')),
            task_type        VARCHAR(50),
            model            VARCHAR(100),
            task_id          VARCHAR(64),
            request_id       VARCHAR(64),
            success          BOOLEAN NOT NULL DEFAULT TRUE,
            error_message    TEXT,
            prompt_tokens    INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens     INTEGER NOT NULL DEFAULT 0,
            cost_cny         NUMERIC(10,4) NOT NULL DEFAULT 0,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_generation_cost_log_project_time ON generation_cost_log (project_id, created_at);")


def downgrade() -> None:
    """Downgrade schema (reverse of Phase B)."""
    op.execute("DROP TABLE IF EXISTS generation_cost_log;")
    op.execute("DROP TABLE IF EXISTS arc_summary;")
    op.execute("DROP TABLE IF EXISTS chapter_summaries;")
    op.execute("DROP TABLE IF EXISTS context_package;")
