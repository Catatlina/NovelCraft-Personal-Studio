"""add real_world_anchor / anachronism_check to timeline_events for V3 §10

Revision ID: nc_v3_timeline_anchor
Create Date: 2026-07-28
"""
from alembic import op
import sqlalchemy as sa

revision = "nc_v3_timeline_anchor"
down_revision = "nc_v3_entity_known_info"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE timeline_events
        ADD COLUMN IF NOT EXISTS real_world_anchor TEXT,
        ADD COLUMN IF NOT EXISTS anachronism_check TEXT;
    """)


def downgrade():
    op.execute("""
        ALTER TABLE timeline_events
        DROP COLUMN IF EXISTS real_world_anchor,
        DROP COLUMN IF EXISTS anachronism_check;
    """)
