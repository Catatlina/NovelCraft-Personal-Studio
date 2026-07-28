"""add known_info (5-layer cognition split) to entity_states for V3 §9

Revision ID: nc_v3_entity_known_info
Create Date: 2026-07-28
"""
from alembic import op
import sqlalchemy as sa

revision = "nc_v3_entity_known_info"
down_revision = "nc_v3_strategy"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE entity_states
        ADD COLUMN IF NOT EXISTS known_info JSONB NOT NULL DEFAULT '{}'::jsonb;
    """)


def downgrade():
    op.execute("""
        ALTER TABLE entity_states DROP COLUMN IF EXISTS known_info;
    """)
