"""Add poster_image_url to events

Revision ID: 009_add_poster_image_url
Revises: 008_create_users_and_event_owner
Create Date: 2026-09-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009_add_poster_image_url'
down_revision: Union[str, None] = '008_create_users_and_event_owner'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('events') as batch_op:
        batch_op.add_column(
            sa.Column('poster_image_url', sa.String(length=1024), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table('events') as batch_op:
        batch_op.drop_column('poster_image_url')

