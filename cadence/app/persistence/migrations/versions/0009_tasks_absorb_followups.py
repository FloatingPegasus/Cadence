"""Turn follow-ups into tasks and drop carry_forward_items.

Open follow-ups become undated tasks, completed ones completed tasks, and
dismissed ones abandoned tasks. A downgrade recreates the empty table and
leaves the moved items as tasks.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009_tasks_absorb_followups"
down_revision: Union[str, Sequence[str], None] = "0008_about_you"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO tasks (
            user_id, title, due_date, is_completed, is_abandoned,
            completed_at, created_at, updated_at
        )
        SELECT
            days.user_id,
            CASE
                WHEN length(trim(item.content)) > 200
                THEN left(trim(item.content), 199) || '…'
                ELSE trim(item.content)
            END,
            NULL,
            item.status = 'completed',
            item.status = 'released',
            CASE
                WHEN item.status = 'completed'
                THEN coalesce(item.resolved_at, item.created_at)
            END,
            item.created_at,
            coalesce(item.resolved_at, item.created_at)
        FROM carry_forward_items AS item
        JOIN days ON days.id = item.origin_day_id
        WHERE length(trim(item.content)) > 0
        ORDER BY item.id
        """
    )
    op.execute("DELETE FROM continuity_embeddings WHERE source_type = 'threads'")
    op.drop_index(
        "ix_carry_forward_items_content_trgm", table_name="carry_forward_items"
    )
    op.drop_index("ix_carry_forward_status_origin", table_name="carry_forward_items")
    op.drop_index("ix_carry_forward_origin_status", table_name="carry_forward_items")
    op.drop_table("carry_forward_items")


def downgrade() -> None:
    op.create_table(
        "carry_forward_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("origin_day_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["origin_day_id"], ["days.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_carry_forward_origin_status",
        "carry_forward_items",
        ["origin_day_id", "status"],
    )
    op.create_index(
        "ix_carry_forward_status_origin",
        "carry_forward_items",
        ["status", "origin_day_id"],
    )
    op.create_index(
        "ix_carry_forward_items_content_trgm",
        "carry_forward_items",
        ["content"],
        postgresql_using="gin",
        postgresql_ops={"content": "gin_trgm_ops"},
    )
