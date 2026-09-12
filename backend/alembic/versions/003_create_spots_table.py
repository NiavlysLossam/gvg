"""Create spots table

Revision ID: 003_create_spots
Revises: 002_add_map_calibration
Create Date: 2026-09-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry


# revision identifiers, used by Alembic.
revision: str = '003_create_spots'
down_revision: Union[str, None] = '002_add_map_calibration'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'spots',
        sa.Column('id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('event_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=False),
        sa.Column('linear_meters', sa.Float(), nullable=False),
        sa.Column('price_cents', sa.Integer(), nullable=False),
        sa.Column('geom', Geometry(geometry_type='POLYGON', srid=-1, spatial_index=True), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='available'),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('locked_by_token', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id', 'label', name='uq_spots_event_id_label'),
    )
    op.create_index('ix_spots_event_id', 'spots', ['event_id'])
    op.create_index('ix_spots_status', 'spots', ['status'])


def downgrade() -> None:
    op.drop_index('ix_spots_status', table_name='spots')
    op.drop_index('ix_spots_event_id', table_name='spots')
    op.drop_table('spots')

