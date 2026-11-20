"""Unit tests for Git worktree and reviewer isolation management."""

import tempfile
import unittest
from pathlib import Path

from benchmark.git.isolation import GitIsolationManager


class GitIsolationTests(unittest.TestCase):
    def setUp(self):
        self.manager = GitIsolationManager()

    def test_isolated_environment_case_01(self):
        with self.manager.isolated_context(1) as env:
            self.assertEqual(env.case_number, 1)
            self.assertEqual(env.case_id, "case-01")
            self.assertTrue(env.worktree_path.is_dir())
            self.assertNotEqual(env.base_commit_sha, env.head_commit_sha)

            # Check that only application files exist in isolated root
            root_files = set(env.files_present)
            expected_core = {"README.md", "console.py", "migrations", "reports.py"}
            self.assertEqual(root_files, expected_core)

            # Assert strict No-Leak Boundary: zero benchmark code or cases catalog
            for forbidden in GitIsolationManager.FORBIDDEN_NAMES:
                leaked = env.worktree_path / forbidden
                self.assertFalse(leaked.exists(), f"Forbidden item leaked into review tree: {forbidden}")

            # Verify isolated Git repository status is clean
            clean, violations = self.manager.verify_no_leak(env.worktree_path)
            self.assertTrue(clean)
            self.assertEqual(violations, [])

        # Verify cleanup after context exit
        self.assertFalse(env.worktree_path.exists(), "Isolated directory was not cleaned up after context exit")

    def test_isolated_environment_case_04_migration(self):
        with self.manager.isolated_context(4) as env:
            self.assertEqual(env.case_number, 4)
            # Case 04 adds 002_retire_format.sql into migrations/
            mig_002 = env.worktree_path / "migrations" / "002_retire_format.sql"
            self.assertTrue(mig_002.is_file(), "Case 04 patch migration was not applied")

            # Verify no benchmark files exist
            clean, violations = self.manager.verify_no_leak(env.worktree_path)
            self.assertTrue(clean)

    def test_no_leak_detection(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir)
            # Create benign app file
            (path / "reports.py").write_text("# report code")

            clean, violations = self.manager.verify_no_leak(path)
            self.assertTrue(clean)
            self.assertEqual(violations, [])

            # Inject forbidden benchmark catalog
            (path / "cases").mkdir()
            (path / "benchmark.sqlite").write_text("sqlite")

            clean2, violations2 = self.manager.verify_no_leak(path)
            self.assertFalse(clean2)
            self.assertEqual(len(violations2), 2)


if __name__ == "__main__":
    unittest.main()
