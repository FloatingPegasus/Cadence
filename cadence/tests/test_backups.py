import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cadence.app.services import backups as backup_service
from cadence.app.services.backups import (
    BackupError,
    create_backup,
    restore_database,
    verify_database,
)
from cadence.app.services.runtime_lock import RuntimeLock


class DatabaseBackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.database_path = self.root / "cadence.db"
        self.backup_dir = self.root / "backups"
        self.connection = sqlite3.connect(self.database_path)
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.executescript(
            """
            CREATE TABLE alembic_version (version_num TEXT PRIMARY KEY);
            CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT);
            CREATE TABLE habits (id INTEGER PRIMARY KEY, user_id INTEGER);
            CREATE TABLE days (id INTEGER PRIMARY KEY, user_id INTEGER);
            INSERT INTO alembic_version VALUES ('test-head');
            INSERT INTO users VALUES (1, 'alpha');
            """
        )
        self.connection.commit()

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary.cleanup()

    def test_backup_includes_committed_wal_content_and_verifies(self) -> None:
        self.connection.execute(
            "INSERT INTO users VALUES (2, 'from-wal')"
        )
        self.connection.commit()

        result = create_backup(
            self.database_path,
            self.backup_dir,
            keep=10,
        )

        verify_database(result.path)
        backup = sqlite3.connect(result.path)
        try:
            usernames = [
                row[0]
                for row in backup.execute(
                    "SELECT username FROM users ORDER BY id"
                )
            ]
        finally:
            backup.close()
        self.assertEqual(usernames, ["alpha", "from-wal"])
        self.assertEqual(result.removed, ())

    def test_retention_only_prunes_managed_backup_files(self) -> None:
        unrelated = self.backup_dir / "manual-copy.db"
        self.backup_dir.mkdir()
        unrelated.touch()

        create_backup(self.database_path, self.backup_dir, keep=2)
        create_backup(self.database_path, self.backup_dir, keep=2)
        result = create_backup(self.database_path, self.backup_dir, keep=2)

        managed = list(self.backup_dir.glob("cadence-backup-*.db"))
        self.assertEqual(len(managed), 2)
        self.assertEqual(len(result.removed), 1)
        self.assertTrue(unrelated.exists())

    def test_verification_rejects_corrupt_or_unrelated_files(self) -> None:
        corrupt = self.root / "corrupt.db"
        corrupt.write_text("not sqlite", encoding="utf-8")
        unrelated = self.root / "unrelated.db"
        connection = sqlite3.connect(unrelated)
        try:
            connection.execute("CREATE TABLE something_else (id INTEGER)")
        finally:
            connection.close()

        with self.assertRaises(BackupError):
            verify_database(corrupt)
        with self.assertRaises(BackupError):
            verify_database(unrelated)

    def test_restore_replaces_live_data_and_preserves_safety_backup(
        self,
    ) -> None:
        snapshot = create_backup(
            self.database_path,
            self.backup_dir,
            keep=10,
        ).path
        self.connection.execute(
            "INSERT INTO users VALUES (2, 'before-restore')"
        )
        self.connection.commit()
        self.connection.close()

        result = restore_database(
            snapshot,
            self.database_path,
            self.backup_dir,
            self.root / "runtime.lock",
            keep=10,
        )
        self.connection = sqlite3.connect(self.database_path)

        live_users = [
            row[0]
            for row in self.connection.execute(
                "SELECT username FROM users ORDER BY id"
            )
        ]
        safety = sqlite3.connect(result.safety_backup)
        try:
            safety_users = [
                row[0]
                for row in safety.execute(
                    "SELECT username FROM users ORDER BY id"
                )
            ]
        finally:
            safety.close()
        self.assertEqual(live_users, ["alpha"])
        self.assertEqual(safety_users, ["alpha", "before-restore"])

    def test_restore_refuses_schema_mismatch_without_changing_live_data(
        self,
    ) -> None:
        snapshot = create_backup(
            self.database_path,
            self.backup_dir,
            keep=10,
        ).path
        backup = sqlite3.connect(snapshot)
        try:
            backup.execute(
                "UPDATE alembic_version SET version_num = 'old-head'"
            )
            backup.commit()
        finally:
            backup.close()
        with self.assertRaisesRegex(BackupError, "schema version"):
            restore_database(
                snapshot,
                self.database_path,
                self.backup_dir,
                self.root / "runtime.lock",
            )
        users = self.connection.execute(
            "SELECT username FROM users"
        ).fetchall()
        self.assertEqual(users, [("alpha",)])

    def test_restore_refuses_while_runtime_lock_is_held(self) -> None:
        snapshot = create_backup(
            self.database_path,
            self.backup_dir,
            keep=10,
        ).path
        runtime_lock = self.root / "runtime.lock"

        with RuntimeLock(runtime_lock):
            with self.assertRaisesRegex(BackupError, "Stop the API"):
                restore_database(
                    snapshot,
                    self.database_path,
                    self.backup_dir,
                    runtime_lock,
                )

    def test_failed_restore_rolls_back_to_pre_restore_state(self) -> None:
        snapshot = create_backup(
            self.database_path,
            self.backup_dir,
            keep=10,
        ).path
        self.connection.execute(
            "INSERT INTO users VALUES (2, 'must-survive')"
        )
        self.connection.commit()
        self.connection.close()
        real_install = backup_service._install_staged_database
        install_calls = 0

        def fail_after_first_install(
            staged_path: Path,
            target_path: Path,
        ) -> None:
            nonlocal install_calls
            install_calls += 1
            real_install(staged_path, target_path)
            if install_calls == 1:
                raise RuntimeError("simulated post-install failure")

        with patch.object(
            backup_service,
            "_install_staged_database",
            side_effect=fail_after_first_install,
        ):
            with self.assertRaisesRegex(BackupError, "safety backup"):
                restore_database(
                    snapshot,
                    self.database_path,
                    self.backup_dir,
                    self.root / "runtime.lock",
                )

        self.connection = sqlite3.connect(self.database_path)
        users = [
            row[0]
            for row in self.connection.execute(
                "SELECT username FROM users ORDER BY id"
            )
        ]
        self.assertEqual(users, ["alpha", "must-survive"])


if __name__ == "__main__":
    unittest.main()
