"""v6.1.2 schema phase F: relation arcs + outline versions

Adds:
- relation_arcs: tracks relationship stages between characters (§4.2)
- outline_versions: stores outline versions for replan history (§5.4)

Revision ID: f0a1b2c3d4e5
Revises: e9f5a6b7c8d9
Create Date: 2026-07-31 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f0a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = 'e9f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add relation_arcs and outline_versions tables."""
    # §4.2 relation arcs: tracks relationship evolution between characters
    op.execute("""
        CREATE TABLE IF NOT EXISTS relation_arcs (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            novel_id        UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            entity_a        VARCHAR(200) NOT NULL,
            entity_b        VARCHAR(200) NOT NULL,
            relation_type   VARCHAR(100) NOT NULL DEFAULT 'unknown',
            stage           VARCHAR(200) NOT NULL DEFAULT '',
            turning_points  JSONB NOT NULL DEFAULT '[]'::jsonb,
            last_chapter_seq INTEGER,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
            CONSTRAINT relation_arcs_entity_pair_uq
                UNIQUE (novel_id, entity_a, entity_b)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_relation_arcs_novel ON relation_arcs (novel_id);")

    # §5.4 outline versions: stores each replan as a versioned outline
    op.execute("""
        CREATE TABLE IF NOT EXISTS outline_versions (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            novel_id            UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            chapter_from        INTEGER NOT NULL,
            chapter_to          INTEGER NOT NULL,
            version             INTEGER NOT NULL DEFAULT 1,
            outline_json        JSONB NOT NULL,
            status              VARCHAR(20) NOT NULL DEFAULT 'active'
                                CHECK (status IN ('active','superseded','draft')),
            parent_version_id   UUID,
            rationale           TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted          BOOLEAN NOT NULL DEFAULT FALSE
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_outline_versions_novel ON outline_versions (novel_id, status);")


def downgrade() -> None:
    """Drop the added tables."""
    op.execute("DROP TABLE IF EXISTS outline_versions;")
    op.execute("DROP TABLE IF EXISTS relation_arcs;")
