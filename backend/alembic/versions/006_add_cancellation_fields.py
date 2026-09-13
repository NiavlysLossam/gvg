"""Add cancellation fields to orders table

Revision ID: 006_add_cancellation_fields
Revises: 005_add_offline_order_fields
Create Date: 2026-09-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_add_cancellation_fields'
down_revision: Union[str, None] = '005_add_offline_order_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('orders') as batch_op:
        batch_op.add_column(sa.Column('cancellation_reason', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('cancellation_comment', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('cancellation_requested_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('orders') as batch_op:
        batch_op.drop_column('cancellation_requested_at')
        batch_op.drop_column('cancellation_comment')
        batch_op.drop_column('cancellation_reason')
