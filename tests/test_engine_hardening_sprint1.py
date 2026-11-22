"""Sprint 1 Hardening Tests: Edge cases, malformed markdown, duplicate suppression, and recovery."""

import os
from pathlib import Path
import tempfile
import unittest

from benchmark.cases.context import ContextManager
from benchmark.cases.registry import CaseRegistry
from benchmark.db.connection import get_connection
from benchmark.db.migrations import migrate_benchmark_db
from benchmark.db.repositories import (
    AttemptRepository,
    BatchRepository,
    CaseRepository,
    EvaluationRepository,
    ExperimentRepository,
    FindingRepository,
    ProviderRepository,
    ResponseRepository,
)
from benchmark.domain.enums import AttemptStatus, ContextCondition, EvaluationClass
from benchmark.domain.models import (
    BenchmarkCase,
    ExecutionBatch,
    Experiment,
    Provider,
    ReviewAttempt,
    ReviewResponse,
)
from benchmark.eval.extractor import FindingExtractor
from benchmark.orchestrator.engine import BenchmarkOrchestrator
from benchmark.scoring.calibration import CalibrationRegistry, LENIENT_PROFILE, STANDARD_PROFILE, STRICT_PROFILE
from benchmark.scoring.service import ScoringService


class EngineHardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp_dir.name) / "test_hardening.sqlite")
        os.environ["BENCHMARK_EVIDENCE_DIR"] = str(Path(self.tmp_dir.name) / "evidence")

        self.db = get_connection(self.db_path)
        migrate_benchmark_db(self.db)

        self.exp_repo = ExperimentRepository(self.db)
        self.batch_repo = BatchRepository(self.db)
        self.prov_repo = ProviderRepository(self.db)
        self.case_repo = CaseRepository(self.db)
        self.att_repo = AttemptRepository(self.db)
        self.resp_repo = ResponseRepository(self.db)
        self.find_repo = FindingRepository(self.db)
        self.eval_repo = EvaluationRepository(self.db)

        self.scoring_svc = ScoringService(self.db)
        self.scoring_svc.seed_ground_truths(["case-01", "case-02", "case-04"])

        self.exp_repo.create(Experiment(id="exp-h", name="Hardening Exp", scoring_protocol_version="v1"))
        self.batch_repo.create(ExecutionBatch(id="batch-h", experiment_id="exp-h", batch_name="Hardening Batch", planned_attempts_count=3))
        self.prov_repo.register(Provider(id="claude-web", display_name="Claude", adapter_type="api_http", default_model="claude-3-5-sonnet"))
        self.prov_repo.register(Provider(id="chatgpt-web", display_name="ChatGPT", adapter_type="api_http", default_model="gpt-4o"))
        self.case_repo.register(BenchmarkCase(id="case-01", case_number=1, title="Case 1", pr_description="Desc", baseline_commit="9b5ac64", target_commit="b422577", patch_relpath="p"))

    def tearDown(self):
        self.db.close()
        self.tmp_dir.cleanup()
        os.environ.pop("BENCHMARK_EVIDENCE_DIR", None)

    def test_malformed_markdown_line_extraction(self):
        """Verify extraction handles tildes, en-dashes, em-dashes, and prefixes."""
        extractor = FindingExtractor()
        variations = [
            ("Target: reports.py, lines ~44–49 (history)\nBug 1: Cursor pagination bug without tie-breaker.", 44, 49),
            ("In reports.py at line L42 to L50: Query drops records during timestamp pagination.", 42, 50),
            ("reports.py#L45 - Silent omission of tied records.", 45, None),
            ("Issue in reports.py approx. line 45: Sorting mismatch.", 45, None),
        ]
        for text, expected_start, expected_end in variations:
            resp = ReviewResponse(id="resp-test", attempt_id="att-test", raw_content=text, content_format="markdown")
            findings = extractor.extract_findings(resp)
            self.assertGreater(len(findings), 0, f"Failed to extract from: {text}")
            f = findings[0]
            self.assertEqual(f.file_path, "reports.py")
            self.assertEqual(f.line_start, expected_start, f"Mismatch start for: {text}")
            if expected_end:
                self.assertEqual(f.line_end, expected_end, f"Mismatch end for: {text}")

    def test_document_level_target_inheritance(self):
        """Verify findings inherit target file declared at document header."""
        extractor = FindingExtractor()
        doc = (
            "## Review for Case 01\n\n"
            "**Target:** reports.py, lines ~44–49\n\n"
            "### Bug 1: Rows skipped at page boundaries\n"
            "The filter is scheduled_at < ? without a tie-breaker.\n\n"
            "### Bug 2: Sort key mismatch\n"
            "Keyset pagination needs both keys in the where clause.\n"
        )
        resp = ReviewResponse(id="resp-doc", attempt_id="att-doc", raw_content=doc, content_format="markdown")
        findings = extractor.extract_findings(resp)
        self.assertEqual(len(findings), 2)
        for f in findings:
            self.assertEqual(f.file_path, "reports.py")
            self.assertEqual(f.line_start, 44)
            self.assertEqual(f.line_end, 49)

    def test_duplicate_finding_suppression_3_plus(self):
        """Verify 3+ redundant comments on the same defect produce exactly 1 TP and 2+ DUPLICATE."""
        att = self.att_repo.create(ReviewAttempt(
            id="att-dup-3", batch_id="batch-h", provider_id="claude-web", case_id="case-01",
            context_condition=ContextCondition.CODE_ONLY, model_name="claude-3-5-sonnet",
            settings_hash="hash", base_commit="9b5ac64", head_commit="b422577", status=AttemptStatus.COMPLETED
        ))
        redundant_review = (
            "## Findings\n\n"
            "1. reports.py:45 - Cursor pagination by scheduled_at without tie-breaker breaks when jobs share timestamp.\n\n"
            "2. reports.py:47 - Same issue: scheduled_at cursor drops rows with identical timestamp.\n\n"
            "3. reports.py:49 - Redundant note: missing secondary sort key in cursor causes data loss.\n"
        )
        resp = self.resp_repo.save(ReviewResponse(id="resp-dup-3", attempt_id=att.id, raw_content=redundant_review))
        findings = FindingExtractor().extract_findings(resp)
        self.assertEqual(len(findings), 3)
        self.find_repo.save_all(findings)

        score = self.scoring_svc.evaluate_attempt(att.id)
        evals = self.eval_repo.list_for_attempt(att.id)

        self.assertEqual(score.tp_count, 1)
        self.assertEqual(score.fp_count, 0)
        self.assertEqual(score.fn_count, 0)
        self.assertEqual(score.precision_rate, 1.0)
        self.assertEqual(score.recall_rate, 1.0)
        self.assertEqual(score.f1_metric, 1.0)

        tp_evals = [e for e in evals if e.classification == EvaluationClass.TRUE_POSITIVE]
        dup_evals = [e for e in evals if e.classification == EvaluationClass.DUPLICATE]
        self.assertEqual(len(tp_evals), 1)
        self.assertEqual(len(dup_evals), 2)

    def test_empty_and_whitespace_ingestion_rejection(self):
        """Verify orchestrator rejects empty, whitespace, and non-existent review files."""
        orchestrator = BenchmarkOrchestrator(self.db)
        att = self.att_repo.create(ReviewAttempt(
            id="att-empty", batch_id="batch-h", provider_id="claude-web", case_id="case-01",
            context_condition=ContextCondition.CODE_ONLY, model_name="claude-3-5-sonnet",
            settings_hash="hash", base_commit="9b5ac64", head_commit="b422577", status=AttemptStatus.PENDING
        ))

        with self.assertRaises(ValueError) as ctx:
            orchestrator.ingest_review(att.id, raw_content="")
        self.assertIn("Review content cannot be empty", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx2:
            orchestrator.ingest_review(att.id, raw_content="   \n\t  ")
        self.assertIn("Review content cannot be empty", str(ctx2.exception))

    def test_calibration_profile_switching(self):
        """Verify calibration registry fingerprints and dynamic profile switching."""
        cal_reg = CalibrationRegistry()
        profiles = cal_reg.list_profiles()
        self.assertIn("standard-v1", profiles)
        self.assertIn("strict-v1", profiles)
        self.assertIn("lenient-v1", profiles)

        std = cal_reg.get_profile("standard-v1")
        strict = cal_reg.get_profile("strict-v1")
        lenient = cal_reg.get_profile("lenient-v1")

        # Distinct parameter hashes
        self.assertNotEqual(std.profile_hash, strict.profile_hash)
        self.assertNotEqual(std.profile_hash, lenient.profile_hash)

        # Stricter profile requires tighter tolerance
        self.assertLess(strict.line_tolerance, std.line_tolerance)
        self.assertGreater(strict.match_threshold, std.match_threshold)

        # Dynamic service switching
        self.scoring_svc.set_calibration_profile(strict)
        self.assertEqual(self.scoring_svc.calibration_profile.name, "strict-v1")
