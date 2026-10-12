"""Add services to events

Revision ID: 011_add_services_to_events
Revises: 010_add_wms_fields_to_events
Create Date: 2026-09-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '011_add_services_to_events'
down_revision: Union[str, None] = '010_add_wms_fields_to_events'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('events') as batch_op:
        batch_op.add_column(
            sa.Column('services', sa.JSON(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table('events') as batch_op:
        batch_op.drop_column('services')
