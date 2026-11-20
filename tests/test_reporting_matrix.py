"""Tests for scoring service, benchmark matrix generation, and report formatters."""

import json
from pathlib import Path
import tempfile
import unittest
import uuid

from benchmark.db.connection import get_connection
from benchmark.db.migrations import migrate_benchmark_db
from benchmark.db.repositories import (
    AttemptRepository,
    AttemptScoreRepository,
    BatchRepository,
    CaseRepository,
    EvaluationRepository,
    ExperimentRepository,
    FindingRepository,
    ProviderRepository,
    ResponseRepository,
)
from benchmark.domain.enums import AttemptStatus, AttemptType, ContextCondition, EvaluationClass
from benchmark.domain.models import (
    BenchmarkCase,
    ExecutionBatch,
    Experiment,
    Provider,
    ReviewAttempt,
    ReviewFinding,
    ReviewResponse,
)
from benchmark.reporting.formatters import (
    BenchmarkReportGenerator,
    CSVFormatter,
    JSONFormatter,
    MarkdownFormatter,
)
from benchmark.reporting.matrix import BenchmarkMatrixGenerator
from benchmark.scoring.service import ScoringService


class ReportingMatrixTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_reporting.sqlite"
        self.db = get_connection(self.db_path)
        migrate_benchmark_db(self.db)

        self.case_repo = CaseRepository(self.db)
        self.prov_repo = ProviderRepository(self.db)
        self.exp_repo = ExperimentRepository(self.db)
        self.batch_repo = BatchRepository(self.db)
        self.attempt_repo = AttemptRepository(self.db)
        self.response_repo = ResponseRepository(self.db)
        self.finding_repo = FindingRepository(self.db)
        self.eval_repo = EvaluationRepository(self.db)
        self.score_repo = AttemptScoreRepository(self.db)

        self.scoring_service = ScoringService(self.db)
        self.matrix_gen = BenchmarkMatrixGenerator(self.db)
        self.report_gen = BenchmarkReportGenerator(self.db)

        # Register experiment and providers
        self.exp_repo.create(Experiment(id="exp-01", name="Test Exp", scoring_protocol_version="v1.0"))
        self.prov_repo.register(Provider(id="mock-prov", display_name="Mock Reviewer", adapter_type="mock", default_model="default"))
        self.prov_repo.register(Provider(id="rabbit-prov", display_name="CodeRabbit", adapter_type="api_http", default_model="default"))

        # Register test cases
        self.case1 = self.case_repo.register(
            BenchmarkCase(
                id="case-01",
                case_number=1,
                title="Page report history",
                pr_description="Page report history",
                baseline_commit="9b5ac64",
                target_commit="target-01",
                patch_relpath="cases/01/change.patch",
            )
        )
        self.case4 = self.case_repo.register(
            BenchmarkCase(
                id="case-04",
                case_number=4,
                title="Retire legacy format",
                pr_description="Retire legacy format",
                baseline_commit="9b5ac64",
                target_commit="target-04",
                patch_relpath="cases/04/change.patch",
                has_deployment_snapshot=True,
                snapshot_content="Elm workers-17 active",
            )
        )
        self.case7 = self.case_repo.register(
            BenchmarkCase(
                id="case-07",
                case_number=7,
                title="Index pending deliveries",
                pr_description="Index pending deliveries",
                baseline_commit="9b5ac64",
                target_commit="target-07",
                patch_relpath="cases/07/change.patch",
            )
        )

        self.scoring_service.seed_ground_truths(["case-01", "case-04", "case-07"])

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_scoring_true_positive_and_clean_pass(self):
        """Verify accurate scoring for true positive and clean pass cases."""
        batch = self.batch_repo.create(
            ExecutionBatch(id="batch-01", experiment_id="exp-01", batch_name="Test Batch", planned_attempts_count=2)
        )

        # 1. Attempt for Case 01 with a True Positive finding
        att1 = self.attempt_repo.create(
            ReviewAttempt(
                id="att-01",
                batch_id=batch.id,
                provider_id="mock-prov",
                case_id="case-01",
                context_condition=ContextCondition.CODE_ONLY,
                attempt_type=AttemptType.INITIAL,
                attempt_number=1,
                status=AttemptStatus.COMPLETED,
                model_name="test-model",
                settings_hash="hash-1",
                base_commit="9b5ac64",
                head_commit="target-01",
            )
        )
        resp1 = self.response_repo.save(
            ReviewResponse(id="resp-01", attempt_id=att1.id, raw_content="Found cursor tie-break pagination bug")
        )
        self.finding_repo.save(
            ReviewFinding(
                id="find-01",
                response_id=resp1.id,
                attempt_id=att1.id,
                file_path="reports.py",
                line_start=45,
                reported_severity="critical",
                summary="Cursor pagination by scheduled_at will skip duplicate items",
            )
        )

        score1 = self.scoring_service.evaluate_attempt(att1.id)
        self.assertEqual(score1.tp_count, 1)
        self.assertEqual(score1.fp_count, 0)
        self.assertEqual(score1.fn_count, 0)
        self.assertEqual(score1.precision_rate, 1.0)
        self.assertEqual(score1.recall_rate, 1.0)
        self.assertEqual(score1.f1_metric, 1.0)
        self.assertTrue(score1.passed_cleanly)

        # 2. Attempt for Case 07 (Clean PR) with no defect findings
        att2 = self.attempt_repo.create(
            ReviewAttempt(
                id="att-02",
                batch_id=batch.id,
                provider_id="mock-prov",
                case_id="case-07",
                context_condition=ContextCondition.CODE_ONLY,
                attempt_type=AttemptType.INITIAL,
                attempt_number=1,
                status=AttemptStatus.COMPLETED,
                model_name="test-model",
                settings_hash="hash-1",
                base_commit="9b5ac64",
                head_commit="target-07",
            )
        )
        self.response_repo.save(
            ReviewResponse(id="resp-02", attempt_id=att2.id, raw_content="LGTM! Clean index addition.")
        )
        score2 = self.scoring_service.evaluate_attempt(att2.id)
        self.assertEqual(score2.tp_count, 0)
        self.assertEqual(score2.fp_count, 0)
        self.assertEqual(score2.fn_count, 0)
        self.assertEqual(score2.f1_metric, 1.0)
        self.assertTrue(score2.passed_cleanly)

    def test_scoring_evidence_citation_and_ablation(self):
        """Verify deployment evidence citation detection in Case 04."""
        batch = self.batch_repo.create(
            ExecutionBatch(id="batch-02", experiment_id="exp-01", batch_name="Ablation Batch", planned_attempts_count=2)
        )

        # Code-only attempt without evidence
        att_code = self.attempt_repo.create(
            ReviewAttempt(
                id="att-c4-code",
                batch_id=batch.id,
                provider_id="rabbit-prov",
                case_id="case-04",
                context_condition=ContextCondition.CODE_ONLY,
                attempt_type=AttemptType.INITIAL,
                attempt_number=1,
                status=AttemptStatus.COMPLETED,
                model_name="default",
                settings_hash="hash-1",
                base_commit="9b5ac64",
                head_commit="target-04",
            )
        )
        resp_c = self.response_repo.save(ReviewResponse(id="resp-c", attempt_id=att_code.id, raw_content="Dropping column"))
        self.finding_repo.save(
            ReviewFinding(
                id="f-c",
                response_id=resp_c.id,
                attempt_id=att_code.id,
                file_path="migrations/002_retire_format.sql",
                summary="Dropping legacy_format column may affect queries",
                reported_severity="warning",
            )
        )
        self.scoring_service.evaluate_attempt(att_code.id)

        # Code-plus-snapshot attempt with Elm workers-17 evidence
        att_snap = self.attempt_repo.create(
            ReviewAttempt(
                id="att-c4-snap",
                batch_id=batch.id,
                provider_id="rabbit-prov",
                case_id="case-04",
                context_condition=ContextCondition.CODE_AND_SNAPSHOT,
                attempt_type=AttemptType.INITIAL,
                attempt_number=1,
                status=AttemptStatus.COMPLETED,
                model_name="default",
                settings_hash="hash-1",
                base_commit="9b5ac64",
                head_commit="target-04",
            )
        )
        resp_s = self.response_repo.save(ReviewResponse(id="resp-s", attempt_id=att_snap.id, raw_content="Elm inventory failure"))
        self.finding_repo.save(
            ReviewFinding(
                id="f-s",
                response_id=resp_s.id,
                attempt_id=att_snap.id,
                file_path="migrations/002_retire_format.sql",
                summary="Dropping legacy_format column breaks active Elm site workers running workers-17",
                reported_severity="critical",
            )
        )
        self.scoring_service.evaluate_attempt(att_snap.id)

        # Check evaluations for evidence citation
        evals_snap = self.eval_repo.list_for_attempt(att_snap.id)
        self.assertTrue(evals_snap[0].cites_deployment_evidence)

        # Check ablation matrix generator
        ablation = self.matrix_gen.generate_ablation_matrix(batch.id, target_case_ids=["case-04"])
        self.assertEqual(len(ablation.rows), 1)
        row = ablation.rows[0]
        self.assertEqual(row.provider_id, "rabbit-prov")
        self.assertEqual(row.case_id, "case-04")
        self.assertTrue(row.snapshot_cites_evidence)
        self.assertTrue(row.evidence_gain)

    def test_matrix_and_denominator_generation(self):
        """Verify provider vs case matrix and denominator summary calculations."""
        batch = self.batch_repo.create(
            ExecutionBatch(id="batch-03", experiment_id="exp-01", batch_name="Matrix Batch", planned_attempts_count=4)
        )

        # Create 1 completed and 1 quota exhausted attempt
        att_comp = self.attempt_repo.create(
            ReviewAttempt(
                id="att-m-comp",
                batch_id=batch.id,
                provider_id="mock-prov",
                case_id="case-01",
                context_condition=ContextCondition.CODE_ONLY,
                attempt_type=AttemptType.INITIAL,
                attempt_number=1,
                status=AttemptStatus.COMPLETED,
                duration_ms=450,
                model_name="default",
                settings_hash="h1",
                base_commit="9b5ac64",
                head_commit="target-01",
            )
        )
        self.response_repo.save(ReviewResponse(id="resp-m1", attempt_id=att_comp.id, raw_content="ok"))
        self.scoring_service.evaluate_attempt(att_comp.id)

        att_quota = self.attempt_repo.create(
            ReviewAttempt(
                id="att-m-quota",
                batch_id=batch.id,
                provider_id="mock-prov",
                case_id="case-07",
                context_condition=ContextCondition.CODE_ONLY,
                attempt_type=AttemptType.INITIAL,
                attempt_number=1,
                status=AttemptStatus.QUOTA_EXHAUSTED,
                model_name="default",
                settings_hash="h1",
                base_commit="9b5ac64",
                head_commit="target-07",
            )
        )
        self.scoring_service.evaluate_attempt(att_quota.id)

        # Denominator summary
        denom = self.matrix_gen.generate_denominator_summary(batch.id)
        self.assertEqual(denom.planned_total, 4)
        self.assertEqual(denom.completed_total, 1)
        self.assertEqual(denom.quota_halted_total, 1)
        self.assertIn("mock-prov", denom.providers)

        # Provider case matrix
        matrix = self.matrix_gen.generate_provider_case_matrix(batch.id)
        self.assertIn("mock-prov", matrix.providers)
        cell_comp = matrix.matrix["mock-prov"]["case-01"]
        self.assertEqual(cell_comp.status, "COMPLETED")
        cell_quota = matrix.matrix["mock-prov"]["case-07"]
        self.assertEqual(cell_quota.status, "QUOTA_EXHAUSTED")

    def test_report_formatting(self):
        """Verify Markdown, CSV, and JSON formatting outputs."""
        batch = self.batch_repo.create(
            ExecutionBatch(id="batch-04", experiment_id="exp-01", batch_name="Format Batch", planned_attempts_count=1)
        )
        att = self.attempt_repo.create(
            ReviewAttempt(
                id="att-fmt-1",
                batch_id=batch.id,
                provider_id="mock-prov",
                case_id="case-07",
                context_condition=ContextCondition.CODE_ONLY,
                attempt_type=AttemptType.INITIAL,
                attempt_number=1,
                status=AttemptStatus.COMPLETED,
                duration_ms=250,
                model_name="default",
                settings_hash="h1",
                base_commit="9b5ac64",
                head_commit="target-07",
            )
        )
        self.response_repo.save(ReviewResponse(id="resp-fmt", attempt_id=att.id, raw_content="Approved"))
        self.scoring_service.evaluate_attempt(att.id)

        report = self.report_gen.generate_full_report(batch.id, title="Test Benchmark Run")

        # Verify markdown contents
        self.assertIn("# Test Benchmark Run", report["markdown"])
        self.assertIn("## 1. Denominator & Run Breadth", report["markdown"])
        self.assertIn("## 2. Provider vs Case Comparison Matrix", report["markdown"])
        self.assertIn("## 3. Deployment Context Ablation", report["markdown"])
        self.assertIn("mock-prov", report["markdown"])

        # Verify CSV contents
        self.assertIn("provider,case-07,precision,recall,f1_score,completed,planned", report["csv"]["matrix"])
        self.assertIn("mock-prov", report["csv"]["denominators"])

        # Verify JSON serialization
        parsed_json = json.loads(report["json"])
        self.assertEqual(parsed_json["batch_id"], batch.id)
        self.assertIn("mock-prov", parsed_json["matrix"]["providers"])


if __name__ == "__main__":
    unittest.main()
