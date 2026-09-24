"""Keep hour entries and day logs as one stream of timed logs."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_one_log_stream"
down_revision: Union[str, Sequence[str], None] = "0005_task_abandon"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversation_entries",
        sa.Column("hour", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "conversation_entry_hour_range",
        "conversation_entries",
        "hour IS NULL OR (hour >= 0 AND hour <= 23)",
    )
    op.execute(
        """
        INSERT INTO conversation_entries (day_id, role, content, created_at, hour)
        SELECT day_id, 'user', content, updated_at, hour
        FROM hour_logs
        WHERE length(trim(content)) > 0
        ORDER BY day_id, hour
        """
    )
    op.drop_index("ix_hour_logs_day_id", table_name="hour_logs")
    op.drop_table("hour_logs")


def downgrade() -> None:
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
    op.execute(
        """
        INSERT INTO hour_logs (day_id, hour, content, updated_at)
        SELECT
            day_id,
            hour,
            string_agg(content, E'\\n' ORDER BY created_at, id),
            max(created_at)
        FROM conversation_entries
        WHERE hour IS NOT NULL AND role = 'user'
        GROUP BY day_id, hour
        """
    )
    op.execute(
        "DELETE FROM conversation_entries WHERE hour IS NOT NULL AND role = 'user'"
    )
    op.drop_constraint(
        "conversation_entry_hour_range",
        "conversation_entries",
        type_="check",
    )
    op.drop_column("conversation_entries", "hour")
