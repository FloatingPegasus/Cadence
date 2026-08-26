from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from sqlalchemy.engine import make_url


BACKUP_PREFIX = "cadence-backup-"
BACKUP_SUFFIX = ".dump"
REQUIRED_TABLES = {
    "alembic_version",
    "users",
    "habits",
    "days",
    "conversation_entries",
    "daily_checkins",
    "habit_logs",
    "carry_forward_items",
    "contexts",
    "day_contexts",
    "ai_models",
    "summary_artifacts",
    "weekly_reflections",
    "continuity_embeddings",
}
REQUIRED_EXTENSIONS = {"vector", "pg_trgm"}
REQUIRED_INDEXES = {
    "ix_continuity_embeddings_embedding_hnsw",
    "ix_days_daily_note_trgm",
    "ix_conversation_entries_content_trgm",
    "ix_summary_artifacts_content_trgm",
    "ix_carry_forward_items_content_trgm",
    "ix_weekly_reflections_content_trgm",
}


class BackupError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackupResult:
    path: Path
    removed: tuple[Path, ...]


@dataclass(frozen=True)
class RestoreResult:
    database_url: str
    safety_backup: Path


def database_url_for_maintenance(database_url: str) -> str:
    """Return a libpq URL suitable for pg_dump and pg_restore.

    The application may use a SQLAlchemy driver suffix such as ``+psycopg``.
    libpq utilities accept the same URL without that suffix.
    Query parameters, including TLS settings, are retained.
    """

    try:
        url = make_url(database_url.strip())
    except Exception as error:
        raise BackupError("CADENCE_DATABASE_URL is not a valid database URL") from error
    if url.get_backend_name() != "postgresql" or not url.host or not url.database:
        raise BackupError("Database maintenance requires a PostgreSQL URL")
    try:
        url.port
    except ValueError as error:
        raise BackupError("Database maintenance requires a valid PostgreSQL port") from error
    return url.set(drivername="postgresql").render_as_string(
        hide_password=False
    )


def _libpq_connection(database_url: str) -> tuple[str, dict[str, str]]:
    normalized = database_url_for_maintenance(database_url)
    url = make_url(normalized)
    environment = os.environ.copy()
    for variable in (
        "PGHOST",
        "PGPORT",
        "PGDATABASE",
        "PGUSER",
        "PGPASSWORD",
        "CADENCE_DATABASE_URL",
        "CADENCE_MIGRATION_DATABASE_URL",
    ):
        environment.pop(variable, None)
    if url.host:
        environment["PGHOST"] = url.host
    if url.port:
        environment["PGPORT"] = str(url.port)
    if url.database:
        environment["PGDATABASE"] = url.database
    if url.username is not None:
        environment["PGUSER"] = url.username
    if url.password is not None:
        environment["PGPASSWORD"] = url.password
    credential_free_url = url._replace(username=None, password=None)
    return credential_free_url.render_as_string(hide_password=False), environment


def _run_command(
    command: list[str],
    operation: str,
    *,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
    except FileNotFoundError as error:
        raise BackupError(
            f"{command[0]} is required for database {operation}"
        ) from error
    except OSError as error:
        raise BackupError(
            f"Could not run {command[0]} for database {operation}"
        ) from error
    if result.returncode != 0:
        raise BackupError(
            f"{command[0]} failed during database {operation} "
            f"(exit code {result.returncode})"
        )
    return result


def _backup_contains_table(output: str, table_name: str) -> bool:
    return any(
        "TABLE" in line
        and re.search(rf"(?:^|\s){re.escape(table_name)}(?:\s|$|;)", line)
        for line in output.splitlines()
    )


def _backup_contains_object(output: str, object_type: str, object_name: str) -> bool:
    return any(
        object_type in line
        and re.search(rf"(?:^|\s){re.escape(object_name)}(?:\s|$|;)", line)
        for line in output.splitlines()
    )


def verify_database(path: Path) -> None:
    """Verify a custom-format pg_dump and its Cadence schema entries."""

    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise BackupError(f"Backup file does not exist: {resolved}")
    if resolved.stat().st_size == 0:
        raise BackupError(f"Backup file is empty: {resolved}")

    result = _run_command(
        ["pg_restore", "--list", str(resolved)],
        "backup verification",
    )
    missing_tables = sorted(
        table
        for table in REQUIRED_TABLES
        if not _backup_contains_table(result.stdout, table)
    )
    missing_extensions = sorted(
        extension
        for extension in REQUIRED_EXTENSIONS
        if not _backup_contains_object(result.stdout, "EXTENSION", extension)
    )
    missing_indexes = sorted(
        index
        for index in REQUIRED_INDEXES
        if not _backup_contains_object(result.stdout, "INDEX", index)
    )
    if missing_tables or missing_extensions or missing_indexes:
        missing_objects = []
        if missing_tables:
            missing_objects.append("tables: " + ", ".join(missing_tables))
        if missing_extensions:
            missing_objects.append("extensions: " + ", ".join(missing_extensions))
        if missing_indexes:
            missing_objects.append("indexes: " + ", ".join(missing_indexes))
        raise BackupError(
            "Not a compatible Cadence backup; missing "
            + "; ".join(missing_objects)
        )


def prune_backups(backup_dir: Path, keep: int) -> tuple[Path, ...]:
    if keep < 1:
        raise BackupError("Backup retention must keep at least one snapshot")
    candidates = sorted(
        (
            path
            for path in backup_dir.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}")
            if path.is_file()
        ),
        reverse=True,
    )
    removed = tuple(candidates[keep:])
    for path in removed:
        path.unlink()
    return removed


def create_backup(
    database_url: str,
    backup_dir: Path,
    keep: int = 10,
) -> BackupResult:
    """Create and verify an atomic custom-format PostgreSQL snapshot."""

    libpq_url, libpq_environment = _libpq_connection(database_url)
    destination_dir = backup_dir.expanduser().resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    final_path = destination_dir / (
        f"{BACKUP_PREFIX}{timestamp}{BACKUP_SUFFIX}"
    )

    temporary = tempfile.NamedTemporaryFile(
        prefix=".cadence-backup-",
        suffix=".tmp",
        dir=destination_dir,
        delete=False,
    )
    temporary_path = Path(temporary.name)
    temporary.close()

    try:
        _run_command(
            [
                "pg_dump",
                "--format=custom",
                "--no-owner",
                "--no-acl",
                "--file",
                str(temporary_path),
                "--dbname",
                libpq_url,
            ],
            "backup",
            environment=libpq_environment,
        )
        verify_database(temporary_path)
        temporary_path.replace(final_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    removed = prune_backups(destination_dir, keep)
    return BackupResult(path=final_path, removed=removed)


def _restore_backup(
    backup_path: Path,
    database_url: str,
    operation: str,
    environment: dict[str, str],
) -> None:
    _run_command(
        [
            "pg_restore",
            "--clean",
            "--if-exists",
            "--exit-on-error",
            "--single-transaction",
            "--no-owner",
            "--no-acl",
            "--dbname",
            database_url,
            str(backup_path),
        ],
        operation,
        environment=environment,
    )


def restore_database(
    backup_path: Path,
    database_url: str,
    backup_dir: Path,
    keep: int = 10,
) -> RestoreResult:
    """Restore a verified snapshot after creating a pre-restore safety dump.

    Every running application instance must be stopped before this command is
    used. PostgreSQL coordinates concurrent clients; a local process lock would
    not coordinate instances deployed on separate machines.
    """

    source_path = backup_path.expanduser().resolve()
    verify_database(source_path)
    libpq_url, libpq_environment = _libpq_connection(database_url)
    destination_dir = backup_dir.expanduser().resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    staged = tempfile.NamedTemporaryFile(
        prefix=".cadence-restore-",
        suffix=".dump",
        dir=destination_dir,
        delete=False,
    )
    staged_path = Path(staged.name)
    staged.close()

    try:
        shutil.copyfile(source_path, staged_path)
        safety = create_backup(database_url, backup_dir, keep=keep)
        try:
            _restore_backup(
                staged_path,
                libpq_url,
                "restore",
                libpq_environment,
            )
        except BackupError as restore_error:
            try:
                _restore_backup(
                    safety.path,
                    libpq_url,
                    "automatic rollback",
                    libpq_environment,
                )
            except BackupError as rollback_error:
                raise BackupError(
                    "Restore and automatic rollback both failed. "
                    f"Safety backup: {safety.path}"
                ) from rollback_error
            raise BackupError(
                "Restore failed; the pre-restore safety backup was restored"
            ) from restore_error
    finally:
        staged_path.unlink(missing_ok=True)

    return RestoreResult(
        database_url=libpq_url,
        safety_backup=safety.path,
    )
