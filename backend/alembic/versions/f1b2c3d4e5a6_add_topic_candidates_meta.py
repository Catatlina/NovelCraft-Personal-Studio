"""add meta jsonb column to topic_candidates

The bookmark/备选池 feature (POST /topics/{id}/bookmark, GET /topics/bookmarked,
and the frontend star toggle) all depend on topic_candidates.meta, but the column
was never created by the initial schema (b73d14f0c2a1) nor any later
migration (current applied head is f0a1b2c3d4e5). As a result every bookmark call 500'd with
`column "meta" does not exist`, so starred topics could never enter the 备选池.

Revision ID: f1b2c3d4e5a6
Revises: f0a1b2c3d4e5
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f1b2c3d4e5a6"
down_revision: Union[str, None] = "f0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE topic_candidates ADD COLUMN meta JSONB NOT NULL DEFAULT '{}'::jsonb;"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE topic_candidates DROP COLUMN IF EXISTS meta;")
