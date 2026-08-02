"""unify habit logs with the day continuity spine

Revision ID: 9f1c2d8a4b70
Revises: f60324d565a2
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9f1c2d8a4b70"
down_revision: Union[str, Sequence[str], None] = "f60324d565a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NAMING_CONVENTION = {
    "uq": "uq_%(table_name)s_%(column_0_name)s",
}


def upgrade() -> None:
    # The initial schema accidentally made dates globally unique. A day is
    # unique per user, so two users must be able to own the same calendar date.
    with op.batch_alter_table(
        "days",
        recreate="always",
        naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_constraint("uq_days_date", type_="unique")

    # Every historical habit log gets a Day before its duplicate date/user
    # columns are replaced with the canonical day_id relationship.
    op.execute(
        """
        INSERT OR IGNORE INTO days (user_id, date, status, daily_note)
        SELECT DISTINCT user_id, date, 'open', ''
        FROM habit_logs
        """
    )

    with op.batch_alter_table("habit_logs") as batch_op:
        batch_op.add_column(sa.Column("day_id", sa.Integer(), nullable=True))

    op.execute(
        """
        UPDATE habit_logs
        SET day_id = (
            SELECT days.id
            FROM days
            WHERE days.user_id = habit_logs.user_id
              AND days.date = habit_logs.date
        )
        """
    )

    with op.batch_alter_table("habit_logs", recreate="always") as batch_op:
        batch_op.drop_constraint("user_habit_date_uc", type_="unique")
        batch_op.drop_column("user_id")
        batch_op.drop_column("date")
        batch_op.alter_column("day_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "fk_habit_logs_day_id_days", "days", ["day_id"], ["id"]
        )
        batch_op.create_unique_constraint(
            "day_habit_uc", ["day_id", "habit_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("habit_logs", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("date", sa.Date(), nullable=True))

    op.execute(
        """
        UPDATE habit_logs
        SET user_id = (SELECT days.user_id FROM days WHERE days.id = habit_logs.day_id),
            date = (SELECT days.date FROM days WHERE days.id = habit_logs.day_id)
        """
    )

    with op.batch_alter_table("habit_logs", recreate="always") as batch_op:
        batch_op.drop_constraint("day_habit_uc", type_="unique")
        batch_op.drop_constraint(
            "fk_habit_logs_day_id_days", type_="foreignkey"
        )
        batch_op.drop_column("day_id")
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("date", existing_type=sa.Date(), nullable=False)
        batch_op.create_unique_constraint(
            "user_habit_date_uc", ["user_id", "habit_id", "date"]
        )
