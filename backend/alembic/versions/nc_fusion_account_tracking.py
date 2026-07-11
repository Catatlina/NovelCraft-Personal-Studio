"""Migration: account_trackings table for insprira clean-room account tracking."""
from alembic import op


revision = "nc_fusion_account_tracking"
down_revision = None

def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS account_trackings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID,
            platform VARCHAR(50) NOT NULL,
            account_id VARCHAR(255) NOT NULL,
            account_name VARCHAR(255),
            status VARCHAR(20) DEFAULT 'active',
            last_synced_at TIMESTAMPTZ,
            meta JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS published_posts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID,
            platform VARCHAR(50) NOT NULL,
            content_id UUID,
            title VARCHAR(500),
            body TEXT,
            status VARCHAR(20) DEFAULT 'draft',
            published_at TIMESTAMPTZ,
            meta JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
    """)

def downgrade():
    op.execute("DROP TABLE IF EXISTS published_posts; DROP TABLE IF EXISTS account_trackings;")
