"""Unit tests for deterministic finding extraction and FindingRepository persistence."""

import unittest

from benchmark.db.connection import get_connection
from benchmark.db.migrations import migrate_benchmark_db
from benchmark.db.repositories import (
    AttemptRepository,
    BatchRepository,
    CaseRepository,
    ExperimentRepository,
    FindingRepository,
    ProviderRepository,
    ResponseRepository,
)
from benchmark.domain.enums import AttemptStatus, ContextCondition
from benchmark.domain.models import (
    BenchmarkCase,
    ExecutionBatch,
    Experiment,
    Provider,
    ReviewAttempt,
    ReviewFinding,
    ReviewResponse,
)
from benchmark.eval.extractor import FindingExtractor


class FindingExtractorTests(unittest.TestCase):
    def setUp(self):
        self.db = get_connection(":memory:")
        migrate_benchmark_db(self.db)
        self.exp_repo = ExperimentRepository(self.db)
        self.batch_repo = BatchRepository(self.db)
        self.prov_repo = ProviderRepository(self.db)
        self.case_repo = CaseRepository(self.db)
        self.attempt_repo = AttemptRepository(self.db)
        self.resp_repo = ResponseRepository(self.db)
        self.finding_repo = FindingRepository(self.db)
        self.extractor = FindingExtractor()

        # Setup container entities
        self.exp_repo.create(Experiment(id="exp-ext", name="Exp", scoring_protocol_version="v1"))
        self.batch_repo.create(ExecutionBatch(id="batch-ext", experiment_id="exp-ext", batch_name="B1", planned_attempts_count=1))
        self.prov_repo.register(Provider(id="prov-ext", display_name="P", adapter_type="mock", default_model="m"))
        self.case_repo.register(BenchmarkCase(
            id="case-01", case_number=1, title="T", pr_description="D",
            baseline_commit="9b5ac64", target_commit="b422577", patch_relpath="cases/01/change.patch"
        ))
        self.attempt = self.attempt_repo.create(ReviewAttempt(
            id="att-ext-1",
            batch_id="batch-ext",
            provider_id="prov-ext",
            case_id="case-01",
            context_condition=ContextCondition.CODE_ONLY,
            model_name="m",
            settings_hash="hash",
            base_commit="9b5ac64",
            head_commit="b422577",
            status=AttemptStatus.COMPLETED,
        ))

    def tearDown(self):
        self.db.close()

    def test_extract_from_bullet_markdown(self):
        markdown_review = (
            "## Review Summary\n\n"
            "- In `reports.py` at line 45: Changing the cursor comparison to `scheduled_at < ?` "
            "causes skipped rows when deliveries share identical timestamps.\n"
            "- Critical: missing unit test coverage for concurrent scheduled batches."
        )
        resp = self.resp_repo.save(ReviewResponse(
            id="resp-b1",
            attempt_id=self.attempt.id,
            raw_content=markdown_review,
        ))

        findings = self.extractor.extract_findings(resp)
        self.assertGreaterEqual(len(findings), 1)

        f1 = findings[0]
        self.assertEqual(f1.response_id, "resp-b1")
        self.assertEqual(f1.attempt_id, self.attempt.id)
        self.assertEqual(f1.file_path, "reports.py")
        self.assertEqual(f1.line_start, 45)
        self.assertIn("reports.py", f1.raw_comment_slice)

    def test_extract_from_structured_json(self):
        json_review = """
        ```json
        {
          "findings": [
            {
              "file": "reports.py",
              "line": 78,
              "severity": "critical",
              "summary": "Incomplete batch starvation",
              "description": "Leftover jobs in incomplete batches are never marked as delivered."
            }
          ]
        }
        ```
        """
        resp = self.resp_repo.save(ReviewResponse(
            id="resp-j1",
            attempt_id=self.attempt.id,
            raw_content=json_review,
        ))

        findings = self.extractor.extract_findings(resp)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].file_path, "reports.py")
        self.assertEqual(findings[0].line_start, 78)
        self.assertEqual(findings[0].reported_severity, "critical")
        self.assertEqual(findings[0].summary, "Incomplete batch starvation")

    def test_benign_approval_produces_zero_findings(self):
        lgtm_review = "## Review\nLooks good to me! No defects found in this implementation."
        resp = self.resp_repo.save(ReviewResponse(
            id="resp-clean",
            attempt_id=self.attempt.id,
            raw_content=lgtm_review,
        ))

        findings = self.extractor.extract_findings(resp)
        self.assertEqual(len(findings), 0)

    def test_finding_repository_persistence(self):
        finding = ReviewFinding(
            id="find-001",
            response_id="resp-repo-test",
            attempt_id=self.attempt.id,
            file_path="reports.py",
            line_start=55,
            reported_severity="warning",
            summary="CSV unquoted commas",
            raw_comment_slice="Joining strings directly bypasses standard csv quoting.",
        )
        # Create response first for FK
        self.resp_repo.save(ReviewResponse(id="resp-repo-test", attempt_id=self.attempt.id, raw_content="content"))

        self.finding_repo.save(finding)
        retrieved = self.finding_repo.get_by_id("find-001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.summary, "CSV unquoted commas")

        findings_for_att = self.finding_repo.list_for_attempt(self.attempt.id)
        self.assertEqual(len(findings_for_att), 1)


if __name__ == "__main__":
    unittest.main()
