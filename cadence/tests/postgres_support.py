"""Shared PostgreSQL integration-test support.

The API tests deliberately run against the Alembic schema rather than a
metadata-created approximation.  Every test truncates application tables and
reseeds the two fixture users, while migration setup is cached per database
identity for the lifetime of the test process.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import unittest

import bcrypt
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from fastapi.testclient import TestClient

from cadence.app import app
from cadence.app.config import settings
from cadence.app.extensions import (
    Base,
    configure_pgvector_async_engine,
    get_db,
)
from cadence.app.persistence.models.habit import Habit
from cadence.app.persistence.models.user import User
from cadence.app.web.routes.auth import _create_token


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg://cadence:cadence-local-password@"
    "localhost:5432/cadence_test"
)
CONFIRM_NONDISPOSABLE_ENV = "CADENCE_CONFIRM_TEST_DATABASE"
_MIGRATED_DATABASES: set[tuple[str | None, int | None, str | None, str | None]] = set()


def _confirmation_enabled() -> bool:
    return os.getenv(CONFIRM_NONDISPOSABLE_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _database_identity(url: URL) -> tuple[str | None, int | None, str | None, str | None]:
    return url.host, url.port, url.database, url.username


def validated_test_database_url() -> str:
    """Return the explicitly selected disposable test URL.

    A runtime or migration URL is never selected as a fallback.  A non-test
    database name requires ``CADENCE_CONFIRM_TEST_DATABASE=true`` so a
    destructive test reset is always an intentional act.
    """

    raw_url = os.getenv("CADENCE_TEST_DATABASE_URL", "").strip()
    if not raw_url:
        raw_url = DEFAULT_TEST_DATABASE_URL
    try:
        parsed = make_url(raw_url)
    except Exception as error:
        raise RuntimeError(
            "CADENCE_TEST_DATABASE_URL must be a valid PostgreSQL URL"
        ) from error
    if (
        parsed.get_backend_name() != "postgresql"
        or parsed.get_driver_name() != "psycopg"
        or not parsed.database
    ):
        raise RuntimeError(
            "CADENCE_TEST_DATABASE_URL must use postgresql+psycopg and include a database"
        )
    database_name = parsed.database.casefold()
    is_disposable = database_name == "test" or database_name.endswith(
        ("_test", "-test")
    )
    if not is_disposable and not _confirmation_enabled():
        raise RuntimeError(
            "Refusing destructive tests against a non-disposable database. "
            "Set CADENCE_TEST_DATABASE_URL to a database ending in _test, "
            f"or explicitly set {CONFIRM_NONDISPOSABLE_ENV}=true."
        )

    migration_raw = os.getenv("CADENCE_MIGRATION_DATABASE_URL", "").strip()
    if migration_raw:
        try:
            migration_url = make_url(migration_raw)
        except Exception as error:
            raise RuntimeError(
                "CADENCE_MIGRATION_DATABASE_URL must be a valid PostgreSQL URL"
            ) from error
        if _database_identity(migration_url) != _database_identity(parsed):
            raise RuntimeError(
                "CADENCE_MIGRATION_DATABASE_URL must target the same database "
                "as CADENCE_TEST_DATABASE_URL during tests"
            )

    os.environ["CADENCE_DATABASE_URL"] = raw_url
    os.environ["CADENCE_MIGRATION_DATABASE_URL"] = raw_url
    return raw_url


def ensure_migrated_schema() -> None:
    """Apply Alembic once for the selected test database."""

    database_url = validated_test_database_url()
    parsed = make_url(database_url)
    identity = _database_identity(parsed)
    if identity in _MIGRATED_DATABASES:
        return
    config = Config(str(PROJECT_ROOT / "cadence" / "alembic.ini"))
    command.upgrade(config, "head")
    _MIGRATED_DATABASES.add(identity)


def _table_names() -> str:
    return ", ".join(
        f'"{table.name}"' for table in Base.metadata.sorted_tables
    )


class PostgresTestCase(unittest.TestCase):
    """Base fixture for API tests against a migrated disposable database."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        ensure_migrated_schema()
        cls.engine = create_async_engine(
            settings.database_url,
            poolclass=NullPool,
            pool_pre_ping=True,
        )
        configure_pgvector_async_engine(cls.engine)
        cls.session_factory = async_sessionmaker(
            cls.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        engine = getattr(cls, "engine", None)
        if engine is not None:
            asyncio.run(engine.dispose())
        super().tearDownClass()

    def setUp(self) -> None:
        self.original_dev_mode = settings.dev_mode
        self.original_test_mode = settings.test_mode
        self.original_dev_email = settings.dev_email
        self.original_dev_password = settings.dev_password
        self.original_ai_api_key = settings.ai_api_key
        self.original_ai_enabled = settings.ai_enabled
        self.original_frontend_base_url = settings.frontend_base_url
        self.engine = type(self).engine
        self.session_factory = type(self).session_factory

        try:
            asyncio.run(self._reset_database())
        except SQLAlchemyError as error:
            self.fail("PostgreSQL test database reset failed")
            raise error

        async def override_get_db():
            async with self.session_factory() as db:
                yield db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.alpha_headers = {
            "Authorization": f"Bearer {_create_token(1)}"
        }
        self.beta_headers = {
            "Authorization": f"Bearer {_create_token(2)}"
        }

    def tearDown(self) -> None:
        settings.dev_mode = self.original_dev_mode
        settings.test_mode = self.original_test_mode
        settings.dev_email = self.original_dev_email
        settings.dev_password = self.original_dev_password
        settings.ai_api_key = self.original_ai_api_key
        settings.ai_enabled = self.original_ai_enabled
        settings.frontend_base_url = self.original_frontend_base_url
        self.client.close()
        app.dependency_overrides.clear()

    async def _reset_database(self) -> None:
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    f"TRUNCATE {_table_names()} "
                    "RESTART IDENTITY CASCADE"
                )
            )
        async with self.session_factory() as db:
            password = bcrypt.hashpw(
                b"test-password", bcrypt.gensalt()
            ).decode()
            db.add_all(
                [
                    User(
                        id=1,
                        username="alpha",
                        email="alpha@example.com",
                        hashed_password=password,
                        is_verified=True,
                        ai_processing_consent=True,
                    ),
                    User(
                        id=2,
                        username="beta",
                        email="beta@example.com",
                        hashed_password=password,
                        is_verified=True,
                    ),
                ]
            )
            await db.commit()
            db.add_all(
                [
                    Habit(id=1, user_id=1, name="Read"),
                    Habit(id=2, user_id=2, name="Move"),
                ]
            )
            await db.commit()
            await db.execute(
                text(
                    "SELECT setval("
                    "pg_get_serial_sequence('users', 'id'), "
                    "COALESCE((SELECT MAX(id) FROM users), 1), true)"
                )
            )
            await db.execute(
                text(
                    "SELECT setval("
                    "pg_get_serial_sequence('habits', 'id'), "
                    "COALESCE((SELECT MAX(id) FROM habits), 1), true)"
                )
            )
            await db.commit()
