"""add AI privacy preferences

Revision ID: 7d2f1a8c6b04
Revises: 1b7d4a9e3c52
Create Date: 2026-07-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7d2f1a8c6b04"
down_revision: Union[str, Sequence[str], None] = "1b7d4a9e3c52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "ai_processing_consent",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        )
    )
    op.add_column(
        "users",
        sa.Column(
            "ai_redaction_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        )
    )


def downgrade() -> None:
    op.drop_column("users", "ai_redaction_enabled")
    op.drop_column("users", "ai_processing_consent")
