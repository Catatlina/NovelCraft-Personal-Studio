"""Merge the V3 feature-flag and agent branches into one deployable head.

Revision ID: nc_merge_v3_heads
Revises: nc_feature_flags, nc_v1_agents
Create Date: 2026-07-23
"""
from collections.abc import Sequence


revision: str = "nc_merge_v3_heads"
down_revision: str | Sequence[str] | None = ("nc_feature_flags", "nc_v1_agents")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
