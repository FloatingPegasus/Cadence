"""Allow guest sessions with a nullable email."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_guest_sessions"
down_revision: Union[str, Sequence[str], None] = "0003_tasks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_guest",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(length=255),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.drop_column("users", "is_guest")
