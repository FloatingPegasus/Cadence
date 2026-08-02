"""add continuity contexts and day links

Revision ID: d6f1b93c4a72
Revises: c4e8a19d7f20
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d6f1b93c4a72"
down_revision: Union[str, Sequence[str], None] = "c4e8a19d7f20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contexts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_contexts_user_archived_id",
        "contexts",
        ["user_id", "is_archived", "id"],
    )
    op.create_index(
        "uq_active_user_context_name",
        "contexts",
        ["user_id", "name"],
        unique=True,
        sqlite_where=sa.text("is_archived = 0"),
    )
    op.create_table(
        "day_contexts",
        sa.Column("day_id", sa.Integer(), nullable=False),
        sa.Column("context_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["context_id"], ["contexts.id"]),
        sa.ForeignKeyConstraint(["day_id"], ["days.id"]),
        sa.PrimaryKeyConstraint("day_id", "context_id"),
    )
    op.create_index(
        "ix_day_contexts_context_day",
        "day_contexts",
        ["context_id", "day_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_day_contexts_context_day",
        table_name="day_contexts",
    )
    op.drop_table("day_contexts")
    op.drop_index(
        "uq_active_user_context_name",
        table_name="contexts",
        sqlite_where=sa.text("is_archived = 0"),
    )
    op.drop_index(
        "ix_contexts_user_archived_id",
        table_name="contexts",
    )
    op.drop_table("contexts")
