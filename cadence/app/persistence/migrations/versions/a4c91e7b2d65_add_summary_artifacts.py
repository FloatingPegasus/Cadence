"""add editable summary artifacts

Revision ID: a4c91e7b2d65
Revises: e2b6d54f9031
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4c91e7b2d65"
down_revision: Union[str, Sequence[str], None] = "e2b6d54f9031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "summary_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("day_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=True),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_snapshot", sa.Text(), nullable=False),
        sa.Column("is_user_edited", sa.Boolean(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["day_id"], ["days.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day_id", "kind", name="day_summary_kind_uc"),
    )


def downgrade() -> None:
    op.drop_table("summary_artifacts")
