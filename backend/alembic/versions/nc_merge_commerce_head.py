"""Merge nc_commerce_plans branch back into the mainline (audit BUG-04).

A single head restores `alembic upgrade head` as the standard deploy command.
"""
from typing import Sequence, Union

revision: str = "nc_merge_commerce_head"
down_revision: Union[str, Sequence[str], None] = ("9f09aa0f10cc", "nc_commerce_plans")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
