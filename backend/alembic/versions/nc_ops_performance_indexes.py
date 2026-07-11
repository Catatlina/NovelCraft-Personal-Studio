"""NC-OPS: Performance indexes — 12 critical + 9 high-priority indexes."""
from alembic import op

revision = "nc_ops_performance_indexes"
down_revision = "nc_sc004_slot_recovery"

def upgrade():
    """Add performance indexes. Use raw connection to avoid transaction for CONCURRENTLY."""
    conn = op.get_bind()
    conn.exec_driver_sql("COMMIT")  # Exit current transaction for CONCURRENTLY

    indexes = [
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_foreshadowings_chapter ON foreshadowings(chapter_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_reviews_content ON reviews(content_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_reviews_workflow_run ON reviews(workflow_run_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_generation_batches_novel ON generation_batches(novel_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_generation_batches_project ON generation_batches(project_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_publish_records_content ON publish_records(content_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_run_nodes_run ON run_nodes(run_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_versions_content ON versions(content_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_versions_user ON versions(created_by)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ai_calls_run ON ai_calls(run_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ai_calls_project ON ai_calls(project_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_operation_logs_content ON operation_logs(content_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contents_parent_type ON contents(parent_id, type)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contents_project ON contents(project_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_knowledge_items_kind ON knowledge_items(kind)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_knowledge_items_project ON knowledge_items(project_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_entity_states_content ON entity_states(content_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_entity_states_updated ON entity_states(updated_at DESC)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workflow_runs_status ON workflow_runs(status)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_operation_logs_created ON operation_logs(created_at DESC)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_logs_entity ON audit_logs(entity_type, entity_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_account_trackings_platform ON account_trackings(platform, account_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_published_posts_platform ON published_posts(platform, content_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_published_posts_created ON published_posts(created_at DESC)",
    ]
    for sql in indexes:
        try:
            conn.exec_driver_sql(sql)
        except Exception:
            pass  # Index may already exist

def downgrade():
    for idx in [
        "idx_foreshadowings_chapter", "idx_reviews_content", "idx_reviews_workflow_run",
        "idx_generation_batches_novel", "idx_generation_batches_project",
        "idx_publish_records_content", "idx_run_nodes_run", "idx_versions_content",
        "idx_versions_user", "idx_ai_calls_run", "idx_ai_calls_project",
        "idx_operation_logs_content", "idx_contents_parent_type", "idx_contents_project",
        "idx_knowledge_items_kind", "idx_knowledge_items_project",
        "idx_entity_states_content", "idx_entity_states_updated",
        "idx_workflow_runs_status", "idx_operation_logs_created",
        "idx_audit_logs_entity", "idx_account_trackings_platform",
        "idx_published_posts_platform", "idx_published_posts_created",
    ]:
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {idx}")
