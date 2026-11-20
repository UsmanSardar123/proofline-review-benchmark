"""Run lifecycle, recovery, idempotency, and failure handling tests."""

import unittest

from benchmark.db.connection import get_connection
from benchmark.db.migrations import migrate_benchmark_db
from benchmark.db.repositories import ProviderRepository
from benchmark.domain.enums import AttemptStatus, AttemptType, ContextCondition
from benchmark.domain.models import Provider
from benchmark.orchestrator.engine import BenchmarkOrchestrator
from benchmark.providers.mock import MockProviderAdapter


class LifecycleOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.db = get_connection(":memory:")
        migrate_benchmark_db(self.db)
        self.prov_repo = ProviderRepository(self.db)
        self.prov_repo.register(
            Provider(
                id="mock-reviewer",
                display_name="Mock Reviewer",
                adapter_type="mock",
                default_model="mock-model",
            )
        )
        self.prov_repo.register(
            Provider(
                id="quota-reviewer",
                display_name="Quota Reviewer",
                adapter_type="mock",
                default_model="mock-model",
            )
        )
        self.orch = BenchmarkOrchestrator(self.db)

    def tearDown(self):
        self.db.close()

    def test_complete_batch_lifecycle_and_idempotency(self):
        # 1. Schedule batch: 8 cases x 1 provider = 8 attempts
        batch = self.orch.schedule_batch(
            experiment_id="exp-pilot",
            batch_name="Pilot Lifecycle",
            provider_ids=["mock-reviewer"],
            case_numbers=list(range(1, 9)),
            context_conditions=[ContextCondition.CODE_ONLY],
        )
        self.assertEqual(batch.planned_attempts_count, 8)

        attempts = self.orch.attempt_repo.list_for_batch(batch.id)
        self.assertEqual(len(attempts), 8)
        self.assertTrue(all(a.status == AttemptStatus.PENDING for a in attempts))

        # 2. Execute attempts
        adapter = MockProviderAdapter(provider_id="mock-reviewer")
        for att in attempts:
            self.orch.execute_attempt(att, adapter)

        completed = self.orch.attempt_repo.list_for_batch(batch.id)
        self.assertTrue(all(a.status == AttemptStatus.COMPLETED for a in completed))
        self.assertTrue(all(a.duration_ms is not None for a in completed))

        # 3. Idempotency protection: re-running does not duplicate response
        first = completed[0]
        re_run = self.orch.execute_attempt(first, adapter)
        self.assertEqual(re_run.status, AttemptStatus.COMPLETED)
        resp = self.orch.response_repo.get_by_attempt_id(first.id)
        self.assertIsNotNone(resp)

    def test_quota_exhaustion_handling(self):
        batch = self.orch.schedule_batch(
            experiment_id="exp-pilot",
            batch_name="Quota Test",
            provider_ids=["quota-reviewer"],
            case_numbers=[1],
            context_conditions=[ContextCondition.CODE_ONLY],
        )
        att = self.orch.attempt_repo.list_for_batch(batch.id)[0]
        adapter = MockProviderAdapter(provider_id="quota-reviewer", mode="quota")

        res = self.orch.execute_attempt(att, adapter)
        self.assertEqual(res.status, AttemptStatus.QUOTA_EXHAUSTED)
        self.assertIn("Simulated rate limit", res.error_reason)

    def test_automatic_retry_handling(self):
        batch = self.orch.schedule_batch(
            experiment_id="exp-pilot",
            batch_name="Retry Test",
            provider_ids=["mock-reviewer"],
            case_numbers=[2],
            context_conditions=[ContextCondition.CODE_ONLY],
        )
        att = self.orch.attempt_repo.list_for_batch(batch.id)[0]
        adapter = MockProviderAdapter(mode="retry_once")

        res = self.orch.execute_attempt(att, adapter, max_retries=2)
        self.assertEqual(res.status, AttemptStatus.COMPLETED)
        self.assertEqual(res.retry_count, 1)
        self.assertEqual(res.attempt_type, AttemptType.AUTOMATIC_RETRY)

    def test_intentional_repeat_linkage(self):
        batch = self.orch.schedule_batch(
            experiment_id="exp-pilot",
            batch_name="Repeat Test",
            provider_ids=["mock-reviewer"],
            case_numbers=[1],
            context_conditions=[ContextCondition.CODE_ONLY],
        )
        att = self.orch.attempt_repo.list_for_batch(batch.id)[0]
        self.orch.execute_attempt(att, MockProviderAdapter())

        repeat = self.orch.schedule_intentional_repeat(att.id)
        self.assertEqual(repeat.attempt_type, AttemptType.INTENTIONAL_REPEAT)
        self.assertEqual(repeat.attempt_number, 2)
        self.assertEqual(repeat.parent_attempt_id, att.id)
        self.assertEqual(repeat.status, AttemptStatus.PENDING)

    def test_crash_recovery_and_resumption(self):
        batch = self.orch.schedule_batch(
            experiment_id="exp-pilot",
            batch_name="Crash Recovery",
            provider_ids=["mock-reviewer"],
            case_numbers=[3],
            context_conditions=[ContextCondition.CODE_ONLY],
        )
        att = self.orch.attempt_repo.list_for_batch(batch.id)[0]
        # Simulate worker crash: attempt left in RUNNING with no response
        self.orch.attempt_repo.mark_running(att.id)
        self.assertEqual(self.orch.attempt_repo.get_by_id(att.id).status, AttemptStatus.RUNNING)

        # Recover and resume
        summary = self.orch.recover_and_resume_batch(
            batch.id,
            adapters={"mock-reviewer": MockProviderAdapter()},
        )
        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["pending"], 0)
        self.assertEqual(self.orch.attempt_repo.get_by_id(att.id).status, AttemptStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
