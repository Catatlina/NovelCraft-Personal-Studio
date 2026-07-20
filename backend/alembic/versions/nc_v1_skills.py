"""create skills & skill_installations tables

Revision ID: nc_v1_skills
Create Date: 2026-07-20
"""
from alembic import op
import sqlalchemy as sa

revision = "nc_v1_skills"
down_revision = "nc_p2_hot_columns"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS skills (
            id VARCHAR(36) PRIMARY KEY,
            slug VARCHAR(100) UNIQUE NOT NULL,
            name VARCHAR(200) NOT NULL,
            version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
            category VARCHAR(50) NOT NULL,
            description TEXT,
            author VARCHAR(200) DEFAULT '星禾官方',
            icon VARCHAR(50),
            input_schema JSONB NOT NULL DEFAULT '{}',
            output_schema JSONB DEFAULT '{}',
            prompt_template VARCHAR(200),
            model_preference VARCHAR(50),
            estimated_tokens INTEGER DEFAULT 500,
            is_builtin BOOLEAN DEFAULT FALSE,
            is_public BOOLEAN DEFAULT FALSE,
            status VARCHAR(20) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS skill_installations (
            id VARCHAR(36) PRIMARY KEY,
            user_id VARCHAR(36) NOT NULL,
            skill_id VARCHAR(36) NOT NULL REFERENCES skills(id),
            status VARCHAR(20) DEFAULT 'active',
            installed_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(user_id, skill_id)
        );

        CREATE TABLE IF NOT EXISTS skill_executions (
            id VARCHAR(36) PRIMARY KEY,
            user_id VARCHAR(36) NOT NULL,
            skill_id VARCHAR(36) NOT NULL REFERENCES skills(id),
            inputs JSONB NOT NULL,
            outputs JSONB,
            ai_call_id VARCHAR(36),
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW(),
            completed_at TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category);
        CREATE INDEX IF NOT EXISTS idx_skills_slug ON skills(slug);
        CREATE INDEX IF NOT EXISTS idx_skill_installations_user ON skill_installations(user_id);
    """)


def downgrade():
    op.execute("""
        DROP TABLE IF EXISTS skill_executions;
        DROP TABLE IF EXISTS skill_installations;
        DROP TABLE IF EXISTS skills;
    """)
