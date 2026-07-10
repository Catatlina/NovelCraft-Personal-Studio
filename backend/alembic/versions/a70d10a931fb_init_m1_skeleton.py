"""init_m1_skeleton

Revision ID: a70d10a931fb
Revises: 
Create Date: 2026-07-10

M1 骨架表初始化：26 张表一次性建齐。
使用原始 SQL DDL（非 SQLAlchemy ORM），避免 UUID 类型兼容问题。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a70d10a931fb'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── L0 ──
    op.execute("""
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            display_name VARCHAR(100) NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE
        );
        COMMENT ON TABLE users IS '用户表';
    """)

    # ── L1 ──
    op.execute("""
        CREATE TABLE projects (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(200) NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            owner_id UUID NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE
        );
        COMMENT ON TABLE projects IS '项目表';
    """)

    # ── L2 ──
    op.execute("""
        CREATE TABLE project_members (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id),
            user_id UUID NOT NULL REFERENCES users(id),
            role VARCHAR(20) NOT NULL DEFAULT 'viewer',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(project_id, user_id)
        );
        COMMENT ON TABLE project_members IS '项目成员，角色: owner/editor/viewer';

        CREATE TABLE platform_accounts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            platform VARCHAR(50) NOT NULL,
            account_name VARCHAR(200),
            credentials_encrypted TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE
        );
        COMMENT ON TABLE platform_accounts IS '发布平台账号，凭据 Fernet 加密';
    """)

    # ── L3 ──
    op.execute("""
        CREATE TABLE contents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id),
            parent_id UUID REFERENCES contents(id),
            type VARCHAR(50) NOT NULL,
            title VARCHAR(500) NOT NULL,
            body JSONB NOT NULL DEFAULT '{}',
            meta JSONB NOT NULL DEFAULT '{}',
            status VARCHAR(30) NOT NULL DEFAULT 'draft',
            owner_id UUID REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE
        );
        CREATE INDEX contents_project_id_idx ON contents(project_id);
        CREATE INDEX contents_parent_id_idx ON contents(parent_id);
        CREATE INDEX contents_type_idx ON contents(type);
        COMMENT ON TABLE contents IS '统一内容模型 C1';

        CREATE TABLE knowledge_items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            scope VARCHAR(20) NOT NULL DEFAULT 'project',
            project_id UUID REFERENCES projects(id),
            content_id UUID REFERENCES contents(id),
            kind VARCHAR(50) NOT NULL,
            title VARCHAR(500) NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            meta JSONB NOT NULL DEFAULT '{}',
            source_url TEXT,
            file_ref VARCHAR(500),
            version_head UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE
        );
        CREATE INDEX knowledge_items_project_kind_idx ON knowledge_items(project_id, kind);
        COMMENT ON TABLE knowledge_items IS 'Knowledge Hub C4';
    """)

    # ── L4 ──
    op.execute("""
        CREATE TABLE derivations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_content_id UUID NOT NULL REFERENCES contents(id),
            derived_content_id UUID NOT NULL REFERENCES contents(id),
            workflow_run_id UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(source_content_id, derived_content_id)
        );
        COMMENT ON TABLE derivations IS '内容复用血缘';

        CREATE TABLE versions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            entity_type VARCHAR(50) NOT NULL,
            entity_id UUID NOT NULL,
            version_no INTEGER NOT NULL DEFAULT 1,
            parent_version_id UUID REFERENCES versions(id),
            label VARCHAR(80) NOT NULL DEFAULT 'auto_save',
            snapshot JSONB NOT NULL,
            reason VARCHAR(50) NOT NULL DEFAULT 'manual',
            author_id UUID REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX versions_entity_idx ON versions(entity_type, entity_id);
        CREATE INDEX versions_parent_idx ON versions(parent_version_id);
        COMMENT ON TABLE versions IS '通用版本系统 C5';

        CREATE EXTENSION IF NOT EXISTS vector;
        CREATE TABLE knowledge_vectors (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            item_id UUID NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
            chunk_no INTEGER NOT NULL,
            embedding vector(1536),
            chunk_text TEXT NOT NULL
        );
        COMMENT ON TABLE knowledge_vectors IS 'pgvector 向量索引';

        CREATE TABLE prompts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(200) NOT NULL,
            version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
            model VARCHAR(100) NOT NULL DEFAULT '*',
            template TEXT NOT NULL,
            output_schema JSONB,
            variables JSONB,
            golden_cases JSONB NOT NULL DEFAULT '[]',
            changelog TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            deprecated BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(name, version, model)
        );
        COMMENT ON TABLE prompts IS 'Prompt 库';

        CREATE TABLE model_routes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            task_type VARCHAR(100) NOT NULL UNIQUE,
            provider VARCHAR(50) NOT NULL DEFAULT 'mock',
            model VARCHAR(100) NOT NULL DEFAULT 'mock-deepseek-chat',
            params JSONB NOT NULL DEFAULT '{}',
            fallback_json JSONB NOT NULL DEFAULT '[]',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        COMMENT ON TABLE model_routes IS '模型路由配置';

        CREATE TABLE workflows (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(200) NOT NULL,
            is_preset BOOLEAN NOT NULL DEFAULT FALSE,
            definition JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE
        );
        COMMENT ON TABLE workflows IS '工作流定义 C2';
    """)

    # ── L5 ──
    op.execute("""
        CREATE TABLE schedules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workflow_id UUID NOT NULL REFERENCES workflows(id),
            cron VARCHAR(100) NOT NULL,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        COMMENT ON TABLE schedules IS '定时调度，Celery beat 读取';

        CREATE TABLE sensitive_words (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            word VARCHAR(200) NOT NULL UNIQUE,
            category VARCHAR(50),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        COMMENT ON TABLE sensitive_words IS '敏感词表';

        CREATE TABLE entity_states (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chapter_id UUID NOT NULL REFERENCES contents(id),
            entity_type VARCHAR(50) NOT NULL,
            entity_name VARCHAR(200) NOT NULL,
            location VARCHAR(500),
            relationships JSONB DEFAULT '{}',
            possessions JSONB DEFAULT '[]',
            known_info JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX entity_states_chapter_idx ON entity_states(chapter_id);
        COMMENT ON TABLE entity_states IS '实体状态表 C6';

        CREATE TABLE foreshadowings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chapter_id UUID NOT NULL REFERENCES contents(id),
            content TEXT NOT NULL,
            planned_resolve_chapter INTEGER,
            resolve_chapter_id UUID REFERENCES contents(id),
            status VARCHAR(30) NOT NULL DEFAULT 'planted',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        COMMENT ON TABLE foreshadowings IS '伏笔系统 C6';

        CREATE TABLE timeline_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chapter_id UUID NOT NULL REFERENCES contents(id),
            event_text TEXT NOT NULL,
            event_order INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        COMMENT ON TABLE timeline_events IS '时间线事件 C6';

        CREATE TABLE arcs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            novel_id UUID NOT NULL REFERENCES contents(id),
            character_name VARCHAR(200) NOT NULL,
            stage VARCHAR(100),
            goal TEXT,
            status VARCHAR(50) DEFAULT 'in_progress',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        COMMENT ON TABLE arcs IS '人物弧线 C6';
    """)

    # ── L6 ──
    op.execute("""
        CREATE TABLE workflow_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workflow_id UUID REFERENCES workflows(id),
            project_id UUID NOT NULL REFERENCES projects(id),
            novel_id UUID REFERENCES contents(id),
            workflow_key VARCHAR(100) NOT NULL DEFAULT 'bootstrap',
            status VARCHAR(30) NOT NULL DEFAULT 'pending',
            current_node_key VARCHAR(100),
            context JSONB NOT NULL DEFAULT '{}',
            schedule_id UUID REFERENCES schedules(id),
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX workflow_runs_project_idx ON workflow_runs(project_id);
        CREATE INDEX workflow_runs_status_idx ON workflow_runs(status);
        COMMENT ON TABLE workflow_runs IS '工作流运行实例 C2';

        CREATE TABLE reviews (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            content_id UUID NOT NULL REFERENCES contents(id),
            workflow_run_id UUID REFERENCES workflow_runs(id),
            score INTEGER,
            dimensions JSONB,
            issues JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        COMMENT ON TABLE reviews IS '审核记录 C6';
    """)

    # ── L7 ──
    op.execute("""
        CREATE TABLE run_nodes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id UUID NOT NULL REFERENCES workflow_runs(id),
            node_key VARCHAR(100) NOT NULL,
            kind VARCHAR(30) NOT NULL,
            agent VARCHAR(100),
            title VARCHAR(200) NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'pending',
            attempt INTEGER NOT NULL DEFAULT 0,
            input JSONB,
            output JSONB NOT NULL DEFAULT '{}',
            error TEXT,
            ai_call_ids UUID[] DEFAULT '{}',
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            UNIQUE(run_id, node_key)
        );
        CREATE INDEX run_nodes_run_idx ON run_nodes(run_id);
        COMMENT ON TABLE run_nodes IS '节点执行记录 C2';
    """)

    # ── L8 ──
    op.execute("""
        CREATE TABLE ai_calls (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id UUID REFERENCES workflow_runs(id),
            node_key VARCHAR(100),
            provider VARCHAR(50) NOT NULL,
            model VARCHAR(100) NOT NULL,
            prompt_name VARCHAR(200) NOT NULL,
            task_type VARCHAR(100) NOT NULL,
            input JSONB NOT NULL,
            output JSONB NOT NULL,
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            cost_cny NUMERIC(10,6) NOT NULL DEFAULT 0,
            latency_ms INTEGER NOT NULL DEFAULT 0,
            status VARCHAR(30) NOT NULL,
            error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX ai_calls_run_idx ON ai_calls(run_id);
        CREATE INDEX ai_calls_created_idx ON ai_calls(created_at);
        COMMENT ON TABLE ai_calls IS 'AI调用全追踪 C8';

        CREATE TABLE budgets (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id),
            scope VARCHAR(50) NOT NULL,
            limit_cny NUMERIC(10,4) NOT NULL DEFAULT 2.0,
            spent_cny NUMERIC(10,4) NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(project_id, scope)
        );
        COMMENT ON TABLE budgets IS '预算管理 C3';
    """)

    # ── L9 ──
    op.execute("""
        CREATE TABLE publish_records (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            content_id UUID NOT NULL REFERENCES contents(id),
            platform_account_id UUID REFERENCES platform_accounts(id),
            platform VARCHAR(50) NOT NULL,
            mode VARCHAR(30) NOT NULL DEFAULT 'manual',
            status VARCHAR(30) NOT NULL DEFAULT 'pending',
            published_url TEXT,
            scheduled_at TIMESTAMPTZ,
            published_at TIMESTAMPTZ,
            error TEXT,
            risk_notice TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        COMMENT ON TABLE publish_records IS '发布记录 C7';

        CREATE TABLE metrics (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            publish_record_id UUID REFERENCES publish_records(id),
            content_id UUID NOT NULL REFERENCES contents(id),
            platform VARCHAR(50) NOT NULL,
            date DATE NOT NULL,
            views INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            favorites INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            revenue NUMERIC(12,2) DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(content_id, platform, date)
        );
        COMMENT ON TABLE metrics IS '数据回流 C7';

        CREATE TABLE audit_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID REFERENCES users(id),
            action VARCHAR(100) NOT NULL,
            entity_type VARCHAR(50),
            entity_id UUID,
            details JSONB,
            ip_address VARCHAR(45),
            user_agent TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX audit_logs_user_idx ON audit_logs(user_id);
        CREATE INDEX audit_logs_created_idx ON audit_logs(created_at);
        COMMENT ON TABLE audit_logs IS '审计日志 C8';
    """)


def downgrade() -> None:
    tables = [
        'audit_logs', 'metrics', 'publish_records',
        'budgets', 'ai_calls',
        'run_nodes', 'workflow_runs',
        'reviews', 'arcs', 'timeline_events', 'foreshadowings', 'entity_states',
        'sensitive_words', 'schedules',
        'workflows', 'model_routes', 'prompts',
        'knowledge_vectors', 'versions', 'derivations',
        'knowledge_items', 'contents',
        'platform_accounts', 'project_members',
        'projects', 'users',
    ]
    for table in tables:
        op.execute(f'DROP TABLE IF EXISTS {table} CASCADE')
    op.execute('DROP EXTENSION IF EXISTS vector')
