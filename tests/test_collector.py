"""Unit tests for ReviewCollector and RawEvidenceStore."""

from pathlib import Path
import tempfile
import unittest

from benchmark.collector.collector import ResponseValidationError, ReviewCollector
from benchmark.collector.storage import RawEvidenceStore
from benchmark.db.connection import get_connection
from benchmark.db.migrations import migrate_benchmark_db
from benchmark.db.repositories import (
    AttemptRepository,
    BatchRepository,
    CaseRepository,
    ExperimentRepository,
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
)
from benchmark.providers.base import ProviderRawResult


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.db = get_connection(":memory:")
        migrate_benchmark_db(self.db)

        self.exp_repo = ExperimentRepository(self.db)
        self.batch_repo = BatchRepository(self.db)
        self.prov_repo = ProviderRepository(self.db)
        self.case_repo = CaseRepository(self.db)
        self.attempt_repo = AttemptRepository(self.db)
        self.resp_repo = ResponseRepository(self.db)

        # Setup container entities
        self.exp_repo.create(Experiment(id="exp-1", name="Exp", scoring_protocol_version="v1"))
        self.batch_repo.create(ExecutionBatch(id="batch-1", experiment_id="exp-1", batch_name="B1", planned_attempts_count=1))
        self.prov_repo.register(Provider(id="prov-1", display_name="P1", adapter_type="mock", default_model="m1"))
        self.case_repo.register(BenchmarkCase(
            id="case-01", case_number=1, title="T", pr_description="D",
            baseline_commit="9b5ac64", target_commit="b422577", patch_relpath="cases/01/change.patch"
        ))

        self.attempt = self.attempt_repo.create(ReviewAttempt(
            id="att-col-1",
            batch_id="batch-1",
            provider_id="prov-1",
            case_id="case-01",
            context_condition=ContextCondition.CODE_ONLY,
            model_name="m1",
            settings_hash="hash",
            base_commit="9b5ac64",
            head_commit="b422577",
            status=AttemptStatus.RUNNING,
        ))

        self.tmp_dir = tempfile.TemporaryDirectory()
        self.store = RawEvidenceStore(root_dir=Path(self.tmp_dir.name))
        self.collector = ReviewCollector(self.resp_repo, self.store)

    def tearDown(self):
        self.db.close()
        self.tmp_dir.cleanup()

    def test_collect_dual_storage_success(self):
        result = ProviderRawResult(
            raw_content="### Review Analysis\nNo issues found.",
            http_status=200,
            external_id="ext-1234",
            prompt_tokens=200,
            completion_tokens=50,
            duration_ms=85,
            model_name="m1-pro",
            finish_reason="stop",
        )

        resp = self.collector.collect(self.attempt, result)

        # Verify DB record
        db_resp = self.resp_repo.get_by_attempt_id("att-col-1")
        self.assertIsNotNone(db_resp)
        self.assertEqual(db_resp.raw_content, "### Review Analysis\nNo issues found.")
        self.assertEqual(db_resp.prompt_tokens, 200)
        self.assertEqual(db_resp.completion_tokens, 50)

        # Verify File mirror
        saved_md = self.store.get_evidence("batch-1", "att-col-1")
        self.assertEqual(saved_md, "### Review Analysis\nNo issues found.")

        metadata = self.store.get_metadata("batch-1", "att-col-1")
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata["attempt_id"], "att-col-1")
        self.assertEqual(metadata["model_name"], "m1-pro")
        self.assertEqual(metadata["duration_ms"], 85)

    def test_collect_rejects_empty_response(self):
        empty_result = ProviderRawResult(raw_content="   \n  ")
        with self.assertRaises(ResponseValidationError):
            self.collector.collect(self.attempt, empty_result)


if __name__ == "__main__":
    unittest.main()
