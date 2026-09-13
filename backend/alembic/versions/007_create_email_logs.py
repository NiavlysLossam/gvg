"""Create email_logs table

Revision ID: 007_create_email_logs
Revises: 006_add_cancellation_fields
Create Date: 2026-09-13 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007_create_email_logs'
down_revision: Union[str, None] = '006_add_cancellation_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'email_logs',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('event_id', sa.Uuid(as_uuid=True), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=True),
        sa.Column('order_id', sa.Uuid(as_uuid=True), sa.ForeignKey('orders.id', ondelete='SET NULL'), nullable=True),
        sa.Column('recipient', sa.String(length=255), nullable=False),
        sa.Column('email_type', sa.String(length=50), nullable=False),
        sa.Column('subject', sa.String(length=500), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='sent'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_email_logs_event_id', 'email_logs', ['event_id'])
    op.create_index('ix_email_logs_order_id', 'email_logs', ['order_id'])
    op.create_index('ix_email_logs_recipient', 'email_logs', ['recipient'])
    op.create_index('ix_email_logs_email_type', 'email_logs', ['email_type'])
    op.create_index('ix_email_logs_status', 'email_logs', ['status'])


def downgrade() -> None:
    op.drop_index('ix_email_logs_status', table_name='email_logs')
    op.drop_index('ix_email_logs_email_type', table_name='email_logs')
    op.drop_index('ix_email_logs_recipient', table_name='email_logs')
    op.drop_index('ix_email_logs_order_id', table_name='email_logs')
    op.drop_index('ix_email_logs_event_id', table_name='email_logs')
    op.drop_table('email_logs')

