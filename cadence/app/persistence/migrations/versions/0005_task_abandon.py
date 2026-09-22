"""Allow tasks to be abandoned without deleting them."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_task_abandon"
down_revision: Union[str, Sequence[str], None] = "0004_guest_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column(
            "is_abandoned",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("tasks", "is_abandoned")
