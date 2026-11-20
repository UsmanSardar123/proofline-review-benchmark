"""Entity persistence and repository layer tests."""

import sqlite3
import unittest

from benchmark.db.connection import get_connection
from benchmark.db.migrations import migrate_benchmark_db
from benchmark.db.repositories import (
    AttemptRepository,
    BatchRepository,
    CaseRepository,
    ExperimentRepository,
    ProviderRepository,
    ResponseRepository,
    RunEventRepository,
)
from benchmark.domain.enums import AttemptStatus, AttemptType, ContextCondition
from benchmark.domain.models import (
    BenchmarkCase,
    ExecutionBatch,
    Experiment,
    Provider,
    ReviewAttempt,
    ReviewResponse,
    RunEvent,
)


class RepositoryLayerTests(unittest.TestCase):
    def setUp(self):
        self.db = get_connection(":memory:")
        migrate_benchmark_db(self.db)
        self.exp_repo = ExperimentRepository(self.db)
        self.batch_repo = BatchRepository(self.db)
        self.prov_repo = ProviderRepository(self.db)
        self.case_repo = CaseRepository(self.db)
        self.attempt_repo = AttemptRepository(self.db)
        self.response_repo = ResponseRepository(self.db)
        self.event_repo = RunEventRepository(self.db)

    def tearDown(self):
        self.db.close()

    def test_experiment_and_batch_persistence(self):
        exp = self.exp_repo.create(
            Experiment(
                id="exp-1",
                name="Test Experiment",
                scoring_protocol_version="v1.0",
                description="Testing persistence",
            )
        )
        self.assertEqual(self.exp_repo.get_by_id("exp-1").name, "Test Experiment")

        batch = self.batch_repo.create(
            ExecutionBatch(
                id="batch-1",
                experiment_id="exp-1",
                batch_name="Run 1",
                planned_attempts_count=16,
            )
        )
        self.assertEqual(self.batch_repo.get_by_id("batch-1").planned_attempts_count, 16)

        self.batch_repo.update_status("batch-1", "completed", "2026-11-20T18:00:00Z")
        updated = self.batch_repo.get_by_id("batch-1")
        self.assertEqual(updated.status, "completed")
        self.assertEqual(updated.completed_at, "2026-11-20T18:00:00Z")

    def test_provider_and_case_persistence(self):
        prov = self.prov_repo.register(
            Provider(
                id="test-provider",
                display_name="Test AI Reviewer",
                adapter_type="api_http",
                default_model="claude-3-5-sonnet",
            )
        )
        self.assertEqual(self.prov_repo.get_by_id("test-provider").display_name, "Test AI Reviewer")

        case = self.case_repo.register(
            BenchmarkCase(
                id="case-01",
                case_number=1,
                title="Page report history by scheduled time",
                pr_description="Show most recently scheduled deliveries first.",
                baseline_commit="9b5ac64",
                target_commit="b422577",
                patch_relpath="cases/01/change.patch",
            )
        )
        self.assertEqual(self.case_repo.get_by_number(1).id, "case-01")

    def test_attempt_and_response_persistence(self):
        self.exp_repo.create(Experiment(id="e1", name="Exp", scoring_protocol_version="v1"))
        self.batch_repo.create(ExecutionBatch(id="b1", experiment_id="e1", batch_name="B1", planned_attempts_count=1))
        self.prov_repo.register(Provider(id="p1", display_name="P1", adapter_type="mock", default_model="m1"))
        self.case_repo.register(
            BenchmarkCase(
                id="c1",
                case_number=1,
                title="T1",
                pr_description="D1",
                baseline_commit="9b5ac64",
                target_commit="b422577",
                patch_relpath="cases/01/change.patch",
            )
        )

        attempt = self.attempt_repo.create(
            ReviewAttempt(
                id="att-1",
                batch_id="b1",
                provider_id="p1",
                case_id="c1",
                context_condition=ContextCondition.CODE_ONLY,
                model_name="m1",
                settings_hash="hash",
                base_commit="9b5ac64",
                head_commit="b422577",
            )
        )
        self.assertEqual(self.attempt_repo.get_by_id("att-1").status, AttemptStatus.PENDING)

        # Unique constraint on batch + provider + case + context + attempt_number
        with self.assertRaises(sqlite3.IntegrityError):
            self.attempt_repo.create(
                ReviewAttempt(
                    id="att-duplicate",
                    batch_id="b1",
                    provider_id="p1",
                    case_id="c1",
                    context_condition=ContextCondition.CODE_ONLY,
                    model_name="m1",
                    settings_hash="hash",
                    base_commit="9b5ac64",
                    head_commit="b422577",
                    idempotency_key="unique-key-2",  # different idempotency key but same tuple
                )
            )

        resp = self.response_repo.save(
            ReviewResponse(
                id="resp-1",
                attempt_id="att-1",
                raw_content="Review comment content",
                prompt_tokens=100,
                completion_tokens=20,
            )
        )
        self.assertEqual(self.response_repo.get_by_attempt_id("att-1").raw_content, "Review comment content")


if __name__ == "__main__":
    unittest.main()
