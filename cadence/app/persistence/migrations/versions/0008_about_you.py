"""Add About you and keep goals to long term and short term."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_about_you"
down_revision: Union[str, Sequence[str], None] = "0007_day_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("about", sa.Text(), server_default="", nullable=False),
    )
    op.execute("UPDATE user_goals SET kind = 'long_term' WHERE kind = 'ultimate'")
    op.execute("UPDATE user_goals SET kind = 'short_term' WHERE kind = 'secondary'")


def downgrade() -> None:
    op.drop_column("users", "about")
