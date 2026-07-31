"""v6.1.2 schema phase E: expand check constraints for new task types

Adds 'replan' to repair_versions.repair_type and 'plan' to
generation_cost_log.phase.  These values are produced by Step 5 (滚动重规划)
and the new extract_ledger task.  Without this fix, real chapter loop runs
crash on INSERT.

Revision ID: e9f5a6b7c8d9
Revises: d8e4f5a6b7c8
Create Date: 2026-07-31 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9f5a6b7c8d9'
down_revision: Union[str, Sequence[str], None] = 'd8e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Expand check constraints."""
    # repair_versions: Step 5 uses repair_type='replan' for replan+rewrite
    op.execute(
        "ALTER TABLE repair_versions DROP CONSTRAINT IF EXISTS repair_versions_repair_type_check;"
    )
    op.execute(
        "ALTER TABLE repair_versions ADD CONSTRAINT repair_versions_repair_type_check "
        "CHECK (repair_type IN ('local','section','chapter','replan'));"
    )

    # generation_cost_log: new phases from Step 5 replan and ledger extraction
    op.execute(
        "ALTER TABLE generation_cost_log DROP CONSTRAINT IF EXISTS generation_cost_log_phase_check;"
    )
    op.execute(
        "ALTER TABLE generation_cost_log ADD CONSTRAINT generation_cost_log_phase_check "
        "CHECK (phase IN ('generate','review','repair','humanize','other','plan'));"
    )


def downgrade() -> None:
    """Restore original constraints."""
    op.execute(
        "ALTER TABLE generation_cost_log DROP CONSTRAINT IF EXISTS generation_cost_log_phase_check;"
    )
    op.execute(
        "ALTER TABLE generation_cost_log ADD CONSTRAINT generation_cost_log_phase_check "
        "CHECK (phase IN ('generate','review','repair','humanize','other'));"
    )
    op.execute(
        "ALTER TABLE repair_versions DROP CONSTRAINT IF EXISTS repair_versions_repair_type_check;"
    )
    op.execute(
        "ALTER TABLE repair_versions ADD CONSTRAINT repair_versions_repair_type_check "
        "CHECK (repair_type IN ('local','section','chapter'));"
    )
