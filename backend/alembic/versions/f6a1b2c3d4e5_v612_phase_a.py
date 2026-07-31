"""v6.1.2 schema phase A: single-chapter closed loop (book_config/book_status/style_cards/reviews/knowledge_items/entity_states/foreshadowings/repair_versions)

Revision ID: f6a1b2c3d4e5
Revises: b324f6c7a7f1
Create Date: 2026-07-31 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = 'b324f6c7a7f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema (Phase A: single-chapter closed loop)."""
    # --- ALTER existing tables (safe, idempotent ADD COLUMN IF NOT EXISTS) ---

    # 2.1 entity_states: grading + write-back confidence
    op.execute("""
        ALTER TABLE entity_states
          ADD COLUMN IF NOT EXISTS importance_level INTEGER NOT NULL DEFAULT 5
            CHECK (importance_level BETWEEN 1 AND 10);
    """)
    op.execute("""
        ALTER TABLE entity_states
          ADD COLUMN IF NOT EXISTS confidence NUMERIC(3,2) NOT NULL DEFAULT 1.0
            CHECK (confidence BETWEEN 0 AND 1);
    """)

    # 2.2 style_cards: author/genre split + drift confidence (Phase A code only reads author_card/genre_card)
    op.execute("""
        ALTER TABLE style_cards
          ADD COLUMN IF NOT EXISTS author_card JSONB NOT NULL DEFAULT '{}'::jsonb;
    """)
    op.execute("""
        ALTER TABLE style_cards
          ADD COLUMN IF NOT EXISTS genre_card JSONB NOT NULL DEFAULT '{}'::jsonb;
    """)
    op.execute("""
        ALTER TABLE style_cards
          ADD COLUMN IF NOT EXISTS style_change_confidence NUMERIC(3,2) NOT NULL DEFAULT 1.0
            CHECK (style_change_confidence BETWEEN 0 AND 1);
    """)
    op.execute("""
        ALTER TABLE style_cards
          ADD COLUMN IF NOT EXISTS relearn_at_chapter INTEGER;
    """)
    op.execute("""
        ALTER TABLE style_cards
          ADD COLUMN IF NOT EXISTS pending_signals JSONB NOT NULL DEFAULT '[]'::jsonb;
    """)
    op.execute("""
        ALTER TABLE style_cards
          ADD COLUMN IF NOT EXISTS approved_count INTEGER NOT NULL DEFAULT 0;
    """)
    op.execute("""
        ALTER TABLE style_cards
          ADD COLUMN IF NOT EXISTS apply_threshold INTEGER NOT NULL DEFAULT 3;
    """)

    # 2.3 reviews: 7-dim structured + fixed output format
    op.execute("""
        ALTER TABLE reviews
          ADD COLUMN IF NOT EXISTS score_7dim JSONB;
    """)
    op.execute("""
        ALTER TABLE reviews
          ADD COLUMN IF NOT EXISTS issues_structured BOOLEAN NOT NULL DEFAULT FALSE;
    """)
    op.execute("""
        ALTER TABLE reviews
          ADD COLUMN IF NOT EXISTS review_type VARCHAR(40);
    """)
    op.execute("""
        ALTER TABLE reviews
          ADD COLUMN IF NOT EXISTS model VARCHAR(100);
    """)
    op.execute("""
        ALTER TABLE reviews
          ADD COLUMN IF NOT EXISTS review_hash VARCHAR(64);
    """)

    # 2.4 knowledge_items: Story Bible hard/soft fact grading + confidence
    op.execute("""
        ALTER TABLE knowledge_items
          ADD COLUMN IF NOT EXISTS confidence NUMERIC(3,2) NOT NULL DEFAULT 1.0
            CHECK (confidence BETWEEN 0 AND 1);
    """)
    op.execute("""
        ALTER TABLE knowledge_items
          ADD COLUMN IF NOT EXISTS source_chapter INTEGER;
    """)
    op.execute("""
        ALTER TABLE knowledge_items
          ADD COLUMN IF NOT EXISTS approved BOOLEAN NOT NULL DEFAULT FALSE;
    """)
    op.execute("""
        ALTER TABLE knowledge_items
          ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id);
    """)
    op.execute("""
        ALTER TABLE knowledge_items
          ADD COLUMN IF NOT EXISTS fact_type VARCHAR(20) NOT NULL DEFAULT 'hard'
            CHECK (fact_type IN ('hard','soft'));
    """)

    # 2.5 foreshadowings: P1 enhancement, supports protected_elements
    op.execute("""
        ALTER TABLE foreshadowings
          ADD COLUMN IF NOT EXISTS expected_payoff_window INTEGER;
    """)
    op.execute("""
        ALTER TABLE foreshadowings
          ADD COLUMN IF NOT EXISTS reader_awareness VARCHAR(20) NOT NULL DEFAULT 'hidden'
            CHECK (reader_awareness IN ('hidden','suspected','known'));
    """)
    op.execute("""
        ALTER TABLE foreshadowings
          ADD COLUMN IF NOT EXISTS importance INTEGER NOT NULL DEFAULT 5
            CHECK (importance BETWEEN 1 AND 10);
    """)

    # --- CREATE new tables (Phase A) ---

    # 3.1 book_config (no status column; status managed by book_status)
    op.execute("""
        CREATE TABLE IF NOT EXISTS book_config (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            novel_id       UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            project_id     UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            genre          VARCHAR(60) NOT NULL DEFAULT '都市重生',
            domain_type    VARCHAR(40) NOT NULL DEFAULT 'urban_business'
                           CHECK (domain_type IN ('urban_business','xuanhuan_power','sci_fi_tech','general')),
            theme          TEXT,
            author_intent  JSONB NOT NULL DEFAULT '{}'::jsonb,
            immutable_rules JSONB NOT NULL DEFAULT '[]'::jsonb,
            target_words   INTEGER NOT NULL DEFAULT 1000000,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted     BOOLEAN NOT NULL DEFAULT FALSE,
            CONSTRAINT book_config_novel_uq UNIQUE (novel_id)
        );
    """)

    # 3.12 book_status (multi-book state machine, append-only)
    op.execute("""
        CREATE TABLE IF NOT EXISTS book_status (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            novel_id    UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            status      VARCHAR(20) NOT NULL
                        CHECK (status IN ('draft','worldbuilding','outline_confirmed','serializing','paused','completed','archived')),
            changed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            reason      TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    # 3.10 repair_versions (repair before/after + 2nd review + rollback + status machine)
    op.execute("""
        CREATE TABLE IF NOT EXISTS repair_versions (
            id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id         UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            content_id         UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            base_version_id    UUID,
            chapter_seq        INTEGER,
            repair_type        VARCHAR(20) NOT NULL DEFAULT 'local'
                               CHECK (repair_type IN ('local','section','chapter')),
            repair_scope       VARCHAR(20),
            repair_status      VARCHAR(20) NOT NULL DEFAULT 'pending'
                               CHECK (repair_status IN ('pending','reviewing','approved','applied','rollback','failed')),
            before_text        TEXT NOT NULL,
            after_text         TEXT NOT NULL,
            repair_prompt      TEXT,
            second_review_score NUMERIC(4,2),
            second_review_issues JSONB,
            rolled_back        BOOLEAN NOT NULL DEFAULT FALSE,
            reason             TEXT,
            model              VARCHAR(100),
            created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)


def downgrade() -> None:
    """Downgrade schema (reverse of Phase A)."""
    # Drop new tables
    op.execute("DROP TABLE IF EXISTS repair_versions;")
    op.execute("DROP TABLE IF EXISTS book_status;")
    op.execute("DROP TABLE IF EXISTS book_config;")

    # Drop foreshadowings added columns
    op.execute("ALTER TABLE foreshadowings DROP COLUMN IF EXISTS importance;")
    op.execute("ALTER TABLE foreshadowings DROP COLUMN IF EXISTS reader_awareness;")
    op.execute("ALTER TABLE foreshadowings DROP COLUMN IF EXISTS expected_payoff_window;")

    # Drop reviews added columns
    op.execute("ALTER TABLE reviews DROP COLUMN IF EXISTS review_hash;")
    op.execute("ALTER TABLE reviews DROP COLUMN IF EXISTS model;")
    op.execute("ALTER TABLE reviews DROP COLUMN IF EXISTS review_type;")
    op.execute("ALTER TABLE reviews DROP COLUMN IF EXISTS issues_structured;")
    op.execute("ALTER TABLE reviews DROP COLUMN IF EXISTS score_7dim;")

    # Drop knowledge_items added columns
    op.execute("ALTER TABLE knowledge_items DROP COLUMN IF EXISTS fact_type;")
    op.execute("ALTER TABLE knowledge_items DROP COLUMN IF EXISTS created_by;")
    op.execute("ALTER TABLE knowledge_items DROP COLUMN IF EXISTS approved;")
    op.execute("ALTER TABLE knowledge_items DROP COLUMN IF EXISTS source_chapter;")
    op.execute("ALTER TABLE knowledge_items DROP COLUMN IF EXISTS confidence;")

    # Drop style_cards added columns
    op.execute("ALTER TABLE style_cards DROP COLUMN IF EXISTS apply_threshold;")
    op.execute("ALTER TABLE style_cards DROP COLUMN IF EXISTS approved_count;")
    op.execute("ALTER TABLE style_cards DROP COLUMN IF EXISTS pending_signals;")
    op.execute("ALTER TABLE style_cards DROP COLUMN IF EXISTS relearn_at_chapter;")
    op.execute("ALTER TABLE style_cards DROP COLUMN IF EXISTS style_change_confidence;")
    op.execute("ALTER TABLE style_cards DROP COLUMN IF EXISTS genre_card;")
    op.execute("ALTER TABLE style_cards DROP COLUMN IF EXISTS author_card;")

    # Drop entity_states added columns
    op.execute("ALTER TABLE entity_states DROP COLUMN IF EXISTS confidence;")
    op.execute("ALTER TABLE entity_states DROP COLUMN IF EXISTS importance_level;")
