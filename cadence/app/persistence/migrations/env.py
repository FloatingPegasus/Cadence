import os
import sys
from logging.config import fileConfig
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from alembic import context
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from cadence.app.extensions import Base, sync_engine
from cadence.app.persistence.models import (
    AIModel,
    CarryForwardItem,
    ContinuityContext,
    ContinuityEmbedding,
    ConversationEntry,
    DailyCheckin,
    Day,
    DayContext,
    Habit,
    HabitLog,
    HourLog,
    SummaryArtifact,
    User,
    UserGoal,
    WeeklyReflection,
    Task,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
MIGRATION_ADVISORY_LOCK_KEY = 728394615


def _migration_engine():
    raw_url = os.environ.get("CADENCE_MIGRATION_DATABASE_URL", "").strip()
    if not raw_url:
        return sync_engine, False
    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("CADENCE_MIGRATION_DATABASE_URL must be PostgreSQL")
    if url.get_driver_name() != "psycopg":
        url = url.set(drivername="postgresql+psycopg")
    return create_engine(url, pool_pre_ping=True), True


def run_migrations_offline() -> None:
    engine, owned = _migration_engine()
    try:
        url = engine.url.render_as_string(hide_password=False)
        context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
        with context.begin_transaction():
            context.run_migrations()
    finally:
        if owned:
            engine.dispose()


def run_migrations_online() -> None:
    engine, owned = _migration_engine()
    try:
        with engine.connect() as connection:
            connection.execute(
                text("SELECT pg_advisory_lock(:lock_key)"),
                {"lock_key": MIGRATION_ADVISORY_LOCK_KEY},
            )
            connection.commit()
            try:
                context.configure(connection=connection, target_metadata=target_metadata)
                with context.begin_transaction():
                    context.run_migrations()
            finally:
                connection.rollback()
                connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_key)"),
                    {"lock_key": MIGRATION_ADVISORY_LOCK_KEY},
                )
                connection.commit()
    finally:
        if owned:
            engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
