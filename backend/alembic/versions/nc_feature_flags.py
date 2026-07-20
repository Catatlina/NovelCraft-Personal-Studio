"""feature_flags table

Revision ID: nc_feature_flags
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa

revision = "nc_feature_flags"
down_revision = None
branch_labels = None


def upgrade():
    op.create_table(
        "feature_flags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(100), unique=True, nullable=False),
        sa.Column("value", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), default=""),
        sa.Column("active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    # Seed default flags
    op.execute("INSERT INTO feature_flags(key,value,description) VALUES('new_editor','false','新版编辑器')")
    op.execute("INSERT INTO feature_flags(key,value,description) VALUES('beta_ui','false','Beta UI')")
    op.execute("INSERT INTO feature_flags(key,value,description) VALUES('dark_mode','true','夜间模式默认')")


def downgrade():
    op.drop_table("feature_flags")
