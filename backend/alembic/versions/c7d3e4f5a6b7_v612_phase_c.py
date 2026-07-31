"""v6.1.2 schema phase C: long-novel stability & pollution guard

Revision ID: c7d3e4f5a6b7
Revises: b7c2d3e4f5a6
Create Date: 2026-07-31 14:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d3e4f5a6b7'
down_revision: Union[str, Sequence[str], None] = 'b7c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema (Phase C: million-word stability)."""
    # 3.2 world_state
    op.execute("""
        CREATE TABLE IF NOT EXISTS world_state (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            novel_id    UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            chapter_seq INTEGER NOT NULL,
            state_version INTEGER NOT NULL DEFAULT 1,
            snapshot    JSONB NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted  BOOLEAN NOT NULL DEFAULT FALSE
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_world_state_novel_seq ON world_state (novel_id, chapter_seq);")

    # 3.3 plot_threads
    op.execute("""
        CREATE TABLE IF NOT EXISTS plot_threads (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            novel_id        UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            name            VARCHAR(200) NOT NULL,
            status          VARCHAR(20) NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active','paused','resolved','abandoned')),
            importance      INTEGER NOT NULL DEFAULT 5
                            CHECK (importance BETWEEN 1 AND 10),
            progress        TEXT,
            last_chapter_seq INTEGER,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted      BOOLEAN NOT NULL DEFAULT FALSE
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_plot_threads_novel_status ON plot_threads (novel_id, status);")

    # 3.9 chapter_snapshot
    op.execute("""
        CREATE TABLE IF NOT EXISTS chapter_snapshot (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id        UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            content_id        UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            chapter_seq       INTEGER NOT NULL,
            content_hash      VARCHAR(64),
            story_state_hash  VARCHAR(64),
            entity_state_hash VARCHAR(64),
            outline_version   INTEGER,
            prompt_version    VARCHAR(64),
            model             VARCHAR(100),
            generation_params JSONB,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chapter_snapshot_content_uq UNIQUE (content_id)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_chapter_snapshot_content ON chapter_snapshot (content_id);")

    # 3.8 chapter_audit_report
    op.execute("""
        CREATE TABLE IF NOT EXISTS chapter_audit_report (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id        UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            novel_id          UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            at_chapter        INTEGER NOT NULL,
            character_changes JSONB NOT NULL DEFAULT '[]'::jsonb,
            wealth_changes    JSONB NOT NULL DEFAULT '[]'::jsonb,
            capability_changes JSONB NOT NULL DEFAULT '[]'::jsonb,
            foreshadowing_status JSONB NOT NULL DEFAULT '{}'::jsonb,
            style_drift       JSONB NOT NULL DEFAULT '{}'::jsonb,
            generated_by      VARCHAR(20) NOT NULL DEFAULT 'rule' CHECK (generated_by IN ('rule')),
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted        BOOLEAN NOT NULL DEFAULT FALSE,
            CONSTRAINT chapter_audit_report_at_uq UNIQUE (novel_id, at_chapter)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_chapter_audit_report_novel_at ON chapter_audit_report (novel_id, at_chapter);")

    # 3.7 chapter_emotion_state
    op.execute("""
        CREATE TABLE IF NOT EXISTS chapter_emotion_state (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            content_id  UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            chapter_seq INTEGER NOT NULL,
            state       VARCHAR(20) NOT NULL
                        CHECK (state IN ('压抑','冲突','爆发','爽','缓冲','期待')),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted  BOOLEAN NOT NULL DEFAULT FALSE,
            CONSTRAINT chapter_emotion_state_content_uq UNIQUE (content_id)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_chapter_emotion_state_content ON chapter_emotion_state (content_id);")


def downgrade() -> None:
    """Downgrade schema (reverse of Phase C)."""
    op.execute("DROP TABLE IF EXISTS chapter_emotion_state;")
    op.execute("DROP TABLE IF EXISTS chapter_audit_report;")
    op.execute("DROP TABLE IF EXISTS chapter_snapshot;")
    op.execute("DROP TABLE IF EXISTS plot_threads;")
    op.execute("DROP TABLE IF EXISTS world_state;")
