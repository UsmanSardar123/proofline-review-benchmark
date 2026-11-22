"""Automated tests for zero-cost manual reviewer functionality: prompt generation and review ingestion."""

import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from benchmark.domain.enums import AttemptStatus, ContextCondition
from benchmark.db.connection import get_connection
from benchmark.db.migrations import migrate_benchmark_db
from benchmark.db.repositories import AttemptRepository, BatchRepository, AttemptScoreRepository, ResponseRepository
from benchmark.orchestrator.engine import BenchmarkOrchestrator
from benchmark.cli.commands import (
    cmd_prompt,
    cmd_ingest,
    cmd_run,
    cmd_show_attempt,
)


class TestPromptGeneration(unittest.TestCase):
    """Tests for benchmark prompt subcommand."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.environ.pop("BENCHMARK_EVIDENCE_DIR", None)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_prompt_stdout_valid_case(self):
        """Prompt command generates valid prompt text for case 1 without ground truth leakage."""
        rc = cmd_prompt(case=1, context="code-only", output=None)
        self.assertEqual(rc, 0)

    def test_prompt_file_output(self):
        """Prompt command writes prompt markdown to specified file."""
        out_path = Path(self.temp_dir) / "case01_prompt.md"
        rc = cmd_prompt(case="case-01", context="code-only", output=str(out_path))
        self.assertEqual(rc, 0)
        self.assertTrue(out_path.is_file())

        content = out_path.read_text(encoding="utf-8")
        self.assertIn("# Pull Request Review:", content)
        self.assertIn("```diff", content)
        self.assertIn("reports.py", content)
        self.assertIn("## Instructions", content)
        # Ground truth / defect label should NOT be leaked
        self.assertNotIn("known_defects", content.lower())
        self.assertNotIn("rubric", content.lower())

    def test_prompt_snapshot_context(self):
        """Prompt command formats code-and-snapshot context with deployment snapshot."""
        out_path = Path(self.temp_dir) / "case04_snapshot.md"
        rc = cmd_prompt(case=4, context="code-and-snapshot", output=str(out_path))
        self.assertEqual(rc, 0)
        self.assertTrue(out_path.is_file())

        content = out_path.read_text(encoding="utf-8")
        self.assertIn("## Operational & Deployment Context", content)
        self.assertIn("inventory-204", content)

    def test_prompt_custom_instructions(self):
        """Prompt command includes custom instructions when provided."""
        out_path = Path(self.temp_dir) / "custom_prompt.md"
        custom_inst = "Check specifically for SQL cursor collisions on duplicate timestamps."
        rc = cmd_prompt(case=1, context="code-only", output=str(out_path), instructions=custom_inst)
        self.assertEqual(rc, 0)

        content = out_path.read_text(encoding="utf-8")
        self.assertIn(custom_inst, content)

    def test_prompt_invalid_case(self):
        """Prompt command rejects invalid case numbers."""
        rc = cmd_prompt(case=99, context="code-only", output=None)
        self.assertEqual(rc, 1)

    def test_prompt_invalid_context(self):
        """Prompt command rejects invalid context condition."""
        rc = cmd_prompt(case=1, context="invalid-context", output=None)
        self.assertEqual(rc, 1)


class TestManualBatchScheduling(unittest.TestCase):
    """Tests for scheduling batches with --manual flag."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_manual.sqlite")

    def tearDown(self):
        os.environ.pop("BENCHMARK_EVIDENCE_DIR", None)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_manual_run_creates_pending_attempts(self):
        """Scheduling with --manual creates attempts in PENDING status without dispatching."""
        rc = cmd_run(
            experiment_id="exp-manual-01",
            batch_name="Manual Review Test Batch",
            providers="chatgpt-web,claude-web",
            cases="1,2",
            context="code-only",
            repeats=1,
            manual=True,
            db_path=self.db_path,
        )
        self.assertEqual(rc, 0)

        conn = get_connection(self.db_path)
        try:
            batch_repo = BatchRepository(conn)
            batches = batch_repo.list_for_experiment("exp-manual-01")
            self.assertEqual(len(batches), 1)
            batch = batches[0]

            att_repo = AttemptRepository(conn)
            attempts = att_repo.list_for_batch(batch.id)
            self.assertEqual(len(attempts), 4)  # 2 providers * 2 cases * 1 repeat

            for att in attempts:
                self.assertEqual(att.status, AttemptStatus.PENDING)
                self.assertIsNone(att.completed_at)
        finally:
            conn.close()


class TestReviewIngestion(unittest.TestCase):
    """Tests for benchmark ingest subcommand."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_ingest.sqlite")
        self.batch_id = "batch-ingest-test"
        os.environ["BENCHMARK_EVIDENCE_DIR"] = os.path.join(self.temp_dir, "evidence")

        # Initialize and schedule a manual batch with 1 attempt
        cmd_run(
            experiment_id=self.batch_id,
            batch_name="Ingestion Test Batch",
            providers="chatgpt-web,proofline",
            cases="1",
            context="code-only",
            repeats=1,
            manual=True,
            db_path=self.db_path,
        )

    def tearDown(self):
        os.environ.pop("BENCHMARK_EVIDENCE_DIR", None)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _get_scheduled_batch_id(self) -> str:
        conn = get_connection(self.db_path)
        try:
            batch_repo = BatchRepository(conn)
            batches = batch_repo.list_for_experiment(self.batch_id)
            return batches[0].id
        finally:
            conn.close()

    def test_successful_ingestion_and_scoring(self):
        """Ingesting a valid review marks attempt COMPLETED, records findings, and computes score."""
        review_text = """## Pull Request Review
### Findings
- **File**: `reports.py`
  **Line**: 45
  **Severity**: High
  **Description**: In `history()`, ordering by `scheduled_at DESC, id DESC` while using `WHERE scheduled_at < ?` will cause pagination anomalies or skipped records when multiple deliveries share the exact same `scheduled_at` timestamp. The cursor comparison only checks `scheduled_at` rather than a composite tuple `(scheduled_at, id)`.
"""
        review_file = Path(self.temp_dir) / "chatgpt_case1.md"
        review_file.write_text(review_text, encoding="utf-8")

        actual_batch_id = self._get_scheduled_batch_id()

        rc = cmd_ingest(
            batch_id=actual_batch_id,
            provider="chatgpt-web",
            case=1,
            file_path=str(review_file),
            context="code-only",
            model="gpt-4o-2024-11-20",
            tokens="1250,450",
            duration_ms=4200,
            force=False,
            db_path=self.db_path,
        )
        self.assertEqual(rc, 0)

        # Verify database state
        conn = get_connection(self.db_path)
        try:
            att_repo = AttemptRepository(conn)
            score_repo = AttemptScoreRepository(conn)

            attempts = att_repo.list_for_batch(actual_batch_id)
            chatgpt_att = next(a for a in attempts if a.provider_id == "chatgpt-web")
            self.assertEqual(chatgpt_att.status, AttemptStatus.COMPLETED)
            self.assertIsNotNone(chatgpt_att.completed_at)
            self.assertEqual(chatgpt_att.duration_ms, 4200)

            # Check response
            resp_repo = ResponseRepository(conn)
            resp = resp_repo.get_by_attempt_id(chatgpt_att.id)
            self.assertIsNotNone(resp)
            self.assertIn("pagination anomalies", resp.raw_content)
            self.assertEqual(resp.prompt_tokens, 1250)
            self.assertEqual(resp.completion_tokens, 450)

            # Check score
            score = score_repo.get_by_attempt_id(chatgpt_att.id)
            self.assertIsNotNone(score)
            self.assertGreaterEqual(score.tp_count, 1)
            self.assertEqual(score.fn_count, 0)
            self.assertGreater(score.recall_rate, 0.0)
        finally:
            conn.close()

    def test_duplicate_attempt_prevention(self):
        """Ingesting into an already COMPLETED attempt fails without --force."""
        review_file = Path(self.temp_dir) / "rev.md"
        review_file.write_text("Finding: issue in reports.py line 45", encoding="utf-8")
        actual_batch_id = self._get_scheduled_batch_id()

        # First ingestion -> SUCCESS
        rc1 = cmd_ingest(
            batch_id=actual_batch_id,
            provider="chatgpt-web",
            case=1,
            file_path=str(review_file),
            db_path=self.db_path,
        )
        self.assertEqual(rc1, 0)

        # Second ingestion without --force -> REJECTED (error code 1)
        rc2 = cmd_ingest(
            batch_id=actual_batch_id,
            provider="chatgpt-web",
            case=1,
            file_path=str(review_file),
            force=False,
            db_path=self.db_path,
        )
        self.assertEqual(rc2, 1)

    def test_force_overwrite_duplicate_attempt(self):
        """Ingesting with --force overwrites an already COMPLETED attempt."""
        review_file_1 = Path(self.temp_dir) / "rev1.md"
        review_file_1.write_text("No issues found. LGTM!", encoding="utf-8")
        actual_batch_id = self._get_scheduled_batch_id()

        # First ingestion
        rc1 = cmd_ingest(
            batch_id=actual_batch_id,
            provider="chatgpt-web",
            case=1,
            file_path=str(review_file_1),
            db_path=self.db_path,
        )
        self.assertEqual(rc1, 0)

        # Check initial score (should be 0 recall)
        conn = get_connection(self.db_path)
        try:
            att_repo = AttemptRepository(conn)
            score_repo = AttemptScoreRepository(conn)
            att = next(a for a in att_repo.list_for_batch(actual_batch_id) if a.provider_id == "chatgpt-web")
            sc1 = score_repo.get_by_attempt_id(att.id)
            self.assertEqual(sc1.tp_count, 0)
            self.assertEqual(sc1.fn_count, 1)
        finally:
            conn.close()

        # Second ingestion with --force and real finding
        review_file_2 = Path(self.temp_dir) / "rev2.md"
        review_file_2.write_text("Issue in reports.py line 45: scheduled_at pagination bug with cursor collision", encoding="utf-8")

        rc2 = cmd_ingest(
            batch_id=actual_batch_id,
            provider="chatgpt-web",
            case=1,
            file_path=str(review_file_2),
            force=True,
            db_path=self.db_path,
        )
        self.assertEqual(rc2, 0)

        conn = get_connection(self.db_path)
        try:
            score_repo = AttemptScoreRepository(conn)
            sc2 = score_repo.get_by_attempt_id(att.id)
            self.assertGreaterEqual(sc2.tp_count, 1)
        finally:
            conn.close()

    def test_missing_file_error(self):
        """Ingesting a non-existent file returns error code 1."""
        actual_batch_id = self._get_scheduled_batch_id()
        rc = cmd_ingest(
            batch_id=actual_batch_id,
            provider="proofline",
            case=1,
            file_path=os.path.join(self.temp_dir, "nonexistent.md"),
            db_path=self.db_path,
        )
        self.assertEqual(rc, 1)

    def test_empty_file_error(self):
        """Ingesting an empty file returns error code 1."""
        actual_batch_id = self._get_scheduled_batch_id()
        empty_file = Path(self.temp_dir) / "empty.md"
        empty_file.write_text("   \n\n  ", encoding="utf-8")

        rc = cmd_ingest(
            batch_id=actual_batch_id,
            provider="proofline",
            case=1,
            file_path=str(empty_file),
            db_path=self.db_path,
        )
        self.assertEqual(rc, 1)

    def test_nonexistent_batch_or_provider(self):
        """Ingesting for invalid batch or invalid provider returns error code 1."""
        actual_batch_id = self._get_scheduled_batch_id()
        rev_file = Path(self.temp_dir) / "valid.md"
        rev_file.write_text("Valid content", encoding="utf-8")

        rc1 = cmd_ingest(
            batch_id="invalid-batch-id",
            provider="chatgpt-web",
            case=1,
            file_path=str(rev_file),
            db_path=self.db_path,
        )
        self.assertEqual(rc1, 1)

        rc2 = cmd_ingest(
            batch_id=actual_batch_id,
            provider="nonexistent-provider",
            case=1,
            file_path=str(rev_file),
            db_path=self.db_path,
        )
        self.assertEqual(rc2, 1)

    def test_ambiguous_context_requires_explicit_flag(self):
        """If batch has both code-only and code-and-snapshot, ingest requires --context."""
        # Create a batch with BOTH contexts for case 1
        multi_batch_id = "batch-multi-context"
        cmd_run(
            experiment_id=multi_batch_id,
            batch_name="Multi Context Batch",
            providers="chatgpt-web",
            cases="1",
            context="both",  # schedules both code-only and code-and-snapshot
            repeats=1,
            manual=True,
            db_path=self.db_path,
        )

        conn = get_connection(self.db_path)
        try:
            batch_repo = BatchRepository(conn)
            actual_multi_id = batch_repo.list_for_experiment(multi_batch_id)[0].id
        finally:
            conn.close()

        rev_file = Path(self.temp_dir) / "rev.md"
        rev_file.write_text("Some review", encoding="utf-8")

        # Ingest without --context -> ambigous -> returns 1
        rc = cmd_ingest(
            batch_id=actual_multi_id,
            provider="chatgpt-web",
            case=1,
            file_path=str(rev_file),
            context=None,
            db_path=self.db_path,
        )
        self.assertEqual(rc, 1)

        # Ingest with --context code-only -> success
        rc_ok = cmd_ingest(
            batch_id=actual_multi_id,
            provider="chatgpt-web",
            case=1,
            file_path=str(rev_file),
            context="code-only",
            db_path=self.db_path,
        )
        self.assertEqual(rc_ok, 0)

    def test_show_attempt_displays_ingested_details(self):
        """show-attempt command displays metadata and score for ingested attempt."""
        review_text = "Finding in reports.py line 45: timestamp ordering cursor bug."
        rev_file = Path(self.temp_dir) / "rev.md"
        rev_file.write_text(review_text, encoding="utf-8")
        actual_batch_id = self._get_scheduled_batch_id()

        cmd_ingest(
            batch_id=actual_batch_id,
            provider="chatgpt-web",
            case=1,
            file_path=str(rev_file),
            model="gpt-4o",
            db_path=self.db_path,
        )

        conn = get_connection(self.db_path)
        try:
            att_repo = AttemptRepository(conn)
            att = next(a for a in att_repo.list_for_batch(actual_batch_id) if a.provider_id == "chatgpt-web")
            attempt_id = att.id
        finally:
            conn.close()

        rc = cmd_show_attempt(attempt_id=attempt_id, full_response=True, db_path=self.db_path)
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
