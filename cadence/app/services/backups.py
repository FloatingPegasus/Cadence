from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile

from sqlalchemy.engine import make_url

from .runtime_lock import RuntimeLock, RuntimeLockError

BACKUP_PREFIX = "cadence-backup-"
BACKUP_SUFFIX = ".db"
REQUIRED_TABLES = {
    "alembic_version",
    "users",
    "habits",
    "days",
}


class BackupError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackupResult:
    path: Path
    removed: tuple[Path, ...]


@dataclass(frozen=True)
class RestoreResult:
    path: Path
    safety_backup: Path


def database_path_from_url(database_url: str) -> Path:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or not url.database:
        raise BackupError("Database maintenance currently supports SQLite only")
    return Path(url.database).expanduser().resolve()


def verify_database(path: Path) -> None:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise BackupError(f"Database file does not exist: {resolved}")

    try:
        connection = sqlite3.connect(
            f"{resolved.as_uri()}?mode=ro",
            uri=True,
            timeout=5,
        )
        try:
            integrity = [
                row[0]
                for row in connection.execute("PRAGMA integrity_check")
            ]
            if integrity != ["ok"]:
                raise BackupError(
                    f"SQLite integrity check failed: {'; '.join(integrity)}"
                )
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            missing = sorted(REQUIRED_TABLES - tables)
            if missing:
                raise BackupError(
                    "Not a compatible Cadence database; missing tables: "
                    + ", ".join(missing)
                )
        finally:
            connection.close()
    except sqlite3.DatabaseError as error:
        raise BackupError(f"Could not verify SQLite database: {error}") from error


def schema_version(path: Path) -> str:
    verify_database(path)
    resolved = path.expanduser().resolve()
    try:
        connection = sqlite3.connect(
            f"{resolved.as_uri()}?mode=ro",
            uri=True,
            timeout=5,
        )
        try:
            row = connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone()
        finally:
            connection.close()
    except sqlite3.DatabaseError as error:
        raise BackupError(
            f"Could not read database schema version: {error}"
        ) from error
    if row is None or not row[0]:
        raise BackupError("Database has no Alembic schema version")
    return str(row[0])


def prune_backups(backup_dir: Path, keep: int) -> tuple[Path, ...]:
    if keep < 1:
        raise BackupError("Backup retention must keep at least one snapshot")
    candidates = sorted(
        (
            path
            for path in backup_dir.glob(
                f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}"
            )
            if path.is_file()
        ),
        reverse=True,
    )
    removed = tuple(candidates[keep:])
    for path in removed:
        path.unlink()
    return removed


def create_backup(
    database_path: Path,
    backup_dir: Path,
    keep: int = 10,
) -> BackupResult:
    source_path = database_path.expanduser().resolve()
    destination_dir = backup_dir.expanduser().resolve()
    if not source_path.is_file():
        raise BackupError(f"Source database does not exist: {source_path}")

    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    final_path = destination_dir / (
        f"{BACKUP_PREFIX}{timestamp}{BACKUP_SUFFIX}"
    )
    if final_path == source_path:
        raise BackupError("Backup destination cannot replace the live database")

    temporary = tempfile.NamedTemporaryFile(
        prefix=".cadence-backup-",
        suffix=".tmp",
        dir=destination_dir,
        delete=False,
    )
    temporary_path = Path(temporary.name)
    temporary.close()

    try:
        source = sqlite3.connect(
            f"{source_path.as_uri()}?mode=ro",
            uri=True,
            timeout=10,
        )
        destination = sqlite3.connect(temporary_path)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        verify_database(temporary_path)
        temporary_path.replace(final_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    removed = prune_backups(destination_dir, keep)
    return BackupResult(path=final_path, removed=removed)


def _staged_copy(source_path: Path, target_dir: Path) -> Path:
    temporary = tempfile.NamedTemporaryFile(
        prefix=".cadence-restore-",
        suffix=".tmp",
        dir=target_dir,
        delete=False,
    )
    temporary_path = Path(temporary.name)
    temporary.close()
    try:
        source = sqlite3.connect(
            f"{source_path.as_uri()}?mode=ro",
            uri=True,
            timeout=10,
        )
        destination = sqlite3.connect(temporary_path)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        verify_database(temporary_path)
        return temporary_path
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _install_staged_database(
    staged_path: Path,
    target_path: Path,
) -> None:
    for suffix in ("-wal", "-shm"):
        target_path.with_name(target_path.name + suffix).unlink(
            missing_ok=True
        )
    staged_path.replace(target_path)


def restore_database(
    backup_path: Path,
    database_path: Path,
    backup_dir: Path,
    runtime_lock_path: Path,
    keep: int = 10,
) -> RestoreResult:
    source_path = backup_path.expanduser().resolve()
    target_path = database_path.expanduser().resolve()
    if source_path == target_path:
        raise BackupError("Restore source cannot be the live database")
    verify_database(source_path)
    source_version = schema_version(source_path)

    try:
        runtime_lock = RuntimeLock(runtime_lock_path)
        runtime_lock.acquire()
    except RuntimeLockError as error:
        raise BackupError(str(error)) from error

    safety: BackupResult | None = None
    staged_path: Path | None = None
    try:
        verify_database(target_path)
        target_version = schema_version(target_path)
        if source_version != target_version:
            raise BackupError(
                "Backup schema version does not match the live database "
                f"({source_version} != {target_version})"
            )
        safety = create_backup(target_path, backup_dir, keep=keep)
        staged_path = _staged_copy(source_path, target_path.parent)
        try:
            _install_staged_database(staged_path, target_path)
            staged_path = None
            verify_database(target_path)
        except Exception as restore_error:
            if staged_path is not None:
                staged_path.unlink(missing_ok=True)
                staged_path = None
            try:
                rollback = _staged_copy(safety.path, target_path.parent)
                _install_staged_database(rollback, target_path)
                verify_database(target_path)
            except Exception as rollback_error:
                raise BackupError(
                    "Restore and automatic rollback both failed. "
                    f"Safety backup: {safety.path}"
                ) from rollback_error
            raise BackupError(
                "Restore failed; the pre-restore safety backup was restored"
            ) from restore_error
    finally:
        if staged_path is not None:
            staged_path.unlink(missing_ok=True)
        runtime_lock.release()

    if safety is None:
        raise BackupError("Restore did not create a safety backup")
    return RestoreResult(
        path=target_path,
        safety_backup=safety.path,
    )
