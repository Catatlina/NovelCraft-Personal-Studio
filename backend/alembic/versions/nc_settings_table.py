"""NC-SETTINGS: Create settings key-value table."""
from alembic import op


revision = "nc_settings_table"
down_revision = "nc_ops_index_repair"


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key VARCHAR(255) PRIMARY KEY,
            value TEXT NOT NULL DEFAULT '',
            description TEXT DEFAULT '',
            updated_at TIMESTAMPTZ DEFAULT now()
        )
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS settings")
