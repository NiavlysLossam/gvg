"""Initial migration: create events table

Revision ID: 001_initial_events
Revises: 
Create Date: 2026-09-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial_events'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'events',
        sa.Column('id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('map_type', sa.String(length=50), nullable=False, server_default='geographic'),
        sa.Column('background_image_url', sa.String(length=1024), nullable=True),
        sa.Column('price_per_meter_cents', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('setup_start_time', sa.String(length=10), nullable=True, server_default='06:00'),
        sa.Column('setup_end_time', sa.String(length=10), nullable=True, server_default='08:00'),
        sa.Column('public_start_time', sa.String(length=10), nullable=True, server_default='08:00'),
        sa.Column('public_end_time', sa.String(length=10), nullable=True, server_default='18:00'),
        sa.Column('location_address', sa.String(length=500), nullable=True),
        sa.Column('organizer_email', sa.String(length=255), nullable=True),
        sa.Column('stripe_account_id', sa.String(length=255), nullable=True),
        sa.Column('manual_approval_required', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('rules_text', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_events_slug', 'events', ['slug'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_events_slug', table_name='events')
    op.drop_table('events')

