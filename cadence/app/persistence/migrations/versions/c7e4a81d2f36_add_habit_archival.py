"""add continuity-preserving habit archival

Revision ID: c7e4a81d2f36
Revises: 9f1c2d8a4b70
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7e4a81d2f36"
down_revision: Union[str, Sequence[str], None] = "9f1c2d8a4b70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("habits", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_archived",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch_op.drop_constraint("user_habitname_uc", type_="unique")

    op.create_index(
        "uq_active_user_habit_name",
        "habits",
        ["user_id", "name"],
        unique=True,
        sqlite_where=sa.text("is_archived = 0"),
    )


def downgrade() -> None:
    op.drop_index("uq_active_user_habit_name", table_name="habits")
    with op.batch_alter_table("habits", recreate="always") as batch_op:
        batch_op.drop_column("is_archived")
        batch_op.create_unique_constraint(
            "user_habitname_uc", ["user_id", "name"]
        )
