"""index open carry-forward items

Revision ID: f8a2c7d14e60
Revises: d6f1b93c4a72
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op


revision: str = "f8a2c7d14e60"
down_revision: Union[str, Sequence[str], None] = "d6f1b93c4a72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_carry_forward_status_origin",
        "carry_forward_items",
        ["status", "origin_day_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_carry_forward_status_origin",
        table_name="carry_forward_items",
    )
