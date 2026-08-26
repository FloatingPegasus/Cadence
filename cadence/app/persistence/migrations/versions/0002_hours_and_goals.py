"""Add hourly logs and user goals."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_hours_and_goals"
down_revision: Union[str, Sequence[str], None] = "0001_postgresql_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hour_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("day_id", sa.Integer(), nullable=False),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("hour >= 0 AND hour <= 23", name="hour_range"),
        sa.ForeignKeyConstraint(["day_id"], ["days.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day_id", "hour", name="day_hour_uc"),
    )
    op.create_index("ix_hour_logs_day_id", "hour_logs", ["day_id"])

    op.create_table(
        "user_goals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_goals_user_id", "user_goals", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_goals_user_id", table_name="user_goals")
    op.drop_table("user_goals")
    op.drop_index("ix_hour_logs_day_id", table_name="hour_logs")
    op.drop_table("hour_logs")
