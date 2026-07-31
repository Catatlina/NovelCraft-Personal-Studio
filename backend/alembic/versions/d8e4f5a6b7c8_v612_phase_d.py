"""v6.1.2 schema phase D: capability tree + character arc on entity_states

Per architecture_v6.1 §4.2 (character_arc) and §4.3 (capability_tree),
both hang off the entity sub-structure rather than living in separate tables.
Purely additive ADD COLUMN IF NOT EXISTS - no data loss, safe to re-run.

Revision ID: d8e4f5a6b7c8
Revises: c7d3e4f5a6b7
Create Date: 2026-07-31 16:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8e4f5a6b7c8'
down_revision: Union[str, Sequence[str], None] = 'c7d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add capability_tree / character_arc to entity_states."""
    # 4.3 capability_tree: [{skill, level, acquired_chapter, evidence, limitations}]
    op.execute("""
        ALTER TABLE entity_states
        ADD COLUMN IF NOT EXISTS capability_tree JSONB NOT NULL DEFAULT '[]'::jsonb;
    """)
    # 4.2 character_arc: {initial_flaw, growth_goal, current_arc_stage, turning_points[]}
    op.execute("""
        ALTER TABLE entity_states
        ADD COLUMN IF NOT EXISTS character_arc JSONB NOT NULL DEFAULT '{}'::jsonb;
    """)


def downgrade() -> None:
    """Drop the added columns."""
    op.execute("ALTER TABLE entity_states DROP COLUMN IF EXISTS character_arc;")
    op.execute("ALTER TABLE entity_states DROP COLUMN IF EXISTS capability_tree;")
