"""add AI model registry

Revision ID: e2b6d54f9031
Revises: c7e4a81d2f36
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2b6d54f9031"
down_revision: Union[str, Sequence[str], None] = "c7e4a81d2f36"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model_id", sa.String(length=255), nullable=False),
        sa.Column("strength_score", sa.Integer(), nullable=False),
        sa.Column("ranking_version", sa.String(length=40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("health_status", sa.String(length=30), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("last_tested_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "model_id", name="provider_model_uc"),
    )


def downgrade() -> None:
    op.drop_table("ai_models")
