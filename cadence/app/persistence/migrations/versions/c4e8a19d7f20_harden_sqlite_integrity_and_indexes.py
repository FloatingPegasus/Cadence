"""harden SQLite integrity and hot-path indexes

Revision ID: c4e8a19d7f20
Revises: b8d3f72a6c14
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c4e8a19d7f20"
down_revision: Union[str, Sequence[str], None] = "b8d3f72a6c14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("PRAGMA foreign_keys=OFF")
    with op.batch_alter_table("days") as batch_op:
        batch_op.create_foreign_key(
            "fk_days_user_id_users",
            "users",
            ["user_id"],
            ["id"],
        )
    with op.batch_alter_table("habits") as batch_op:
        batch_op.create_foreign_key(
            "fk_habits_user_id_users",
            "users",
            ["user_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_habits_user_archived_id",
            ["user_id", "is_archived", "id"],
        )
    op.create_index(
        "ix_conversation_entries_day_created",
        "conversation_entries",
        ["day_id", "created_at"],
    )
    op.execute("PRAGMA foreign_keys=ON")


def downgrade() -> None:
    op.execute("PRAGMA foreign_keys=OFF")
    op.drop_index(
        "ix_conversation_entries_day_created",
        table_name="conversation_entries",
    )
    with op.batch_alter_table("habits") as batch_op:
        batch_op.drop_index("ix_habits_user_archived_id")
        batch_op.drop_constraint(
            "fk_habits_user_id_users",
            type_="foreignkey",
        )
    with op.batch_alter_table("days") as batch_op:
        batch_op.drop_constraint(
            "fk_days_user_id_users",
            type_="foreignkey",
        )
    op.execute("PRAGMA foreign_keys=ON")
