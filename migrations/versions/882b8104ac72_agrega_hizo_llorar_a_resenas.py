"""agrega hizo_llorar a resenas

Revision ID: 882b8104ac72
Revises: 40e26b7cd9e3
Create Date: 2026-08-25 15:04:44.928212

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '882b8104ac72'
down_revision: Union[str, None] = '40e26b7cd9e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('resenas', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('hizo_llorar', sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table('resenas', schema=None) as batch_op:
        batch_op.drop_column('hizo_llorar')
