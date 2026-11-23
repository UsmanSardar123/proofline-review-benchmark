"""Database creation, migration, and foreign-key integrity tests."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from benchmark.db.connection import get_connection
from benchmark.db.migrations import get_current_version, migrate_benchmark_db


class DatabaseFoundationTests(unittest.TestCase):
    def test_clean_creation_and_migration(self):
        con = get_connection(":memory:")
        applied = migrate_benchmark_db(con)
        self.assertEqual(applied, [1, 2])
        self.assertEqual(get_current_version(con), 2)

        # Check all 12 core benchmark tables exist
        tables = [
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
        expected_tables = sorted([
            "schema_migrations",
            "experiments",
            "execution_batches",
            "providers",
            "benchmark_cases",
            "ground_truth_defects",
            "review_attempts",
            "review_responses",
            "review_findings",
            "finding_evaluations",
            "attempt_scores",
            "run_events",
        ])
        self.assertEqual(tables, expected_tables)

    def test_migration_idempotency(self):
        con = get_connection(":memory:")
        first_run = migrate_benchmark_db(con)
        self.assertEqual(first_run, [1, 2])

        # Second run should be a no-op
        second_run = migrate_benchmark_db(con)
        self.assertEqual(second_run, [])
        self.assertEqual(get_current_version(con), 2)

    def test_foreign_key_integrity(self):
        con = get_connection(":memory:")
        migrate_benchmark_db(con)

        # Inserting a child record with invalid FK must raise IntegrityError
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute(
                "INSERT INTO execution_batches (id, experiment_id, batch_name, planned_attempts_count, status, started_at) "
                "VALUES ('b1', 'nonexistent-exp', 'Batch 1', 1, 'pending', 'now')"
            )

    def test_wal_journal_mode_on_disk(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_wal.sqlite"
            con = get_connection(db_path)
            migrate_benchmark_db(con)
            mode = con.execute("PRAGMA journal_mode").fetchone()[0]
            self.assertEqual(mode.lower(), "wal")
            con.close()


if __name__ == "__main__":
    unittest.main()
