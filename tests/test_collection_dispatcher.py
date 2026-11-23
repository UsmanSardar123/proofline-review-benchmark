"""Unit and integration tests for the Automated Review Collection Dispatcher."""

import gc
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from benchmark.collector.dispatcher import CollectionDispatcher
from benchmark.db.connection import get_connection
from benchmark.db.migrations import migrate_benchmark_db
from benchmark.cli.commands import cmd_collect


class TestCollectionDispatcher(unittest.TestCase):
    """Test suite for the CollectionDispatcher and safe collection workflow."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = str(Path(self.tmp_dir.name) / "test_dispatcher.sqlite")
        con = get_connection(self.db_path)
        migrate_benchmark_db(con)

        self.batch_id = "batch-test-dispatcher"
        con.execute(
            "INSERT INTO experiments (id, name, scoring_protocol_version, status, created_at) "
            "VALUES ('test-exp', 'Test Experiment', 'standard-v1', 'active', '2026-11-22T00:00:00Z')"
        )
        con.execute(
            "INSERT INTO execution_batches (id, experiment_id, batch_name, planned_attempts_count, status, started_at) "
            "VALUES (?, 'test-exp', 'Test Batch', 3, 'pending', '2026-11-22T00:00:00Z')",
            (self.batch_id,),
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
        con.execute(
            "INSERT INTO benchmark_cases (id, case_number, title, pr_description, baseline_commit, target_commit, patch_relpath, has_deployment_snapshot, created_at) "
            "VALUES ('case-02', 2, 'Stream export', 'Stream report rows', '9b5ac64', '9d551b8', 'cases/02/patch.diff', 0, '2026-11-22T00:00:00Z')"
        )
        con.execute(
            "INSERT INTO review_attempts (id, batch_id, case_id, provider_id, context_condition, model_name, attempt_type, status, idempotency_key, settings_hash, base_commit, head_commit, created_at) "
            "VALUES ('att-d1', ?, 'case-01', 'chatgpt-web', 'CODE_ONLY', 'manual-v1', 'INITIAL', 'PENDING', 'k1', 'h1', 'c1', 'c2', '2026-11-22T00:00:00Z')",
            (self.batch_id,),
        )
        con.execute(
            "INSERT INTO review_attempts (id, batch_id, case_id, provider_id, context_condition, model_name, attempt_type, status, idempotency_key, settings_hash, base_commit, head_commit, created_at) "
            "VALUES ('att-d2', ?, 'case-01', 'claude-web', 'CODE_ONLY', 'manual-v1', 'INITIAL', 'PENDING', 'k2', 'h2', 'c1', 'c2', '2026-11-22T00:00:00Z')",
            (self.batch_id,),
        )
        con.execute(
            "INSERT INTO review_attempts (id, batch_id, case_id, provider_id, context_condition, model_name, attempt_type, status, idempotency_key, settings_hash, base_commit, head_commit, created_at) "
            "VALUES ('att-d3', ?, 'case-02', 'chatgpt-web', 'CODE_ONLY', 'manual-v1', 'INITIAL', 'COMPLETED', 'k3', 'h3', 'c1', 'c2', '2026-11-22T00:00:00Z')",
            (self.batch_id,),
        )
        con.commit()
        con.close()
        self.dispatcher = CollectionDispatcher(db_path=self.db_path)

    def tearDown(self):
        if hasattr(self, "dispatcher") and hasattr(self.dispatcher, "_conn") and self.dispatcher._conn:
            self.dispatcher._conn.close()
        gc.collect()
        try:
            self.tmp_dir.cleanup()
        except PermissionError:
            pass

    def test_create_plan_identifies_pending_attempts(self):
        plan = self.dispatcher.create_plan(batch_id=self.batch_id)
        # Should only find the 2 pending attempts (not the completed one)
        self.assertEqual(plan.total_pending, 2)
        self.assertEqual(plan.openai_attempts, 1)
        self.assertEqual(plan.anthropic_attempts, 1)
        self.assertGreater(plan.total_prompt_tokens, 0)
        self.assertGreater(plan.total_completion_tokens, 0)
        self.assertGreater(plan.total_estimated_cost_usd, 0.0)

    def test_execute_dry_run_simulation(self):
        plan = self.dispatcher.create_plan(batch_id=self.batch_id)
        res = self.dispatcher.execute_dry_run(plan)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["total_simulated"], 2)
        self.assertEqual(res["simulated_cost_usd"], 0.0)
        for r in res["results"]:
            self.assertEqual(r["status"], "VALID_DRY_RUN")
            self.assertTrue(len(r["sha256_hash"]) == 64)

    def test_safety_gate_blocks_unauthorized_call(self):
        with self.assertRaises(PermissionError):
            self.dispatcher.dispatch_authorized_collection(allow_paid_api=False)

    def test_cost_limit_blocks_exorbitant_requests(self):
        with self.assertRaises(ValueError):
            self.dispatcher.dispatch_authorized_collection(
                allow_paid_api=True, cost_limit_usd=0.00001
            )

    def test_cli_cmd_collect(self):
        # Test CLI plan mode
        code = cmd_collect(show_plan=True, db_path=self.db_path)
        self.assertEqual(code, 0)

        # Test CLI dry-run mode
        code_dry = cmd_collect(dry_run=True, db_path=self.db_path)
        self.assertEqual(code_dry, 0)

        # Test CLI blocked run mode without authorization
        code_blocked = cmd_collect(run=True, allow_paid_api=False, db_path=self.db_path)
        self.assertEqual(code_blocked, 1)


if __name__ == "__main__":
    unittest.main()
