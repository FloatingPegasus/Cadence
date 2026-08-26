import argparse
import asyncio
import os
from pathlib import Path

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from .app.config import settings
from .app.extensions import configure_pgvector_async_engine
from .app.services.backups import (
    BackupError,
    create_backup,
    database_url_for_maintenance,
    restore_database,
    verify_database,
)
from .app.services.embeddings import backfill_embeddings


def _database_url() -> str:
    return (
        os.environ.get("CADENCE_MIGRATION_DATABASE_URL", "").strip()
        or settings.database_url
    )


def _migration_async_url() -> URL:
    raw_url = os.environ.get("CADENCE_MIGRATION_DATABASE_URL", "").strip()
    if not raw_url:
        raise BackupError(
            "CADENCE_MIGRATION_DATABASE_URL is required for embedding backfill"
        )
    try:
        url = make_url(raw_url)
    except Exception as error:
        raise BackupError(
            "CADENCE_MIGRATION_DATABASE_URL is not a valid PostgreSQL URL"
        ) from error
    if url.get_backend_name() != "postgresql" or not url.database:
        raise BackupError(
            "CADENCE_MIGRATION_DATABASE_URL must target PostgreSQL"
        )
    if url.get_driver_name() != "psycopg":
        url = url.set(drivername="postgresql+psycopg")
    return url


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cadence local database maintenance"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    backup = commands.add_parser(
        "backup",
        help="Create and verify a PostgreSQL custom-format snapshot",
    )
    backup.add_argument(
        "--destination",
        type=Path,
        default=settings.resolved_backup_dir,
    )
    backup.add_argument(
        "--keep",
        type=int,
        default=settings.backup_retention_count,
    )

    verify = commands.add_parser(
        "verify",
        help="Run integrity and Cadence-schema checks on a snapshot",
    )
    verify.add_argument("path", type=Path)

    restore = commands.add_parser(
        "restore",
        help="Restore a verified snapshot into a stopped PostgreSQL database",
    )
    restore.add_argument("path", type=Path)
    restore.add_argument(
        "--confirm",
        required=True,
        choices=["RESTORE"],
        help="Required destructive-action confirmation",
    )
    restore.add_argument(
        "--backup-dir",
        type=Path,
        default=settings.resolved_backup_dir,
    )
    restore.add_argument(
        "--keep",
        type=int,
        default=settings.backup_retention_count,
    )

    backfill = commands.add_parser(
        "backfill-embeddings",
        help="Retry a bounded batch of missing or stale embeddings",
    )
    backfill.add_argument("--user-id", type=int, default=None)
    backfill.add_argument("--batch-size", type=int, default=50)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "backfill-embeddings":
            async def run_backfill():
                engine = create_async_engine(
                    _migration_async_url(),
                    poolclass=NullPool,
                    pool_pre_ping=True,
                )
                configure_pgvector_async_engine(engine)
                try:
                    session_factory = async_sessionmaker(
                        engine,
                        class_=AsyncSession,
                        expire_on_commit=False,
                    )
                    async with session_factory() as db:
                        return await backfill_embeddings(
                            db,
                            user_id=args.user_id,
                            batch_size=args.batch_size,
                        )
                finally:
                    await engine.dispose()

            result = asyncio.run(run_backfill())
            print(
                "Embedding backfill: "
                f"attempted={result['attempted']} "
                f"refreshed={result['refreshed']} "
                f"failed={result['failed']}"
            )
            return 0
        if args.command == "verify":
            verify_database(args.path)
            print(f"Verified: {args.path.expanduser().resolve()}")
            return 0

        database_url = database_url_for_maintenance(_database_url())
        if args.command == "restore":
            result = restore_database(
                args.path,
                database_url,
                args.backup_dir,
                keep=args.keep,
            )
            print(f"Database restored: {result.database_url}")
            print(f"Pre-restore safety backup: {result.safety_backup}")
            return 0

        result = create_backup(
            database_url,
            args.destination,
            keep=args.keep,
        )
        print(f"Backup created: {result.path}")
        if result.removed:
            print(f"Retention removed {len(result.removed)} old backup(s)")
        return 0
    except (BackupError, ValueError) as error:
        print(f"Maintenance error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
