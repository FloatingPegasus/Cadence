"""Add user tasks."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_tasks"
down_revision: Union[str, Sequence[str], None] = "0002_hours_and_goals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "is_completed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
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
    op.create_index("ix_tasks_user_due", "tasks", ["user_id", "due_date"])
    op.create_index(
        "ix_tasks_user_open",
        "tasks",
        ["user_id", "is_completed", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_user_open", table_name="tasks")
    op.drop_index("ix_tasks_user_due", table_name="tasks")
    op.drop_table("tasks")
