"""merge all heads

Revision ID: b324f6c7a7f1
Revises: f932f2b0b3bb, nc_v3_scene_layer
Create Date: 2026-07-29 12:52:56.727414

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b324f6c7a7f1'
down_revision: Union[str, Sequence[str], None] = ('f932f2b0b3bb', 'nc_v3_scene_layer')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
