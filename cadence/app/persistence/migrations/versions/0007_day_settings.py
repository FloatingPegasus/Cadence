"""Let each person choose when their day ends and whether days close themselves."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_day_settings"
down_revision: Union[str, Sequence[str], None] = "0006_one_log_stream"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "day_ends_at",
            sa.SmallInteger(),
            server_default="4",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "user_day_ends_at_range",
        "users",
        "day_ends_at >= 0 AND day_ends_at <= 12",
    )
    op.add_column(
        "users",
        sa.Column(
            "auto_close",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "auto_close")
    op.drop_constraint("user_day_ends_at_range", "users", type_="check")
    op.drop_column("users", "day_ends_at")
