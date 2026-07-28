"""create strategy table for V3 web-novel strategy library (MVP)

Revision ID: nc_v3_strategy
Create Date: 2026-07-28
"""
from alembic import op
import sqlalchemy as sa

revision = "nc_v3_strategy"
down_revision = "nc_merge_commerce_head"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS strategy (
            id VARCHAR(36) PRIMARY KEY,
            category VARCHAR(50) NOT NULL,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            stages JSONB NOT NULL DEFAULT '[]',
            applicable_conditions JSONB NOT NULL DEFAULT '[]',
            is_builtin BOOLEAN DEFAULT TRUE,
            status VARCHAR(20) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_strategy_category ON strategy(category);
        CREATE INDEX IF NOT EXISTS idx_strategy_builtin ON strategy(is_builtin);
    """)


def downgrade():
    op.execute("""
        DROP TABLE IF EXISTS strategy;
    """)
