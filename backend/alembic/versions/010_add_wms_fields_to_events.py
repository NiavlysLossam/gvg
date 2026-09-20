"""Add wms_url and wms_layer to events

Revision ID: 010_add_wms_fields_to_events
Revises: 009_add_poster_image_url
Create Date: 2026-09-20 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '010_add_wms_fields_to_events'
down_revision: Union[str, None] = '009_add_poster_image_url'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('events') as batch_op:
        batch_op.add_column(
            sa.Column('wms_url', sa.String(length=1024), nullable=True)
        )
        batch_op.add_column(
            sa.Column('wms_layer', sa.String(length=255), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table('events') as batch_op:
        batch_op.drop_column('wms_layer')
        batch_op.drop_column('wms_url')
