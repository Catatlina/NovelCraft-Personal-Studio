"""Merge feature flags and V1 agents migration heads.

Revision ID: f932f2b0b3bb
Revises: nc_feature_flags, nc_v1_agents
"""

from typing import Sequence, Union


revision: str = "f932f2b0b3bb"
down_revision: Union[str, Sequence[str], None] = ("nc_feature_flags", "nc_v1_agents")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
