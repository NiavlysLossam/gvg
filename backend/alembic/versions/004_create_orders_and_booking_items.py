"""Create orders and booking_items tables

Revision ID: 004_create_orders_and_booking_items
Revises: 003_create_spots
Create Date: 2026-09-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_create_orders_and_booking_items'
down_revision: Union[str, None] = '003_create_spots'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'orders',
        sa.Column('id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('event_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('order_number', sa.String(length=50), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=False),
        sa.Column('last_name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=False),
        sa.Column('street_address', sa.String(length=255), nullable=False),
        sa.Column('postal_code', sa.String(length=20), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('honor_declaration_accepted', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('honor_declaration_accepted_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('total_price_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('payment_method', sa.String(length=50), nullable=False, server_default='stripe'),
        sa.Column('stripe_payment_intent_id', sa.String(length=255), nullable=True),
        sa.Column('access_token', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_number', name='uq_orders_order_number'),
        sa.UniqueConstraint('access_token', name='uq_orders_access_token'),
    )
    op.create_index('ix_orders_event_id', 'orders', ['event_id'])
    op.create_index('ix_orders_order_number', 'orders', ['order_number'])
    op.create_index('ix_orders_email', 'orders', ['email'])
    op.create_index('ix_orders_access_token', 'orders', ['access_token'])
    op.create_index('ix_orders_status', 'orders', ['status'])

    op.create_table(
        'booking_items',
        sa.Column('id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('order_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('spot_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('price_cents', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['spot_id'], ['spots.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_booking_items_order_id', 'booking_items', ['order_id'])
    op.create_index('ix_booking_items_spot_id', 'booking_items', ['spot_id'])


def downgrade() -> None:
    op.drop_index('ix_booking_items_spot_id', table_name='booking_items')
    op.drop_index('ix_booking_items_order_id', table_name='booking_items')
    op.drop_table('booking_items')

    op.drop_index('ix_orders_status', table_name='orders')
    op.drop_index('ix_orders_access_token', table_name='orders')
    op.drop_index('ix_orders_email', table_name='orders')
    op.drop_index('ix_orders_order_number', table_name='orders')
    op.drop_index('ix_orders_event_id', table_name='orders')
    op.drop_table('orders')
