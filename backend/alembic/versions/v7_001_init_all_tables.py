"""v7_001_init_all_tables

V7 Alpha 初始化：18 张表一次性建齐。
使用原始 SQL DDL（非 SQLAlchemy ORM），与现有 migration 风格保持一致。

Revision ID: v7_001_init
Revises: a70d10a931fb
Create Date: 2026-08-01
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'v7_001_init'
down_revision: Union[str, None] = 'a70d10a931fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 001: v7_story_versions
    op.execute("""
        CREATE TABLE v7_story_versions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            novel_id UUID NOT NULL,
            version_number INTEGER NOT NULL,
            version_type VARCHAR(50) NOT NULL,
            description TEXT,
            snapshot_data JSONB NOT NULL DEFAULT '{}',
            parent_version_id UUID REFERENCES v7_story_versions(id),
            branch_name VARCHAR(100),
            tag_name VARCHAR(100),
            created_by VARCHAR(50) NOT NULL DEFAULT 'system',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX v7_story_versions_novel_id_idx ON v7_story_versions(novel_id);
        CREATE INDEX v7_story_versions_version_number_idx ON v7_story_versions(version_number);
        COMMENT ON TABLE v7_story_versions IS 'V7 故事版本控制';
    """)

    # 002: v7_brain_snapshots
    op.execute("""
        CREATE TABLE v7_brain_snapshots (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            novel_id UUID NOT NULL,
            version_id UUID REFERENCES v7_story_versions(id),
            snapshot_type VARCHAR(50) NOT NULL,
            state_data JSONB NOT NULL DEFAULT '{}',
            description TEXT,
            size_bytes INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX v7_brain_snapshots_novel_id_idx ON v7_brain_snapshots(novel_id);
        CREATE INDEX v7_brain_snapshots_version_id_idx ON v7_brain_snapshots(version_id);
        COMMENT ON TABLE v7_brain_snapshots IS 'V7 Brain 状态快照';
    """)

    # 003: v7_story_states
    op.execute("""
        CREATE TABLE v7_story_states (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            novel_id UUID NOT NULL,
            state_type VARCHAR(50) NOT NULL,
            state_key VARCHAR(200) NOT NULL,
            state_value JSONB NOT NULL DEFAULT '{}',
            confidence FLOAT NOT NULL DEFAULT 0.9,
            confidence_reason TEXT,
            source VARCHAR(50) NOT NULL DEFAULT 'ai_extracted',
            source_run_id UUID,
            version INTEGER NOT NULL DEFAULT 1,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            is_pending_review BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX v7_story_states_novel_id_idx ON v7_story_states(novel_id);
        CREATE INDEX v7_story_states_type_key_idx ON v7_story_states(state_type, state_key);
        CREATE INDEX v7_story_states_confidence_idx ON v7_story_states(confidence);
        COMMENT ON TABLE v7_story_states IS 'V7 故事状态 + 置信度';
    """)

    # 004: v7_state_changes
    op.execute("""
        CREATE TABLE v7_state_changes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            novel_id UUID NOT NULL,
            state_id UUID REFERENCES v7_story_states(id),
            change_type VARCHAR(50) NOT NULL,
            state_type VARCHAR(50) NOT NULL,
            state_key VARCHAR(200) NOT NULL,
            old_value JSONB,
            new_value JSONB,
            old_confidence FLOAT,
            new_confidence FLOAT,
            reason TEXT,
            source VARCHAR(50) NOT NULL,
            source_run_id UUID,
            version_before INTEGER,
            version_after INTEGER,
            snapshot_id UUID REFERENCES v7_brain_snapshots(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX v7_state_changes_novel_id_idx ON v7_state_changes(novel_id);
        CREATE INDEX v7_state_changes_state_id_idx ON v7_state_changes(state_id);
        CREATE INDEX v7_state_changes_run_id_idx ON v7_state_changes(source_run_id);
        COMMENT ON TABLE v7_state_changes IS 'V7 状态变化流水';
    """)

    # 005: v7_author_intents
    op.execute("""
        CREATE TABLE v7_author_intents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            novel_id UUID NOT NULL,
            intent_type VARCHAR(50) NOT NULL,
            intent_key VARCHAR(100) NOT NULL,
            intent_value JSONB NOT NULL DEFAULT '{}',
            description TEXT,
            priority INTEGER NOT NULL DEFAULT 50,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX v7_author_intents_novel_id_idx ON v7_author_intents(novel_id);
        CREATE INDEX v7_author_intents_type_key_idx ON v7_author_intents(intent_type, intent_key);
        COMMENT ON TABLE v7_author_intents IS 'V7 作者意图';
    """)

    # 006: v7_story_goals
    op.execute("""
        CREATE TABLE v7_story_goals (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            novel_id UUID NOT NULL,
            goal_type VARCHAR(50) NOT NULL,
            goal_name VARCHAR(200) NOT NULL,
            description TEXT,
            parent_goal_id UUID REFERENCES v7_story_goals(id),
            goal_order INTEGER NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            progress FLOAT NOT NULL DEFAULT 0.0,
            target_chapter INTEGER,
            completed_chapter INTEGER,
            priority INTEGER NOT NULL DEFAULT 50,
            confidence FLOAT NOT NULL DEFAULT 0.8,
            extra_metadata JSONB NOT NULL DEFAULT '{}',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX v7_story_goals_novel_id_idx ON v7_story_goals(novel_id);
        CREATE INDEX v7_story_goals_parent_id_idx ON v7_story_goals(parent_goal_id);
        CREATE INDEX v7_story_goals_status_idx ON v7_story_goals(status);
        COMMENT ON TABLE v7_story_goals IS 'V7 目标系统';
    """)

    # 007: v7_constraints
    op.execute("""
        CREATE TABLE v7_constraints (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            novel_id UUID NOT NULL,
            constraint_type VARCHAR(50) NOT NULL,
            constraint_name VARCHAR(200) NOT NULL,
            description TEXT,
            constraint_value JSONB NOT NULL DEFAULT '{}',
            severity VARCHAR(20) NOT NULL DEFAULT 'warning',
            check_method VARCHAR(50) NOT NULL DEFAULT 'ai_review',
            priority INTEGER NOT NULL DEFAULT 50,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            violation_count INTEGER NOT NULL DEFAULT 0,
            last_violation_at TIMESTAMPTZ,
            extra_metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX v7_constraints_novel_id_idx ON v7_constraints(novel_id);
        CREATE INDEX v7_constraints_type_idx ON v7_constraints(constraint_type);
        CREATE INDEX v7_constraints_severity_idx ON v7_constraints(severity);
        COMMENT ON TABLE v7_constraints IS 'V7 约束系统';
    """)

    # 008: v7_decision_permissions
    op.execute("""
        CREATE TABLE v7_decision_permissions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            novel_id UUID NOT NULL,
            decision_type VARCHAR(100) NOT NULL UNIQUE,
            permission_level VARCHAR(20) NOT NULL DEFAULT 'auto',
            description TEXT,
            confidence_threshold FLOAT,
            max_retries INTEGER NOT NULL DEFAULT 3,
            escalation_rule JSONB NOT NULL DEFAULT '{}',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            priority INTEGER NOT NULL DEFAULT 50,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX v7_decision_permissions_novel_id_idx ON v7_decision_permissions(novel_id);
        CREATE INDEX v7_decision_permissions_decision_type_idx ON v7_decision_permissions(decision_type);
        COMMENT ON TABLE v7_decision_permissions IS 'V7 决策权限配置';
    """)

    # 009: v7_decision_logs
    op.execute("""
        CREATE TABLE v7_decision_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            novel_id UUID NOT NULL,
            decision_type VARCHAR(100) NOT NULL,
            decision VARCHAR(50) NOT NULL,
            decision_reason TEXT,
            confidence FLOAT NOT NULL DEFAULT 0.9,
            permission_level VARCHAR(20) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'completed',
            run_id UUID,
            context JSONB NOT NULL DEFAULT '{}',
            alternatives JSONB NOT NULL DEFAULT '[]',
            decided_by VARCHAR(50) NOT NULL DEFAULT 'ai',
            decided_by_user_id UUID,
            decided_at TIMESTAMPTZ,
            approval_id UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX v7_decision_logs_novel_id_idx ON v7_decision_logs(novel_id);
        CREATE INDEX v7_decision_logs_run_id_idx ON v7_decision_logs(run_id);
        CREATE INDEX v7_decision_logs_decision_type_idx ON v7_decision_logs(decision_type);
        CREATE INDEX v7_decision_logs_status_idx ON v7_decision_logs(status);
        COMMENT ON TABLE v7_decision_logs IS 'V7 决策日志';
    """)

    # 010: v7_human_interventions
    op.execute("""
        CREATE TABLE v7_human_interventions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            novel_id UUID NOT NULL,
            intervention_type VARCHAR(50) NOT NULL,
            target_type VARCHAR(50) NOT NULL,
            target_id UUID,
            action VARCHAR(50) NOT NULL,
            description TEXT,
            old_value JSONB,
            new_value JSONB,
            reason TEXT,
            user_id UUID,
            run_id UUID,
            result VARCHAR(20) NOT NULL DEFAULT 'success',
            extra_metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX v7_human_interventions_novel_id_idx ON v7_human_interventions(novel_id);
        CREATE INDEX v7_human_interventions_user_id_idx ON v7_human_interventions(user_id);
        CREATE INDEX v7_human_interventions_run_id_idx ON v7_human_interventions(run_id);
        CREATE INDEX v7_human_interventions_type_idx ON v7_human_interventions(intervention_type);
        COMMENT ON TABLE v7_human_interventions IS 'V7 人工干预记录';
    """)

    # 011: v7_plot_nodes
    op.execute("""
        CREATE TABLE v7_plot_nodes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            novel_id UUID NOT NULL,
            node_type VARCHAR(50) NOT NULL,
            node_name VARCHAR(200) NOT NULL,
            description TEXT,
            parent_node_id UUID REFERENCES v7_plot_nodes(id),
            node_order INTEGER NOT NULL DEFAULT 0,
            depth INTEGER NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'planned',
            chapter_number INTEGER,
            word_count_target INTEGER,
            word_count_actual INTEGER,
            importance FLOAT NOT NULL DEFAULT 0.5,
            confidence FLOAT NOT NULL DEFAULT 0.8,
            node_data JSONB NOT NULL DEFAULT '{}',
            goal_id UUID REFERENCES v7_story_goals(id),
            foreshadowing_ids JSONB NOT NULL DEFAULT '[]',
            character_ids JSONB NOT NULL DEFAULT '[]',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX v7_plot_nodes_novel_id_idx ON v7_plot_nodes(novel_id);
        CREATE INDEX v7_plot_nodes_parent_id_idx ON v7_plot_nodes(parent_node_id);
        CREATE INDEX v7_plot_nodes_status_idx ON v7_plot_nodes(status);
        CREATE INDEX v7_plot_nodes_chapter_idx ON v7_plot_nodes(chapter_number);
        COMMENT ON TABLE v7_plot_nodes IS 'V7 故事树节点';
    """)

    # 012: v7_agent_runs
    op.execute("""
        CREATE TABLE v7_agent_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            novel_id UUID NOT NULL,
            run_type VARCHAR(50) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'running',
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at TIMESTAMPTZ,
            duration_seconds FLOAT,
            trigger VARCHAR(50) NOT NULL DEFAULT 'manual',
            trigger_by UUID,
            parent_run_id UUID REFERENCES v7_agent_runs(id),
            input_data JSONB NOT NULL DEFAULT '{}',
            output_data JSONB,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            total_cost FLOAT NOT NULL DEFAULT 0.0,
            step_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            error_type VARCHAR(100),
            extra_metadata JSONB NOT NULL DEFAULT '{}',
            chapter_number INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX v7_agent_runs_novel_id_idx ON v7_agent_runs(novel_id);
        CREATE INDEX v7_agent_runs_status_idx ON v7_agent_runs(status);
        CREATE INDEX v7_agent_runs_run_type_idx ON v7_agent_runs(run_type);
        CREATE INDEX v7_agent_runs_chapter_idx ON v7_agent_runs(chapter_number);
        COMMENT ON TABLE v7_agent_runs IS 'V7 Agent Run';
    """)

    # 013: v7_agent_traces
    op.execute("""
        CREATE TABLE v7_agent_traces (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            novel_id UUID NOT NULL,
            run_id UUID NOT NULL REFERENCES v7_agent_runs(id),
            step_name VARCHAR(100) NOT NULL,
            step_type VARCHAR(50) NOT NULL,
            step_order INTEGER NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'running',
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at TIMESTAMPTZ,
            duration_seconds FLOAT,
            input_summary TEXT,
            output_summary TEXT,
            input_data JSONB,
            output_data JSONB,
            tokens_input INTEGER NOT NULL DEFAULT 0,
            tokens_output INTEGER NOT NULL DEFAULT 0,
            cost FLOAT NOT NULL DEFAULT 0.0,
            model VARCHAR(100),
            prompt_version VARCHAR(50),
            confidence FLOAT,
            decision_id UUID,
            error_message TEXT,
            parent_step_id UUID REFERENCES v7_agent_traces(id),
            extra_metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX v7_agent_traces_novel_id_idx ON v7_agent_traces(novel_id);
        CREATE INDEX v7_agent_traces_run_id_idx ON v7_agent_traces(run_id);
        CREATE INDEX v7_agent_traces_step_order_idx ON v7_agent_traces(step_order);
        CREATE INDEX v7_agent_traces_step_type_idx ON v7_agent_traces(step_type);
        COMMENT ON TABLE v7_agent_traces IS 'V7 执行追踪步骤';
    """)

    # 014: v7_prompt_versions
    op.execute("""
        CREATE TABLE v7_prompt_versions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            prompt_name VARCHAR(200) NOT NULL,
            version INTEGER NOT NULL,
            version_label VARCHAR(100),
            template TEXT NOT NULL,
            model VARCHAR(100) NOT NULL,
            parameters JSONB NOT NULL DEFAULT '{}',
            output_schema JSONB,
            prompt_hash VARCHAR(64) NOT NULL,
            description TEXT,
            change_notes TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            is_default BOOLEAN NOT NULL DEFAULT FALSE,
            created_by VARCHAR(50) NOT NULL DEFAULT 'system',
            golden_cases JSONB NOT NULL DEFAULT '[]',
            extra_metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX v7_prompt_versions_name_idx ON v7_prompt_versions(prompt_name);
        CREATE INDEX v7_prompt_versions_hash_idx ON v7_prompt_versions(prompt_hash);
        CREATE UNIQUE INDEX v7_prompt_versions_name_version_idx ON v7_prompt_versions(prompt_name, version);
        COMMENT ON TABLE v7_prompt_versions IS 'V7 Prompt 版本管理';
    """)

    # 015: v7_prompt_executions
    op.execute("""
        CREATE TABLE v7_prompt_executions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            prompt_version_id UUID NOT NULL,
            prompt_name VARCHAR(200) NOT NULL,
            version INTEGER NOT NULL,
            model VARCHAR(100) NOT NULL,
            input_variables JSONB NOT NULL DEFAULT '{}',
            rendered_prompt TEXT,
            output JSONB,
            output_raw TEXT,
            tokens_input INTEGER NOT NULL DEFAULT 0,
            tokens_output INTEGER NOT NULL DEFAULT 0,
            cost FLOAT NOT NULL DEFAULT 0.0,
            duration_seconds FLOAT,
            status VARCHAR(20) NOT NULL DEFAULT 'success',
            error_message TEXT,
            run_id UUID,
            step_id UUID,
            novel_id UUID,
            validation_passed BOOLEAN,
            validation_errors JSONB NOT NULL DEFAULT '[]',
            extra_metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX v7_prompt_executions_name_idx ON v7_prompt_executions(prompt_name);
        CREATE INDEX v7_prompt_executions_run_id_idx ON v7_prompt_executions(run_id);
        CREATE INDEX v7_prompt_executions_novel_id_idx ON v7_prompt_executions(novel_id);
        CREATE INDEX v7_prompt_executions_status_idx ON v7_prompt_executions(status);
        COMMENT ON TABLE v7_prompt_executions IS 'V7 Prompt 调用记录';
    """)

    # 016: v7_cost_budgets
    op.execute("""
        CREATE TABLE v7_cost_budgets (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            novel_id UUID NOT NULL,
            budget_type VARCHAR(50) NOT NULL,
            budget_scope VARCHAR(50) NOT NULL,
            limit_cny FLOAT NOT NULL,
            spent_cny FLOAT NOT NULL DEFAULT 0.0,
            limit_tokens INTEGER,
            spent_tokens INTEGER NOT NULL DEFAULT 0,
            period_start DATE,
            period_end DATE,
            alert_threshold_80 BOOLEAN NOT NULL DEFAULT FALSE,
            alert_threshold_95 BOOLEAN NOT NULL DEFAULT FALSE,
            action_on_exceed VARCHAR(20) NOT NULL DEFAULT 'warn',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            description TEXT,
            cost_policy JSONB NOT NULL DEFAULT '{}',
            extra_metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX v7_cost_budgets_novel_id_idx ON v7_cost_budgets(novel_id);
        CREATE INDEX v7_cost_budgets_type_idx ON v7_cost_budgets(budget_type);
        CREATE INDEX v7_cost_budgets_scope_idx ON v7_cost_budgets(budget_scope);
        COMMENT ON TABLE v7_cost_budgets IS 'V7 成本预算管理';
    """)

    # 017: v7_event_logs
    op.execute("""
        CREATE TABLE v7_event_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            novel_id UUID NOT NULL,
            event_type VARCHAR(100) NOT NULL,
            event_name VARCHAR(200) NOT NULL,
            event_category VARCHAR(50) NOT NULL,
            event_data JSONB NOT NULL DEFAULT '{}',
            event_time TIMESTAMPTZ NOT NULL DEFAULT now(),
            source VARCHAR(50) NOT NULL,
            source_run_id UUID,
            source_step_id UUID,
            source_user_id UUID,
            severity VARCHAR(20) NOT NULL DEFAULT 'info',
            description TEXT,
            correlation_id UUID,
            version INTEGER NOT NULL DEFAULT 1,
            extra_metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX v7_event_logs_novel_id_idx ON v7_event_logs(novel_id);
        CREATE INDEX v7_event_logs_event_type_idx ON v7_event_logs(event_type);
        CREATE INDEX v7_event_logs_event_category_idx ON v7_event_logs(event_category);
        CREATE INDEX v7_event_logs_run_id_idx ON v7_event_logs(source_run_id);
        CREATE INDEX v7_event_logs_correlation_id_idx ON v7_event_logs(correlation_id);
        CREATE INDEX v7_event_logs_event_time_idx ON v7_event_logs(event_time);
        COMMENT ON TABLE v7_event_logs IS 'V7 事件永久记录';
    """)

    # 018: v7_seed_data
    op.execute("""
        CREATE TABLE v7_seed_data (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            seed_type VARCHAR(50) NOT NULL,
            seed_key VARCHAR(200) NOT NULL,
            seed_value JSONB NOT NULL DEFAULT '{}',
            description TEXT,
            is_builtin BOOLEAN NOT NULL DEFAULT TRUE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            version INTEGER NOT NULL DEFAULT 1,
            extra_metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX v7_seed_data_type_idx ON v7_seed_data(seed_type);
        CREATE INDEX v7_seed_data_key_idx ON v7_seed_data(seed_key);
        CREATE UNIQUE INDEX v7_seed_data_type_key_idx ON v7_seed_data(seed_type, seed_key);
        COMMENT ON TABLE v7_seed_data IS 'V7 种子数据配置';
    """)

    # 插入默认权限配置种子数据
    op.execute("""
        INSERT INTO v7_seed_data (seed_type, seed_key, seed_value, description, is_builtin) VALUES
        ('permission', 'chapter_generation', '{"permission_level": "auto", "confidence_threshold": 0.7, "max_retries": 3}', '章节生成权限', TRUE),
        ('permission', 'state_update', '{"permission_level": "auto", "confidence_threshold": 0.8, "max_retries": 2}', '状态更新权限', TRUE),
        ('permission', 'character_change', '{"permission_level": "notify", "confidence_threshold": 0.9, "max_retries": 1}', '人物变更权限', TRUE),
        ('permission', 'plot_replan', '{"permission_level": "approve", "confidence_threshold": 0.8, "max_retries": 1}', '剧情重规划权限', TRUE),
        ('permission', 'style_change', '{"permission_level": "approve", "confidence_threshold": 0.9, "max_retries": 1}', '风格变更权限', TRUE),
        ('permission', 'world_rule_change', '{"permission_level": "forbidden", "confidence_threshold": 1.0, "max_retries": 0}', '世界观规则变更权限', TRUE);
    """)


def downgrade() -> None:
    # 按创建逆序删除
    op.execute("DROP TABLE IF EXISTS v7_seed_data CASCADE;")
    op.execute("DROP TABLE IF EXISTS v7_event_logs CASCADE;")
    op.execute("DROP TABLE IF EXISTS v7_cost_budgets CASCADE;")
    op.execute("DROP TABLE IF EXISTS v7_prompt_executions CASCADE;")
    op.execute("DROP TABLE IF EXISTS v7_prompt_versions CASCADE;")
    op.execute("DROP TABLE IF EXISTS v7_agent_traces CASCADE;")
    op.execute("DROP TABLE IF EXISTS v7_agent_runs CASCADE;")
    op.execute("DROP TABLE IF EXISTS v7_plot_nodes CASCADE;")
    op.execute("DROP TABLE IF EXISTS v7_human_interventions CASCADE;")
    op.execute("DROP TABLE IF EXISTS v7_decision_logs CASCADE;")
    op.execute("DROP TABLE IF EXISTS v7_decision_permissions CASCADE;")
    op.execute("DROP TABLE IF EXISTS v7_constraints CASCADE;")
    op.execute("DROP TABLE IF EXISTS v7_story_goals CASCADE;")
    op.execute("DROP TABLE IF EXISTS v7_author_intents CASCADE;")
    op.execute("DROP TABLE IF EXISTS v7_state_changes CASCADE;")
    op.execute("DROP TABLE IF EXISTS v7_story_states CASCADE;")
    op.execute("DROP TABLE IF EXISTS v7_brain_snapshots CASCADE;")
    op.execute("DROP TABLE IF EXISTS v7_story_versions CASCADE;")
