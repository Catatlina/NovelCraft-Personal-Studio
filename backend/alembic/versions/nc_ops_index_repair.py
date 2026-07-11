"""NC-OPS: repair 4 silently-failed performance indexes.

nc_ops_performance_indexes referenced columns that do not exist
(entity_states.content_id, versions.content_id, versions.created_by,
operation_logs.content_id) and swallowed the errors with try/except.
This migration creates the intended indexes on the real columns and
fails loudly if anything is wrong.
"""
from alembic import op


revision = "nc_ops_index_repair"
down_revision = "nc_ops_performance_indexes"

INDEXES = [
    ("idx_entity_states_chapter", "entity_states(chapter_id)"),
    ("idx_versions_entity", "versions(entity_type, entity_id)"),
    ("idx_versions_author", "versions(author_id)"),
    ("idx_operation_logs_project", "operation_logs(project_id)"),
]


def upgrade():
    for name, target in INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {target}")


def downgrade():
    for name, _target in INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
