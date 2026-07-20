"""create agents & agent_runs tables

Revision ID: nc_v1_agents
Create Date: 2026-07-20
"""
from alembic import op

revision = "nc_v1_agents"
down_revision = "nc_v1_skills"


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id VARCHAR(36) PRIMARY KEY,
            slug VARCHAR(100) UNIQUE NOT NULL,
            name VARCHAR(200) NOT NULL,
            version VARCHAR(20) DEFAULT '1.0.0',
            category VARCHAR(50) NOT NULL,
            description TEXT,
            goal JSONB NOT NULL DEFAULT '{}',
            workflow JSONB NOT NULL DEFAULT '{}',
            memory_config JSONB DEFAULT '{}',
            model_preference JSONB DEFAULT '{}',
            trigger_type VARCHAR(20) DEFAULT 'manual',
            trigger_config JSONB DEFAULT '{}',
            is_builtin BOOLEAN DEFAULT FALSE,
            status VARCHAR(20) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS agent_runs (
            id VARCHAR(36) PRIMARY KEY,
            agent_id VARCHAR(36) NOT NULL REFERENCES agents(id),
            user_id VARCHAR(36) NOT NULL,
            project_id VARCHAR(36),
            status VARCHAR(20) DEFAULT 'pending',
            current_step VARCHAR(100),
            progress DECIMAL(5,2) DEFAULT 0,
            inputs JSONB DEFAULT '{}',
            outputs JSONB DEFAULT '{}',
            error_message TEXT,
            started_at TIMESTAMP DEFAULT NOW(),
            completed_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS agent_run_steps (
            id VARCHAR(36) PRIMARY KEY,
            run_id VARCHAR(36) NOT NULL REFERENCES agent_runs(id),
            step_id VARCHAR(100) NOT NULL,
            step_name VARCHAR(200),
            skill_id VARCHAR(36),
            status VARCHAR(20) DEFAULT 'pending',
            inputs JSONB DEFAULT '{}',
            outputs JSONB DEFAULT '{}',
            retry_count INTEGER DEFAULT 0,
            started_at TIMESTAMP,
            completed_at TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_agents_slug ON agents(slug);
        CREATE INDEX IF NOT EXISTS idx_agent_runs_user ON agent_runs(user_id);
        CREATE INDEX IF NOT EXISTS idx_agent_runs_agent ON agent_runs(agent_id);
        CREATE INDEX IF NOT EXISTS idx_agent_run_steps_run ON agent_run_steps(run_id);
    """)


def downgrade():
    op.execute("""
        DROP TABLE IF EXISTS agent_run_steps;
        DROP TABLE IF EXISTS agent_runs;
        DROP TABLE IF EXISTS agents;
    """)
