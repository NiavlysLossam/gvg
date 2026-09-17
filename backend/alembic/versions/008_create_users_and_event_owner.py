"""Create users table and add owner_id to events

Revision ID: 008_create_users_and_event_owner
Revises: 007_create_email_logs
Create Date: 2026-09-17 14:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008_create_users_and_event_owner'
down_revision: Union[str, None] = '007_create_email_logs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='event_admin'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_role', 'users', ['role'])

    # 2. Add owner_id to events table with FK referencing users.id
    with op.batch_alter_table('events') as batch_op:
        batch_op.add_column(
            sa.Column(
                'owner_id',
                sa.Uuid(as_uuid=True),
                sa.ForeignKey('users.id', ondelete='SET NULL', name='fk_events_owner_id_users'),
                nullable=True,
            )
        )
        batch_op.create_index('ix_events_owner_id', ['owner_id'])


def downgrade() -> None:
    # 1. Remove owner_id from events
    with op.batch_alter_table('events') as batch_op:
        batch_op.drop_index('ix_events_owner_id')
        batch_op.drop_column('owner_id')

    # 2. Drop users table
    op.drop_index('ix_users_role', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')

