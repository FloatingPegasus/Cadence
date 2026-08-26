"""Create the PostgreSQL schema and search extensions."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from cadence.app.persistence.models.continuity_embedding import (
    CONTINUITY_EMBEDDING_DIMENSION,
)


revision: str = "0001_postgresql_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamp_column(name: str, *, nullable: bool = True) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=nullable,
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=128), nullable=False),
        sa.Column(
            "is_verified",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "ai_processing_consent",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "ai_redaction_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "days",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("daily_note", sa.Text(), nullable=True),
        _timestamp_column("created_at"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "date", name="user_day_uc"),
    )
    op.create_index(
        "ix_days_daily_note_trgm",
        "days",
        ["daily_note"],
        postgresql_using="gin",
        postgresql_ops={"daily_note": "gin_trgm_ops"},
    )

    op.create_table(
        "habits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_active_user_habit_name",
        "habits",
        ["user_id", "name"],
        unique=True,
        postgresql_where=sa.text("is_archived = false"),
    )
    op.create_index(
        "ix_habits_user_archived_id",
        "habits",
        ["user_id", "is_archived", "id"],
    )

    op.create_table(
        "conversation_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("day_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        _timestamp_column("created_at"),
        sa.ForeignKeyConstraint(["day_id"], ["days.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_entries_day_created",
        "conversation_entries",
        ["day_id", "created_at"],
    )
    op.create_index(
        "ix_conversation_entries_content_trgm",
        "conversation_entries",
        ["content"],
        postgresql_using="gin",
        postgresql_ops={"content": "gin_trgm_ops"},
    )

    op.create_table(
        "daily_checkins",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("day_id", sa.Integer(), nullable=False),
        sa.Column("sleep_hours", sa.Float(), nullable=True),
        sa.Column("sleep_quality", sa.Integer(), nullable=True),
        sa.Column("energy_level", sa.Integer(), nullable=True),
        sa.Column("focus_quality", sa.Integer(), nullable=True),
        sa.Column("emotional_state", sa.String(length=100), nullable=True),
        sa.Column("recovery_quality", sa.Integer(), nullable=True),
        sa.Column("reentry_success", sa.Integer(), nullable=True),
        sa.Column("drift_minutes", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        _timestamp_column("created_at"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["day_id"], ["days.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day_id"),
    )

    op.create_table(
        "habit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("habit_id", sa.Integer(), nullable=False),
        sa.Column("day_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["habit_id"], ["habits.id"]),
        sa.ForeignKeyConstraint(["day_id"], ["days.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day_id", "habit_id", name="day_habit_uc"),
    )

    op.create_table(
        "carry_forward_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("origin_day_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        _timestamp_column("created_at", nullable=False),
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

    op.create_table(
        "contexts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_active_user_context_name",
        "contexts",
        ["user_id", "name"],
        unique=True,
        postgresql_where=sa.text("is_archived = false"),
    )
    op.create_index(
        "ix_contexts_user_archived_id",
        "contexts",
        ["user_id", "is_archived", "id"],
    )

    op.create_table(
        "day_contexts",
        sa.Column("day_id", sa.Integer(), nullable=False),
        sa.Column("context_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["context_id"], ["contexts.id"]),
        sa.ForeignKeyConstraint(["day_id"], ["days.id"]),
        sa.PrimaryKeyConstraint("day_id", "context_id"),
    )
    op.create_index(
        "ix_day_contexts_context_day",
        "day_contexts",
        ["context_id", "day_id"],
    )

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
        _timestamp_column("first_seen_at", nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("last_tested_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "model_id", name="provider_model_uc"),
    )

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
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["day_id"], ["days.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day_id", "kind", name="day_summary_kind_uc"),
    )
    op.create_index(
        "ix_summary_artifacts_content_trgm",
        "summary_artifacts",
        ["content"],
        postgresql_using="gin",
        postgresql_ops={"content": "gin_trgm_ops"},
    )

    op.create_table(
        "weekly_reflections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
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
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "week_start",
            name="user_weekly_reflection_uc",
        ),
    )
    op.create_index(
        "ix_weekly_reflections_content_trgm",
        "weekly_reflections",
        ["content"],
        postgresql_using="gin",
        postgresql_ops={"content": "gin_trgm_ops"},
    )

    op.create_table(
        "continuity_embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("day_id", sa.Integer(), nullable=True),
        sa.Column("source_date", sa.Date(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column(
            "embedding",
            Vector(CONTINUITY_EMBEDDING_DIMENSION),
            nullable=False,
        ),
        sa.Column(
            "is_current",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["day_id"], ["days.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "source_type",
            "source_id",
            name="user_embedding_source_uc",
        ),
    )
    op.create_index(
        "ix_continuity_embeddings_embedding_hnsw",
        "continuity_embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_where=sa.text("is_current IS TRUE"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_continuity_embeddings_embedding_hnsw",
        table_name="continuity_embeddings",
    )
    op.drop_table("continuity_embeddings")
    op.drop_index(
        "ix_weekly_reflections_content_trgm",
        table_name="weekly_reflections",
    )
    op.drop_table("weekly_reflections")
    op.drop_index(
        "ix_summary_artifacts_content_trgm",
        table_name="summary_artifacts",
    )
    op.drop_table("summary_artifacts")
    op.drop_table("ai_models")
    op.drop_index("ix_day_contexts_context_day", table_name="day_contexts")
    op.drop_table("day_contexts")
    op.drop_index("ix_contexts_user_archived_id", table_name="contexts")
    op.drop_index("uq_active_user_context_name", table_name="contexts")
    op.drop_table("contexts")
    op.drop_index("ix_carry_forward_status_origin", table_name="carry_forward_items")
    op.drop_index("ix_carry_forward_origin_status", table_name="carry_forward_items")
    op.drop_index(
        "ix_carry_forward_items_content_trgm",
        table_name="carry_forward_items",
    )
    op.drop_table("carry_forward_items")
    op.drop_index(
        "ix_conversation_entries_day_created",
        table_name="conversation_entries",
    )
    op.drop_index(
        "ix_conversation_entries_content_trgm",
        table_name="conversation_entries",
    )
    op.drop_table("habit_logs")
    op.drop_table("daily_checkins")
    op.drop_table("conversation_entries")
    op.drop_index("ix_habits_user_archived_id", table_name="habits")
    op.drop_index("uq_active_user_habit_name", table_name="habits")
    op.drop_table("habits")
    op.drop_index("ix_days_daily_note_trgm", table_name="days")
    op.drop_table("days")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
