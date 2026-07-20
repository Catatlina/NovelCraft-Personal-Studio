"""Allow complete human review feedback in version history.

Revision ID: nc_versions_reason_text
Revises: nc_merge_commerce_head
"""

from alembic import op
import sqlalchemy as sa


revision = "nc_versions_reason_text"
down_revision = "nc_merge_commerce_head"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "versions",
        "reason",
        existing_type=sa.String(length=50),
        type_=sa.Text(),
        existing_nullable=False,
        existing_server_default="manual",
    )


def downgrade() -> None:
    op.alter_column(
        "versions",
        "reason",
        existing_type=sa.Text(),
        type_=sa.String(length=50),
        existing_nullable=False,
        existing_server_default="manual",
        postgresql_using="left(reason, 50)",
    )
