"""merge remaining heads

Revision ID: 9f09aa0f10cc
Revises: nc_ai_calls_project_index, nc_audit_workflow_scope
Create Date: 2026-07-13 11:02:28.926643

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f09aa0f10cc'
down_revision: Union[str, Sequence[str], None] = ('nc_ai_calls_project_index', 'nc_audit_workflow_scope')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
