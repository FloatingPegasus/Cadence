import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

if __package__:
    from .bootstrap import configure_test_environment
else:
    from bootstrap import configure_test_environment

configure_test_environment()

from cadence.app.services import backups as backup_service
from cadence.app.services.backups import (
    BackupError,
    create_backup,
    database_url_for_maintenance,
    prune_backups,
    restore_database,
    verify_database,
)


DATABASE_URL = "postgresql+psycopg://cadence:secret@localhost:5432/cadence"
TABLE_LISTING = "\n".join(
    f"123; 1259 16403 TABLE public {table} cadence"
    for table in sorted(backup_service.REQUIRED_TABLES)
) + (
    "\n123; 0 0 EXTENSION - vector cadence"
    "\n123; 0 0 EXTENSION - pg_trgm cadence"
    "\n123; 0 0 INDEX public ix_continuity_embeddings_embedding_hnsw cadence"
    "\n123; 0 0 INDEX public ix_days_daily_note_trgm cadence"
    "\n123; 0 0 INDEX public ix_conversation_entries_content_trgm cadence"
    "\n123; 0 0 INDEX public ix_summary_artifacts_content_trgm cadence"
    "\n123; 0 0 INDEX public ix_carry_forward_items_content_trgm cadence"
    "\n123; 0 0 INDEX public ix_weekly_reflections_content_trgm cadence"
)


class DatabaseBackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.backup_dir = self.root / "backups"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _run_command(
        self,
        command: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        if command[0] == "pg_dump":
            output = Path(command[command.index("--file") + 1])
            output.write_bytes(b"custom-format-dump")
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=TABLE_LISTING,
            stderr="",
        )

    def test_database_url_normalizes_psycopg_driver_and_preserves_tls(self) -> None:
        normalized = database_url_for_maintenance(
            DATABASE_URL + "?sslmode=require"
        )
        self.assertEqual(
            normalized,
            "postgresql://cadence:secret@localhost:5432/cadence?sslmode=require",
        )

    def test_database_url_rejects_non_postgresql_databases(self) -> None:
        with self.assertRaisesRegex(BackupError, "PostgreSQL"):
            database_url_for_maintenance("mysql+pymysql://user:pass@localhost/db")

    def test_backup_uses_custom_pg_dump_and_verifies_result(self) -> None:
        with patch.object(backup_service.subprocess, "run", side_effect=self._run_command) as run:
            result = create_backup(DATABASE_URL, self.backup_dir, keep=10)

        self.assertTrue(result.path.name.startswith("cadence-backup-"))
        self.assertTrue(result.path.name.endswith(".dump"))
        self.assertEqual(result.path.read_bytes(), b"custom-format-dump")
        dump_command = run.call_args_list[0].args[0]
        self.assertEqual(dump_command[0], "pg_dump")
        self.assertIn("--format=custom", dump_command)
        database_argument = dump_command[dump_command.index("--dbname") + 1]
        self.assertEqual(database_argument, "postgresql://localhost:5432/cadence")
        self.assertNotIn("cadence:", database_argument)
        self.assertNotIn("secret", database_argument)
        self.assertNotIn("***", database_argument)
        self.assertEqual(run.call_args_list[0].kwargs["env"]["PGUSER"], "cadence")
        self.assertEqual(run.call_args_list[0].kwargs["env"]["PGPASSWORD"], "secret")
        self.assertEqual(run.call_args_list[1].args[0][:2], ["pg_restore", "--list"])

    def test_retention_only_prunes_managed_dump_files(self) -> None:
        self.backup_dir.mkdir()
        unrelated = self.backup_dir / "manual-copy.dump"
        unrelated.touch()
        managed = [
            self.backup_dir / f"cadence-backup-2026010{index}T000000Z.dump"
            for index in range(3)
        ]
        for path in managed:
            path.touch()

        removed = prune_backups(self.backup_dir, keep=2)

        self.assertEqual(len(removed), 1)
        self.assertFalse(removed[0].exists())
        self.assertTrue(unrelated.exists())
        self.assertEqual(len(list(self.backup_dir.glob("cadence-backup-*.dump"))), 2)

    def test_verification_rejects_missing_empty_or_unrelated_files(self) -> None:
        missing = self.root / "missing.dump"
        with self.assertRaisesRegex(BackupError, "does not exist"):
            verify_database(missing)

        empty = self.root / "empty.dump"
        empty.touch()
        with self.assertRaisesRegex(BackupError, "empty"):
            verify_database(empty)

        unrelated = self.root / "unrelated.dump"
        unrelated.write_bytes(b"custom-format-dump")
        with patch.object(
            backup_service.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(
                ["pg_restore"],
                0,
                stdout=(
                    "123; 1259 16403 TABLE public unrelated cadence"
                ),
                stderr="",
            ),
        ):
            with self.assertRaisesRegex(BackupError, "missing tables"):
                verify_database(unrelated)

    def test_restore_creates_safety_backup_and_restores_verified_dump(self) -> None:
        source = self.root / "source.dump"
        source.write_bytes(b"custom-format-dump")

        with patch.object(backup_service.subprocess, "run", side_effect=self._run_command) as run:
            result = restore_database(
                source,
                DATABASE_URL,
                self.backup_dir,
                keep=10,
            )

        self.assertEqual(
            result.database_url,
            "postgresql://localhost:5432/cadence",
        )
        self.assertTrue(result.safety_backup.is_file())
        restore_commands = [
            call.args[0]
            for call in run.call_args_list
            if call.args[0][0] == "pg_restore" and "--clean" in call.args[0]
        ]
        self.assertEqual(len(restore_commands), 1)
        self.assertIn("--exit-on-error", restore_commands[0])
        self.assertIn("--single-transaction", restore_commands[0])
        restore_database_argument = restore_commands[0][
            restore_commands[0].index("--dbname") + 1
        ]
        self.assertEqual(
            restore_database_argument,
            "postgresql://localhost:5432/cadence",
        )
        self.assertNotIn("cadence:", restore_database_argument)
        self.assertNotIn("secret", restore_database_argument)
        self.assertNotIn("***", restore_database_argument)

    def test_failed_restore_rolls_back_with_safety_backup(self) -> None:
        source = self.root / "source.dump"
        source.write_bytes(b"custom-format-dump")
        calls = 0

        def fail_restore(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            nonlocal calls
            calls += 1
            if command[0] == "pg_dump":
                Path(command[command.index("--file") + 1]).write_bytes(
                    b"custom-format-dump"
                )
            if command[0] == "pg_restore" and "--clean" in command and calls == 4:
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="")
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=TABLE_LISTING,
                stderr="",
            )

        with patch.object(backup_service.subprocess, "run", side_effect=fail_restore):
            with self.assertRaisesRegex(BackupError, "safety backup was restored"):
                restore_database(source, DATABASE_URL, self.backup_dir)

    def test_restore_reports_when_automatic_rollback_fails(self) -> None:
        source = self.root / "source.dump"
        source.write_bytes(b"custom-format-dump")
        calls = 0

        def fail_restore_and_rollback(
            command: list[str], **_kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            nonlocal calls
            calls += 1
            if command[0] == "pg_dump":
                Path(command[command.index("--file") + 1]).write_bytes(
                    b"custom-format-dump"
                )
            if command[0] == "pg_restore" and "--clean" in command:
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="")
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=TABLE_LISTING,
                stderr="",
            )

        with patch.object(
            backup_service.subprocess,
            "run",
            side_effect=fail_restore_and_rollback,
        ):
            with self.assertRaisesRegex(BackupError, "both failed"):
                restore_database(source, DATABASE_URL, self.backup_dir)


if __name__ == "__main__":
    unittest.main()
