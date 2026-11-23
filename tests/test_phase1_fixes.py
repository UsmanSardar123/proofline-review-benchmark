"""Regression and unit tests for Phase 1 fixes across Tasks A, D, and F."""

import unittest
from pathlib import Path
import tempfile
import os

from benchmark.domain.models import ReviewResponse
from benchmark.domain.enums import EvaluationClass
from benchmark.providers.base import ProviderConfig, ProviderAuthenticationError
from benchmark.providers.coderabbit import CodeRabbitAdapter, CodeRabbitConfig
from benchmark.providers.greptile import GreptileAdapter, GreptileConfig
from benchmark.reporting.formatters import MarkdownFormatter, OUTCOME_ABBREVIATIONS
from benchmark.reporting.matrix import (
    BenchmarkMatrixGenerator,
    MatrixCell,
    ProviderCaseMatrix,
    ProviderSummary,
)
from benchmark.scoring.heldout import PartitionManager


class Phase1RegressionTests(unittest.TestCase):
    """Tests verifying fixes for Tasks A, D, and F."""

    def test_task_a1_outcome_abbreviations_tp_not_tr(self):
        """Task A.1: Verify TRUE_POSITIVE is formatted as 'TP', not 'TR'."""
        self.assertEqual(OUTCOME_ABBREVIATIONS[EvaluationClass.TRUE_POSITIVE.value], "TP")
        self.assertEqual(OUTCOME_ABBREVIATIONS["TRUE_POSITIVE"], "TP")
        self.assertEqual(OUTCOME_ABBREVIATIONS["FALSE_POSITIVE"], "FP")
        self.assertEqual(OUTCOME_ABBREVIATIONS["FALSE_NEGATIVE"], "FN")
        self.assertEqual(OUTCOME_ABBREVIATIONS["CLEAN_PASS"], "CL")

        # Check in formatted markdown
        matrix = ProviderCaseMatrix(
            batch_id="test-batch",
            providers=["claude"],
            cases=["case-01"],
            matrix={
                "claude": {
                    "case-01": MatrixCell(
                        status="COMPLETED",
                        outcome="TRUE_POSITIVE",
                        precision=1.0,
                        recall=1.0,
                        f1_score=1.0,
                        execution_mode="live",
                    )
                }
            },
            provider_summaries={
                "claude": ProviderSummary(
                    provider_id="claude",
                    completed=1,
                    total_planned=1,
                    tp_count=1,
                    fp_count=0,
                    fn_count=0,
                    precision=1.0,
                    recall=1.0,
                    f1_score=1.0,
                )
            },
        )
        md = MarkdownFormatter.format_matrix(matrix)
        self.assertIn("TP (1.00)", md)
        self.assertNotIn("TR (1.00)", md)

    def test_task_a2_multi_context_matrix_keys_no_collision(self):
        """Task A.2: Verify multi-context evaluations (CODE_ONLY vs CODE_AND_SNAPSHOT) do not collide."""
        from benchmark.db.connection import get_connection
        from benchmark.db.migrations import migrate_benchmark_db
        from benchmark.domain.enums import AttemptStatus, ContextCondition
        from benchmark.domain.models import ExecutionBatch, ReviewAttempt, AttemptScore

        con = get_connection(":memory:")
        migrate_benchmark_db(con)

        # Insert experiment and batch
        con.execute(
            "INSERT INTO experiments (id, name, scoring_protocol_version, status, created_at) "
            "VALUES ('exp-1', 'Exp 1', 'standard-v1', 'active', '2026-11-22T00:00:00Z')"
        )
        con.execute(
            "INSERT INTO execution_batches (id, experiment_id, batch_name, planned_attempts_count, status, started_at) "
            "VALUES ('batch-test', 'exp-1', 'Batch Test', 2, 'completed', '2026-11-22T00:00:00Z')"
        )
        con.execute(
            "INSERT INTO providers (id, display_name, adapter_type, default_model, created_at) "
            "VALUES ('claude', 'Claude', 'api_http', 'claude-3-7-sonnet', '2026-11-22T00:00:00Z')"
        )
        con.execute(
            "INSERT INTO benchmark_cases (id, case_number, title, pr_description, baseline_commit, target_commit, patch_relpath, has_deployment_snapshot, created_at) "
            "VALUES ('case-04', 4, 'Case 04', 'Retire column', '9b5ac64', '420baea', 'cases/04/patch.diff', 1, '2026-11-22T00:00:00Z')"
        )

        # Insert two attempts for the same case and provider with different context conditions
        con.execute(
            "INSERT INTO review_attempts (id, batch_id, case_id, provider_id, context_condition, model_name, attempt_type, status, idempotency_key, settings_hash, base_commit, head_commit, duration_ms, created_at, started_at) "
            "VALUES ('att-1', 'batch-test', 'case-04', 'claude', 'CODE_ONLY', 'claude-3-7-sonnet', 'INITIAL', 'COMPLETED', 'idem-1', 'hash-1', '9b5ac64', '420baea', 100, '2026-11-22T00:00:00Z', '2026-11-22T00:00:00Z')"
        )
        con.execute(
            "INSERT INTO review_attempts (id, batch_id, case_id, provider_id, context_condition, model_name, attempt_type, status, idempotency_key, settings_hash, base_commit, head_commit, duration_ms, created_at, started_at) "
            "VALUES ('att-2', 'batch-test', 'case-04', 'claude', 'CODE_AND_SNAPSHOT', 'claude-3-7-sonnet', 'INITIAL', 'COMPLETED', 'idem-2', 'hash-2', '9b5ac64', '420baea', 150, '2026-11-22T00:00:00Z', '2026-11-22T00:00:00Z')"
        )

        # Insert scores: att-1 is False Negative (F1=0.0), att-2 is True Positive (F1=1.0)
        con.execute(
            "INSERT INTO attempt_scores (id, attempt_id, tp_count, fp_count, fn_count, precision_rate, recall_rate, f1_metric, passed_cleanly, computed_at) "
            "VALUES ('sc-1', 'att-1', 0, 0, 1, 0.0, 0.0, 0.0, 0, '2026-11-22T00:00:00Z')"
        )
        con.execute(
            "INSERT INTO attempt_scores (id, attempt_id, tp_count, fp_count, fn_count, precision_rate, recall_rate, f1_metric, passed_cleanly, computed_at) "
            "VALUES ('sc-2', 'att-2', 1, 0, 0, 1.0, 1.0, 1.0, 1, '2026-11-22T00:00:00Z')"
        )

        gen = BenchmarkMatrixGenerator(con)
        res = gen.generate_provider_case_matrix("batch-test")

        # Column keys must be differentiated
        self.assertIn("case-04@code", res.cases)
        self.assertIn("case-04@snap", res.cases)
        self.assertEqual(len(res.cases), 2)

        # Outcomes in matrix must not overwrite each other
        self.assertEqual(res.matrix["claude"]["case-04@code"].outcome, "FALSE_NEGATIVE")
        self.assertEqual(res.matrix["claude"]["case-04@snap"].outcome, "TRUE_POSITIVE")

    def test_task_a3_heldout_zero_count_not_overfitted(self):
        """Task A.3: When heldout_count is 0, is_overfitted must be False, not True."""
        from benchmark.domain.models import AttemptScore

        cal_scores = [
            AttemptScore(
                id="sc-cal",
                attempt_id="att-cal",
                tp_count=1,
                fp_count=0,
                fn_count=0,
                vuf_count=0,
                precision_rate=1.0,
                recall_rate=1.0,
                f1_metric=1.0,
                passed_cleanly=True,
            )
        ]
        heldout_scores = []
        report = PartitionManager.evaluate_generalization(cal_scores, heldout_scores)
        self.assertEqual(report.heldout_count, 0)
        self.assertEqual(report.calibration_count, 1)
        self.assertFalse(report.is_overfitted)
        self.assertEqual(report.generalization_delta, -1.0)

    def test_task_d_coderabbit_auto_mode_no_silent_fallback(self):
        """Task D: In auto mode without keys, raising error unless dry_run or allow_fixture_fallback."""
        from benchmark.domain.enums import ContextCondition
        from benchmark.providers.base import ReviewContext

        old_key = os.environ.pop("CODERABBIT_API_KEY", None)
        ctx = ReviewContext(
            case_id="case-01",
            case_number=1,
            pr_title="Page report history by scheduled time",
            pr_body="Fix cursor pagination",
            base_commit="9b5ac64",
            head_commit="b422577",
            context_condition=ContextCondition.CODE_ONLY,
            patch_diff="diff --git a/reports.py b/reports.py\n...",
        )
        try:
            config = CodeRabbitConfig(
                provider_id="coderabbit",
                display_name="CodeRabbit",
                default_model="coderabbit-ai",
                mode="auto",
                dry_run=False,
                allow_fixture_fallback=False,
            )
            adapter = CodeRabbitAdapter(config)
            # Must raise ProviderAuthenticationError instead of silently falling back to fixture
            with self.assertRaises(ProviderAuthenticationError):
                adapter.invoke_review(ctx)

            # When dry_run is True, fixture is permitted and tagged fixture
            config_dry = CodeRabbitConfig(
                provider_id="coderabbit",
                display_name="CodeRabbit",
                default_model="coderabbit-ai",
                mode="auto",
                dry_run=True,
                allow_fixture_fallback=False,
            )
            adapter_dry = CodeRabbitAdapter(config_dry)
            res = adapter_dry.invoke_review(ctx)
            self.assertEqual(res.execution_mode, "fixture")

        finally:
            if old_key is not None:
                os.environ["CODERABBIT_API_KEY"] = old_key

    def test_task_d_greptile_auto_mode_no_silent_fallback(self):
        """Task D: In auto mode without keys, Greptile raises error unless dry_run or allow_fixture_fallback."""
        from benchmark.domain.enums import ContextCondition
        from benchmark.providers.base import ReviewContext

        old_token = os.environ.pop("GREPTILE_API_KEY", None)
        old_github = os.environ.pop("GREPTILE_GITHUB_TOKEN", None)
        ctx = ReviewContext(
            case_id="case-01",
            case_number=1,
            pr_title="Page report history by scheduled time",
            pr_body="Fix cursor pagination",
            base_commit="9b5ac64",
            head_commit="b422577",
            context_condition=ContextCondition.CODE_ONLY,
            patch_diff="diff --git a/reports.py b/reports.py\n...",
        )
        try:
            config = GreptileConfig(
                provider_id="greptile",
                display_name="Greptile",
                default_model="greptile-ai",
                mode="auto",
                dry_run=False,
                allow_fixture_fallback=False,
            )
            adapter = GreptileAdapter(config)
            with self.assertRaises(ProviderAuthenticationError):
                adapter.invoke_review(ctx)

            config_dry = GreptileConfig(
                provider_id="greptile",
                display_name="Greptile",
                default_model="greptile-ai",
                mode="auto",
                dry_run=True,
                allow_fixture_fallback=False,
            )
            adapter_dry = GreptileAdapter(config_dry)
            res = adapter_dry.invoke_review(ctx)
            self.assertEqual(res.execution_mode, "fixture")

        finally:
            if old_token is not None:
                os.environ["GREPTILE_API_KEY"] = old_token
            if old_github is not None:
                os.environ["GREPTILE_GITHUB_TOKEN"] = old_github


if __name__ == "__main__":
    unittest.main()
