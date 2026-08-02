"""add email and is_verified to users

Revision ID: f60324d565a2
Revises: 520f0462d383
Create Date: 2026-07-23 13:38:32.511620

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f60324d565a2'
down_revision: Union[str, Sequence[str], None] = '520f0462d383'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('email', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('is_verified', sa.Boolean(), nullable=True))

    op.execute(
        "UPDATE users SET email = 'user' || id || '@cadence.app' WHERE email IS NULL"
    )
    op.execute(
        "UPDATE users SET is_verified = 1 WHERE is_verified IS NULL"
    )

    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('email', nullable=False)
        batch_op.alter_column('is_verified', nullable=False, server_default=sa.text('0'))
        batch_op.create_index('ix_users_email', ['email'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_column('users', 'is_verified')
    op.drop_column('users', 'email')
