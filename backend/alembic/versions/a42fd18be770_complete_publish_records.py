"""Complete publish record storage used by workers and scheduling APIs.

Revision ID: a42fd18be770
Revises: f91a3c612de4
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a42fd18be770"
down_revision: Union[str, None] = "f91a3c612de4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE publish_records ADD COLUMN IF NOT EXISTS result JSONB NOT NULL DEFAULT '{}'")
    op.execute("ALTER TABLE publish_records ADD COLUMN IF NOT EXISTS meta JSONB NOT NULL DEFAULT '{}'")
    op.execute("ALTER TABLE publish_records ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now()")
    op.execute("CREATE INDEX IF NOT EXISTS publish_records_status_idx ON publish_records(status)")
    op.execute("CREATE INDEX IF NOT EXISTS publish_records_scheduled_idx ON publish_records(scheduled_at) WHERE scheduled_at IS NOT NULL")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS publish_records_scheduled_idx")
    op.execute("DROP INDEX IF EXISTS publish_records_status_idx")
    op.execute("ALTER TABLE publish_records DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE publish_records DROP COLUMN IF EXISTS meta")
    op.execute("ALTER TABLE publish_records DROP COLUMN IF EXISTS result")
