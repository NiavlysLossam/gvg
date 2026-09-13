"""Add offline order fields and adapt nullability

Revision ID: 005_add_offline_order_fields
Revises: 004_create_orders
Create Date: 2026-09-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_add_offline_order_fields'
down_revision: Union[str, None] = '004_create_orders'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('orders') as batch_op:
        batch_op.add_column(sa.Column('offline_payment_reference', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('admin_notes', sa.Text(), nullable=True))
        batch_op.alter_column('email', existing_type=sa.String(length=255), nullable=True)
        batch_op.alter_column('street_address', existing_type=sa.String(length=255), nullable=True)
        batch_op.alter_column('postal_code', existing_type=sa.String(length=20), nullable=True)
        batch_op.alter_column('city', existing_type=sa.String(length=100), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('orders') as batch_op:
        batch_op.drop_column('admin_notes')
        batch_op.drop_column('offline_payment_reference')
        batch_op.alter_column('city', existing_type=sa.String(length=100), nullable=False)
        batch_op.alter_column('postal_code', existing_type=sa.String(length=20), nullable=False)
        batch_op.alter_column('street_address', existing_type=sa.String(length=255), nullable=False)
        batch_op.alter_column('email', existing_type=sa.String(length=255), nullable=False)

