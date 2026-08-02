import argparse
from pathlib import Path

from .app.config import settings
from .app.services.backups import (
    BackupError,
    create_backup,
    database_path_from_url,
    restore_database,
    verify_database,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cadence local database maintenance"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    backup = commands.add_parser(
        "backup",
        help="Create and verify a consistent SQLite snapshot",
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
        help="Replace the stopped local database from a verified snapshot",
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
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "verify":
            verify_database(args.path)
            print(f"Verified: {args.path.expanduser().resolve()}")
            return 0

        database_path = database_path_from_url(settings.sync_database_url)
        if args.command == "restore":
            result = restore_database(
                args.path,
                database_path,
                args.backup_dir,
                settings.resolved_runtime_lock_path,
                keep=args.keep,
            )
            print(f"Database restored: {result.path}")
            print(f"Pre-restore safety backup: {result.safety_backup}")
            return 0

        result = create_backup(
            database_path,
            args.destination,
            keep=args.keep,
        )
        print(f"Backup created: {result.path}")
        if result.removed:
            print(f"Retention removed {len(result.removed)} old backup(s)")
        return 0
    except BackupError as error:
        print(f"Backup error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
