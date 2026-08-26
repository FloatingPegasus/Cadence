"""Disposable PostgreSQL support for opt-in integration tests."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Iterator
from uuid import uuid4

import psycopg
from sqlalchemy.engine import URL, make_url


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_CONFIG = PROJECT_ROOT / "cadence" / "alembic.ini"
INTEGRATION_ENV = "CADENCE_RUN_INTEGRATION"


def integration_enabled() -> bool:
    return os.environ.get(INTEGRATION_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def integration_database_url() -> URL:
    raw_url = (
        os.environ.get("CADENCE_INTEGRATION_DATABASE_URL", "").strip()
        or os.environ.get("CADENCE_TEST_DATABASE_URL", "").strip()
        or os.environ.get("CADENCE_DATABASE_URL", "").strip()
    )
    if not raw_url:
        raise RuntimeError(
            "CADENCE_INTEGRATION_DATABASE_URL or "
            "CADENCE_TEST_DATABASE_URL is required when integration tests run"
        )
    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("integration tests require a PostgreSQL URL")
    if not url.host or not url.database or not url.username:
        raise RuntimeError(
            "integration database URL must include host, database, and user"
        )
    if url.get_driver_name() != "psycopg":
        url = url.set(drivername="postgresql+psycopg")
    return url


def _admin_database_url() -> URL:
    raw_url = os.environ.get(
        "CADENCE_INTEGRATION_ADMIN_DATABASE_URL", ""
    ).strip()
    if raw_url:
        url = make_url(raw_url)
    else:
        url = integration_database_url()
        url = url.set(database="postgres")
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("integration admin URL must be PostgreSQL")
    if url.get_driver_name() != "psycopg":
        url = url.set(drivername="postgresql+psycopg")
    return url


def _sync_url(url: URL) -> str:
    return url.set(drivername="postgresql").render_as_string(
        hide_password=False
    )


def _quote_identifier(identifier: str) -> str:
    if not identifier or any(
        character
        not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
        for character in identifier
    ):
        raise ValueError("invalid PostgreSQL identifier")
    return '"' + identifier.replace('"', '""') + '"'


class DisposableDatabase:
    def __init__(self) -> None:
        base_url = integration_database_url()
        self.admin_url = _admin_database_url()
        self.name = f"cadence_it_{os.getpid()}_{uuid4().hex[:12]}"
        self.url = base_url.set(database=self.name)

    def create(self) -> None:
        database_name = _quote_identifier(self.name)
        owner = _quote_identifier(self.url.username or "")
        with psycopg.connect(_sync_url(self.admin_url), autocommit=True) as db:
            db.execute(f"CREATE DATABASE {database_name} OWNER {owner}")

    def drop(self) -> None:
        database_name = _quote_identifier(self.name)
        with psycopg.connect(_sync_url(self.admin_url), autocommit=True) as db:
            db.execute(
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (self.name,),
            )
            db.execute(f"DROP DATABASE IF EXISTS {database_name}")

    def run_alembic(self, command: str, revision: str | None = None) -> None:
        if command not in {"upgrade", "downgrade", "check"}:
            raise ValueError(f"unsupported Alembic command: {command}")
        args = [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_CONFIG), command]
        if revision is not None:
            args.append(revision)
        environment = os.environ.copy()
        database_url = self.url.render_as_string(hide_password=False)
        environment.update(
            {
                "CADENCE_TEST_MODE": "true",
                "CADENCE_SECRET_KEY": "cadence-integration-secret-key-32-bytes",
                "CADENCE_DATABASE_URL": database_url,
                "CADENCE_MIGRATION_DATABASE_URL": database_url,
                "CADENCE_TEST_DATABASE_URL": database_url,
            }
        )
        result = subprocess.run(
            args,
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"Alembic {command} {revision or ''} failed:\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )

    def async_engine(self):
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.pool import NullPool

        from cadence.app.extensions import configure_pgvector_async_engine

        engine = create_async_engine(
            self.url,
            poolclass=NullPool,
            pool_pre_ping=True,
        )
        configure_pgvector_async_engine(engine)
        return engine


@contextmanager
def disposable_database(
    *, require_pg_tools: bool = False
) -> Iterator[DisposableDatabase]:
    if require_pg_tools:
        missing = [
            tool
            for tool in ("pg_dump", "pg_restore")
            if shutil.which(tool) is None
        ]
        if missing:
            raise RuntimeError(
                "integration tests require PostgreSQL client tools: "
                + ", ".join(missing)
            )
    database = DisposableDatabase()
    database.create()
    try:
        yield database
    finally:
        database.drop()
