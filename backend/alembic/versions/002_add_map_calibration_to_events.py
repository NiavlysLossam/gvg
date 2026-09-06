"""Add map calibration columns to events table

Revision ID: 002_add_map_calibration
Revises: 001_initial_events
Create Date: 2026-09-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_map_calibration'
down_revision: Union[str, None] = '001_initial_events'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('events', sa.Column('center_latitude', sa.Float(), nullable=True))
    op.add_column('events', sa.Column('center_longitude', sa.Float(), nullable=True))
    op.add_column('events', sa.Column('default_zoom', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('events', 'default_zoom')
    op.drop_column('events', 'center_longitude')
    op.drop_column('events', 'center_latitude')

