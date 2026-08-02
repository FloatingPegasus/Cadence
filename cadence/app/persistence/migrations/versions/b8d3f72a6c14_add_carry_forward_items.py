"""add carry-forward continuity items

Revision ID: b8d3f72a6c14
Revises: a4c91e7b2d65
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8d3f72a6c14"
down_revision: Union[str, Sequence[str], None] = "a4c91e7b2d65"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "carry_forward_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("origin_day_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["origin_day_id"], ["days.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_carry_forward_origin_status",
        "carry_forward_items",
        ["origin_day_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_carry_forward_origin_status", table_name="carry_forward_items"
    )
    op.drop_table("carry_forward_items")
