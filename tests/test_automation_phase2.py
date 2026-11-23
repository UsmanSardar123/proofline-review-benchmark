"""Automated unit and integration tests for Phase 2 automation pipeline."""

import os
from pathlib import Path
import tempfile
import unittest

from benchmark.db.connection import get_connection
from benchmark.db.migrations import migrate_benchmark_db
from benchmark.domain.enums import AttemptStatus, ContextCondition
from benchmark.orchestrator.automation import AutomationPipeline, IngestionCandidate


class Phase2AutomationTests(unittest.TestCase):
    """Test suite covering prompt generation, file discovery, metadata matching, ingestion, and reports."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp_dir.name)
        self.db_path = str(self.root / "test_benchmark.sqlite")
        self.prompts_dir = self.root / "prompts"
        self.reviews_dir = self.root / "reviews"
        self.reports_dir = self.root / "reports"
        self.prompts_dir.mkdir(parents=True)
        self.reviews_dir.mkdir(parents=True)
        self.reports_dir.mkdir(parents=True)

        os.environ["BENCHMARK_EVIDENCE_DIR"] = str(self.root / "evidence")

        # Initialize DB with mock experiment, batch, and attempts
        con = get_connection(self.db_path)
        migrate_benchmark_db(con)

        con.execute(
            "INSERT INTO experiments (id, name, scoring_protocol_version, status, created_at) "
            "VALUES ('exp-auto', 'Automation Exp', 'standard-v1', 'active', '2026-11-22T00:00:00Z')"
        )
        con.execute(
            "INSERT INTO execution_batches (id, experiment_id, batch_name, planned_attempts_count, status, started_at) "
            "VALUES ('batch-auto', 'exp-auto', 'Automation Batch', 2, 'pending', '2026-11-22T00:00:00Z')"
        )
        con.execute(
            "INSERT INTO providers (id, display_name, adapter_type, default_model, created_at) "
            "VALUES ('chatgpt-web', 'ChatGPT Web', 'mock', 'gpt-4o', '2026-11-22T00:00:00Z')"
        )
        con.execute(
            "INSERT INTO providers (id, display_name, adapter_type, default_model, created_at) "
            "VALUES ('claude-web', 'Claude Web', 'mock', 'claude-3-5-sonnet', '2026-11-22T00:00:00Z')"
        )
        con.execute(
            "INSERT INTO benchmark_cases (id, case_number, title, pr_description, baseline_commit, target_commit, patch_relpath, has_deployment_snapshot, created_at) "
            "VALUES ('case-01', 1, 'Page report history', 'Fix pagination', '9b5ac64', 'b422577', 'cases/01/patch.diff', 0, '2026-11-22T00:00:00Z')"
        )

        # 2 pending attempts: one for chatgpt, one for claude
        con.execute(
            "INSERT INTO review_attempts (id, batch_id, case_id, provider_id, context_condition, model_name, attempt_type, status, idempotency_key, settings_hash, base_commit, head_commit, created_at) "
            "VALUES ('att-chatgpt-1', 'batch-auto', 'case-01', 'chatgpt-web', 'CODE_ONLY', 'gpt-4o', 'INITIAL', 'PENDING', 'idem-1', 'hash-1', '9b5ac64', 'b422577', '2026-11-22T00:00:00Z')"
        )
        con.execute(
            "INSERT INTO review_attempts (id, batch_id, case_id, provider_id, context_condition, model_name, attempt_type, status, idempotency_key, settings_hash, base_commit, head_commit, created_at) "
            "VALUES ('att-claude-1', 'batch-auto', 'case-01', 'claude-web', 'CODE_ONLY', 'claude-3-5-sonnet', 'INITIAL', 'PENDING', 'idem-2', 'hash-2', '9b5ac64', 'b422577', '2026-11-22T00:00:00Z')"
        )
        con.commit()
        con.close()

        self.pipeline = AutomationPipeline(
            db_path=self.db_path,
            prompts_dir=self.prompts_dir,
            reviews_dir=self.reviews_dir,
            reports_dir=self.reports_dir,
        )

    def tearDown(self):
        import gc
        gc.collect()
        try:
            self.tmp_dir.cleanup()
        except PermissionError:
            pass
        os.environ.pop("BENCHMARK_EVIDENCE_DIR", None)

    def test_prompt_generation_and_index_creation(self):
        """Verify pipeline discovers pending attempts and generates leak-free prompts with metadata."""
        con = get_connection(self.db_path)
        att_repo = con.execute("SELECT * FROM review_attempts WHERE status = 'PENDING'").fetchall()
        con.close()

        summary = self.pipeline.run_automation_cycle(auto_ingest=False, regenerate_reports=False)
        self.assertEqual(summary.discovered_pending_attempts, 2)
        self.assertEqual(summary.prompts_generated, 2)

        prompt_files = list(self.prompts_dir.glob("case-*.md"))
        self.assertEqual(len(prompt_files), 2)

        # Check index README
        index_file = self.prompts_dir / "README.md"
        self.assertTrue(index_file.is_file())
        index_content = index_file.read_text(encoding="utf-8")
        self.assertIn("**Total Pending Attempts:** 2", index_content)
        self.assertIn("att-chatgpt-1", index_content)
        self.assertIn("att-claude-1", index_content)

    def test_file_discovery_and_metadata_matching(self):
        """Verify automatic matching of review file with explicit metadata comment block."""
        review_file = self.reviews_dir / "review_incoming.md"
        content = """<!--
  METADATA FOR AUTOMATED INGESTION:
  attempt_id: att-chatgpt-1
-->
# Pull Request Review: Page report history

### Finding 1
**Severity:** High
**File:** `reports.py`
**Line:** 45

Timestamp pagination drops records on boundary ties. Use composite cursor (scheduled_at, id).
"""
        review_file.write_text(content, encoding="utf-8")

        summary = self.pipeline.run_automation_cycle(auto_ingest=True, regenerate_prompts=True, regenerate_reports=True)
        self.assertEqual(summary.ingested_count, 1)
        self.assertEqual(summary.discovered_pending_attempts, 2)

        # Verify DB status transitioned to COMPLETED
        con = get_connection(self.db_path)
        att = con.execute("SELECT status FROM review_attempts WHERE id = 'att-chatgpt-1'").fetchone()
        self.assertEqual(att[0], "COMPLETED")

        # Verify execution_mode is 'live'
        resp = con.execute("SELECT execution_mode, raw_content FROM review_responses WHERE attempt_id = 'att-chatgpt-1'").fetchone()
        self.assertEqual(resp[0], "live")
        self.assertNotIn("<!--", resp[1])  # comment header stripped from raw content

        # Verify scores calculated
        score = con.execute("SELECT tp_count, fp_count, f1_metric FROM attempt_scores WHERE attempt_id = 'att-chatgpt-1'").fetchone()
        self.assertEqual(score[0], 1)
        self.assertEqual(score[1], 0)
        self.assertEqual(score[2], 1.0)
        con.close()

    def test_duplicate_protection_does_not_reingest(self):
        """Verify pipeline detects already-ingested content and avoids duplicate evaluations."""
        review_file = self.reviews_dir / "review_incoming.md"
        content = """<!--
  attempt_id: att-chatgpt-1
-->
# Pull Request Review

Finding in reports.py line 45: timestamp cursor collision.
"""
        review_file.write_text(content, encoding="utf-8")

        # First run: ingests
        s1 = self.pipeline.run_automation_cycle(auto_ingest=True)
        self.assertEqual(s1.ingested_count, 1)

        # Second run: detects already completed / duplicate hash, skips safely
        s2 = self.pipeline.run_automation_cycle(auto_ingest=True)
        self.assertEqual(s2.ingested_count, 0)
        self.assertEqual(len(s2.errors), 0)


if __name__ == "__main__":
    unittest.main()
