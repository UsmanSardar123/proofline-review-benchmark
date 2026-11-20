"""Comprehensive unit and edge-case tests for Phase 4 scoring, calibration, and held-out evaluation.

Tests:
1. Perfect detection (TP=1, FP=0, FN=0, F1=1.0).
2. Complete defect miss (TP=0, FP=0, FN=1, F1=0.0).
3. False positives (hallucinated bugs on clean code or non-existent defects).
4. Duplicate findings (multiple findings on same defect do not inflate TP).
5. Location tolerance matching (within tolerance vs outside tolerance).
6. Valid unexpected findings vs false positives.
7. Evidence grounding (citing Elm/Cedar inventory in snapshot cases).
8. Severity weighting and quality metrics (actionability, specificity).
9. Empty review responses.
10. Held-out partition isolation and anti-leak verification.
11. Calibration profile hashing and reproducibility.
12. Multi-provider partition comparison and report generation.
"""

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
    AttemptScore,
    BenchmarkCase,
    ExecutionBatch,
    Experiment,
    GroundTruthDefect,
    Provider,
    ReviewAttempt,
    ReviewFinding,
    ReviewResponse,
)
from benchmark.reporting.formatters import BenchmarkReportGenerator
from benchmark.reporting.matrix import BenchmarkMatrixGenerator
from benchmark.scoring.calibration import (
    CalibrationProfile,
    CalibrationRegistry,
    LENIENT_PROFILE,
    STANDARD_PROFILE,
    STRICT_PROFILE,
)
from benchmark.scoring.heldout import PartitionManager
from benchmark.scoring.matcher import FindingMatcher, MatchingConfig
from benchmark.scoring.metrics import ScoringCalculator
from benchmark.scoring.quality import FindingQualityEvaluator
from benchmark.scoring.service import ScoringService


class Phase4ScoringAndCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "p4_test.sqlite"
        self.db = get_connection(self.db_path)
        migrate_benchmark_db(self.db)

        self.exp_repo = ExperimentRepository(self.db)
        self.prov_repo = ProviderRepository(self.db)
        self.case_repo = CaseRepository(self.db)
        self.batch_repo = BatchRepository(self.db)
        self.attempt_repo = AttemptRepository(self.db)
        self.response_repo = ResponseRepository(self.db)
        self.finding_repo = FindingRepository(self.db)
        self.eval_repo = EvaluationRepository(self.db)
        self.score_repo = AttemptScoreRepository(self.db)

        self.scoring_service = ScoringService(self.db)
        self.matrix_gen = BenchmarkMatrixGenerator(self.db)
        self.report_gen = BenchmarkReportGenerator(self.db)

        self.exp = self.exp_repo.create(
            Experiment(id="exp-p4", name="Phase 4 Experiment", scoring_protocol_version="v2.0")
        )
        self.prov_repo.register(
            Provider(id="claude", display_name="Anthropic Claude", adapter_type="api_http", default_model="claude-3-5-sonnet")
        )
        self.prov_repo.register(
            Provider(id="gpt4o", display_name="OpenAI GPT-4o", adapter_type="api_http", default_model="gpt-4o")
        )

        # Register Case 1 (logic bug), Case 4 (deployment conflict), and Case 7 (clean PR)
        self.case1 = self.case_repo.register(
            BenchmarkCase(
                id="case-01",
                case_number=1,
                title="Page report history",
                pr_description="Cursor pagination",
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
                pr_description="Drop legacy format",
                baseline_commit="9b5ac64",
                target_commit="target-04",
                patch_relpath="cases/04/change.patch",
                has_deployment_snapshot=True,
                snapshot_content="Elm site workers-17 active",
            )
        )
        self.case7 = self.case_repo.register(
            BenchmarkCase(
                id="case-07",
                case_number=7,
                title="Index pending deliveries",
                pr_description="Add partial index",
                baseline_commit="9b5ac64",
                target_commit="target-07",
                patch_relpath="cases/07/change.patch",
            )
        )

        self.scoring_service.seed_ground_truths(["case-01", "case-04", "case-07"])
        self.batch = self.batch_repo.create(
            ExecutionBatch(id="batch-p4-01", experiment_id="exp-p4", batch_name="P4 Verification Batch", planned_attempts_count=6)
        )

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def _create_attempt(self, provider_id: str, case_id: str, cond: ContextCondition = ContextCondition.CODE_ONLY) -> ReviewAttempt:
        att = ReviewAttempt(
            id=f"att-{uuid.uuid4().hex[:10]}",
            batch_id=self.batch.id,
            provider_id=provider_id,
            case_id=case_id,
            context_condition=cond,
            attempt_type=AttemptType.INITIAL,
            attempt_number=1,
            status=AttemptStatus.COMPLETED,
            model_name="test-model",
            settings_hash="hash-p4",
            base_commit="9b5ac64",
            head_commit="target",
            duration_ms=250,
        )
        return self.attempt_repo.create(att)

    def test_edge_case_perfect_defect_detection(self):
        """Edge case 1: Perfect defect detection produces TP=1, FP=0, FN=0, F1=1.0."""
        att = self._create_attempt("claude", "case-01")
        resp = self.response_repo.save(ReviewResponse(id=f"resp-{att.id}", attempt_id=att.id, raw_content="Review"))
        self.finding_repo.save(
            ReviewFinding(
                id=f"f-{att.id}",
                response_id=resp.id,
                attempt_id=att.id,
                file_path="reports.py",
                line_start=45,
                reported_severity="critical",
                summary="Cursor pagination query ordered by scheduled_at without tie-breaker drops duplicate records.",
            )
        )

        score = self.scoring_service.evaluate_attempt(att.id)
        self.assertEqual(score.tp_count, 1)
        self.assertEqual(score.fp_count, 0)
        self.assertEqual(score.fn_count, 0)
        self.assertEqual(score.precision_rate, 1.0)
        self.assertEqual(score.recall_rate, 1.0)
        self.assertEqual(score.f1_metric, 1.0)
        self.assertTrue(score.passed_cleanly)

    def test_edge_case_complete_miss(self):
        """Edge case 2: Review completely misses defect, producing TP=0, FP=0, FN=1, F1=0.0."""
        att = self._create_attempt("claude", "case-01")
        self.response_repo.save(ReviewResponse(id=f"resp-{att.id}", attempt_id=att.id, raw_content="LGTM. No issues found."))

        score = self.scoring_service.evaluate_attempt(att.id)
        self.assertEqual(score.tp_count, 0)
        self.assertEqual(score.fp_count, 0)
        self.assertEqual(score.fn_count, 1)
        self.assertEqual(score.f1_metric, 0.0)
        self.assertFalse(score.passed_cleanly)

    def test_edge_case_duplicate_findings_deduplication(self):
        """Edge case 3: Multiple comments addressing the same defect do not inflate TP count."""
        att = self._create_attempt("gpt4o", "case-01")
        resp = self.response_repo.save(ReviewResponse(id=f"resp-{att.id}", attempt_id=att.id, raw_content="Review"))
        
        # Primary finding
        self.finding_repo.save(
            ReviewFinding(
                id="f-dup-1",
                response_id=resp.id,
                attempt_id=att.id,
                file_path="reports.py",
                line_start=45,
                reported_severity="critical",
                summary="Pagination cursor query skips duplicate scheduled_at items",
            )
        )
        # Duplicate finding
        self.finding_repo.save(
            ReviewFinding(
                id="f-dup-2",
                response_id=resp.id,
                attempt_id=att.id,
                file_path="reports.py",
                line_start=48,
                reported_severity="warning",
                summary="Cursor pagination tie breaker is omitted here",
            )
        )

        score = self.scoring_service.evaluate_attempt(att.id)
        self.assertEqual(score.tp_count, 1)  # Only 1 TP!
        self.assertEqual(score.fp_count, 0)

        # Check evaluations classification
        evals = self.eval_repo.list_for_attempt(att.id)
        self.assertEqual(len(evals), 2)
        classifications = [e.classification for e in evals]
        self.assertIn(EvaluationClass.TRUE_POSITIVE, classifications)
        self.assertIn(EvaluationClass.DUPLICATE, classifications)

    def test_edge_case_false_positive_on_clean_pr(self):
        """Edge case 4: False positive / hallucinated bug on clean PR penalizes precision."""
        att = self._create_attempt("claude", "case-07")
        resp = self.response_repo.save(ReviewResponse(id=f"resp-{att.id}", attempt_id=att.id, raw_content="Review"))
        self.finding_repo.save(
            ReviewFinding(
                id="f-fp-1",
                response_id=resp.id,
                attempt_id=att.id,
                file_path="migrations/002_pending_by_queue.sql",
                line_start=1,
                reported_severity="critical",
                summary="Critical SQL syntax bug will cause table deadlock and crash migration",
            )
        )

        score = self.scoring_service.evaluate_attempt(att.id)
        self.assertEqual(score.tp_count, 0)
        self.assertEqual(score.fp_count, 1)
        self.assertEqual(score.precision_rate, 0.0)
        self.assertEqual(score.f1_metric, 0.0)
        self.assertFalse(score.passed_cleanly)

    def test_edge_case_valid_unexpected_finding_vs_false_positive(self):
        """Edge case 5: Minor style/info comment is categorized as VALID_UNEXPECTED without FP penalty."""
        att = self._create_attempt("claude", "case-07")
        resp = self.response_repo.save(ReviewResponse(id=f"resp-{att.id}", attempt_id=att.id, raw_content="Review"))
        self.finding_repo.save(
            ReviewFinding(
                id="f-vuf-1",
                response_id=resp.id,
                attempt_id=att.id,
                file_path="migrations/002_pending_by_queue.sql",
                line_start=1,
                reported_severity="info",
                summary="Consider adding a comment documenting the partial index predicate for future maintainers.",
            )
        )

        score = self.scoring_service.evaluate_attempt(att.id)
        self.assertEqual(score.tp_count, 0)
        self.assertEqual(score.fp_count, 0)
        self.assertEqual(score.vuf_count, 1)
        self.assertEqual(score.f1_metric, 1.0)
        self.assertTrue(score.passed_cleanly)

    def test_edge_case_location_tolerance_matcher(self):
        """Edge case 6: Line within tolerance matches; line far outside tolerance does not."""
        matcher = FindingMatcher(MatchingConfig(line_tolerance=5, require_file_match=True))
        gt = GroundTruthDefect(
            id="gt-loc",
            case_id="case-01",
            defect_category="LOGIC_BUG",
            description="Cursor bug",
            target_file="reports.py",
            target_lines="45-50",
        )

        # Line 52 (distance 2 from 50) -> within tolerance of 5
        finding_near = ReviewFinding(
            id="f-near", response_id="r", attempt_id="a",
            file_path="reports.py", line_start=52, summary="cursor tie issue",
        )
        res_near = matcher.match(finding_near, gt, ["cursor", "tie"], [])
        self.assertTrue(res_near.is_match)
        self.assertTrue(res_near.location_matched)

        # Line 85 (distance 35 from 50) -> outside tolerance of 5
        finding_far = ReviewFinding(
            id="f-far", response_id="r", attempt_id="a",
            file_path="reports.py", line_start=85, summary="cursor tie issue",
        )
        res_far = matcher.match(finding_far, gt, ["cursor", "tie"], [])
        self.assertFalse(res_far.location_matched)

    def test_edge_case_evidence_grounding_citation(self):
        """Edge case 7: Verifies citation of Elm site workers-17 inventory in Case 04."""
        att = self._create_attempt("claude", "case-04", cond=ContextCondition.CODE_AND_SNAPSHOT)
        resp = self.response_repo.save(ReviewResponse(id=f"resp-{att.id}", attempt_id=att.id, raw_content="Review"))
        self.finding_repo.save(
            ReviewFinding(
                id="f-ev-1",
                response_id=resp.id,
                attempt_id=att.id,
                file_path="migrations/002_retire_format.sql",
                line_start=1,
                reported_severity="critical",
                summary="Dropping legacy_format column causes fatal error on Elm site workers running workers-17 polling SQL",
            )
        )

        score = self.scoring_service.evaluate_attempt(att.id)
        evals = self.eval_repo.list_for_attempt(att.id)
        self.assertEqual(len(evals), 1)
        self.assertTrue(evals[0].cites_deployment_evidence)
        self.assertEqual(score.tp_count, 1)

    def test_edge_case_finding_quality_metrics(self):
        """Edge case 8: Calculates specificity, actionability, and severity weighting."""
        evaluator = FindingQualityEvaluator()

        # High quality finding with file, line, code snippet, action keywords, and evidence
        f_high = ReviewFinding(
            id="f-q1", response_id="r", attempt_id="a",
            file_path="reports.py", line_start=45, reported_severity="critical",
            summary="Recommend replacing query with `WHERE (scheduled_at, id) < (?, ?)`",
            raw_comment_slice="Suggest updating cursor handling to avoid dropping duplicates.",
        )
        q_high = evaluator.evaluate_finding(f_high, cites_deployment_evidence=True)
        self.assertEqual(q_high.specificity_score, 1.0)
        self.assertGreaterEqual(q_high.actionability_score, 0.8)
        self.assertEqual(q_high.evidence_score, 1.0)
        self.assertEqual(q_high.severity_weight, 1.0)
        self.assertGreaterEqual(q_high.overall_quality, 0.8)

        # Low quality finding without line numbers or actionable advice
        f_low = ReviewFinding(
            id="f-q2", response_id="r", attempt_id="a",
            file_path=None, line_start=None, reported_severity="info",
            summary="Code style could be improved.",
            raw_comment_slice="",
        )
        q_low = evaluator.evaluate_finding(f_low, cites_deployment_evidence=False)
        self.assertEqual(q_low.specificity_score, 0.2)
        self.assertEqual(q_low.actionability_score, 0.2)
        self.assertEqual(q_low.evidence_score, 0.0)
        self.assertLessEqual(q_low.overall_quality, 0.3)

    def test_edge_case_empty_review_or_uncompleted_attempt(self):
        """Edge case 9: Non-completed attempts deterministically evaluate to F1=0.0."""
        att_failed = ReviewAttempt(
            id="att-failed-1", batch_id=self.batch.id, provider_id="claude",
            case_id="case-01", context_condition=ContextCondition.CODE_ONLY,
            attempt_type=AttemptType.INITIAL, attempt_number=1,
            status=AttemptStatus.FAILED, model_name="claude-3-5-sonnet",
            settings_hash="h1", base_commit="9b5ac64", head_commit="t1",
        )
        self.attempt_repo.create(att_failed)
        score_f = self.scoring_service.evaluate_attempt(att_failed.id)
        self.assertEqual(score_f.tp_count, 0)
        self.assertEqual(score_f.fn_count, 1)
        self.assertEqual(score_f.f1_metric, 0.0)

    def test_edge_case_held_out_partition_isolation_anti_leak(self):
        """Edge case 10: Anti-leak verification prevents held-out cases from leaking into calibration."""
        # Clean calibration cases
        cal_cases = ["case-01", "case-02", "case-03", "case-07"]
        self.assertTrue(PartitionManager.verify_no_leakage(cal_cases))

        # Contaminated calibration attempt with held-out case raises ValueError
        contaminated = ["case-01", "case-02", "case-04"]  # case-04 is held out!
        with self.assertRaises(ValueError) as ctx:
            PartitionManager.verify_no_leakage(contaminated)
        self.assertIn("held-out cases leaked into calibration", str(ctx.exception))

    def test_edge_case_calibration_profile_hash_reproducibility(self):
        """Edge case 11: Calibration profile hash reproduces identically for identical parameters."""
        p1 = CalibrationProfile(name="test", version="v1.0", line_tolerance=5, match_threshold=0.45)
        p2 = CalibrationProfile(name="test", version="v1.0", line_tolerance=5, match_threshold=0.45)
        p3 = CalibrationProfile(name="test", version="v1.0", line_tolerance=8, match_threshold=0.45)

        self.assertEqual(p1.profile_hash, p2.profile_hash)
        self.assertNotEqual(p1.profile_hash, p3.profile_hash)

        # Verify registry pre-registers standard, strict, and lenient
        reg = CalibrationRegistry()
        self.assertIn("standard-v1", reg.list_profiles())
        self.assertIn("strict-v1", reg.list_profiles())
        self.assertIn("lenient-v1", reg.list_profiles())

    def test_multi_provider_partition_comparison_report(self):
        """Edge case 12: Generate partition comparison matrix and full report."""
        # Claude on Case 1 (Calibration) -> TP
        att_c1 = self._create_attempt("claude", "case-01")
        resp_c1 = self.response_repo.save(ReviewResponse(id=f"resp-{att_c1.id}", attempt_id=att_c1.id, raw_content="ok"))
        self.finding_repo.save(
            ReviewFinding(id=f"f-{att_c1.id}", response_id=resp_c1.id, attempt_id=att_c1.id, file_path="reports.py", line_start=45, summary="cursor tie pagination bug")
        )
        self.scoring_service.evaluate_attempt(att_c1.id)

        # Claude on Case 4 (Held-Out) -> TP
        att_c4 = self._create_attempt("claude", "case-04", cond=ContextCondition.CODE_AND_SNAPSHOT)
        resp_c4 = self.response_repo.save(ReviewResponse(id=f"resp-{att_c4.id}", attempt_id=att_c4.id, raw_content="ok"))
        self.finding_repo.save(
            ReviewFinding(id=f"f-{att_c4.id}", response_id=resp_c4.id, attempt_id=att_c4.id, file_path="migrations/002_retire_format.sql", line_start=1, summary="dropping legacy_format breaks elm workers-17")
        )
        self.scoring_service.evaluate_attempt(att_c4.id)

        part_matrix = self.matrix_gen.generate_partition_comparison_matrix(self.batch.id)
        self.assertEqual(len(part_matrix.rows), 1)
        row = part_matrix.rows[0]
        self.assertEqual(row.provider_id, "claude")
        self.assertEqual(row.calibration_cases_count, 1)
        self.assertEqual(row.heldout_cases_count, 1)
        self.assertEqual(row.calibration_f1, 1.0)
        self.assertEqual(row.heldout_f1, 1.0)
        self.assertEqual(row.f1_delta, 0.0)
        self.assertFalse(row.is_overfitted)

        # Full report with partition table
        full_rep = self.report_gen.generate_full_report(self.batch.id, title="P4 Partition Report")
        self.assertIn("## 4. Calibration vs Held-Out Generalization", full_rep["markdown"])
        self.assertIn("claude", full_rep["csv"]["partition"])


if __name__ == "__main__":
    unittest.main()
