"""End-to-end integration test validating the complete Phase 2 workflow."""

import json
from pathlib import Path
import tempfile
import unittest

from benchmark.collector.storage import RawEvidenceStore
from benchmark.config import PROJECT_ROOT
from benchmark.db.connection import get_connection
from benchmark.db.migrations import migrate_benchmark_db
from benchmark.domain.enums import AttemptStatus, ContextCondition
from benchmark.domain.models import Provider
from benchmark.orchestrator.engine import BenchmarkOrchestrator
from benchmark.providers.base import (
    BaseProviderAdapter,
    ProviderConfig,
    ProviderRawResult,
    ReviewContext,
)


class SimulatedSmartAdapter(BaseProviderAdapter):
    """Simulates an AI review provider with case-aware responses for e2e validation."""

    def __init__(self, provider_id: str, name: str):
        super().__init__(ProviderConfig(provider_id=provider_id, display_name=name, default_model="claude-3-5-sonnet"))

    def invoke_review(self, context: ReviewContext) -> ProviderRawResult:
        case_num = context.case_number
        is_snapshot = context.context_condition == ContextCondition.CODE_AND_SNAPSHOT

        if case_num == 1:
            content = (
                "## AI Code Review\n\n"
                "- **File:** `reports.py`\n"
                "- **Lines:** 45-48\n"
                "- **Severity:** critical\n"
                "- **Comment:** Cursor pagination query relies on `scheduled_at < ?` without tie-breaker. "
                "Multiple deliveries scheduled for the same second will be skipped or duplicated."
            )
        elif case_num == 4:
            if is_snapshot and context.snapshot_content and "elm" in context.snapshot_content.lower():
                content = (
                    "## AI Code Review with Deployment Snapshot\n\n"
                    "- **File:** `migrations/002_retire_format.sql`\n"
                    "- **Lines:** 1\n"
                    "- **Severity:** critical\n"
                    "- **Comment:** Dropping `legacy_format` column breaks active Elm site workers running "
                    "revision `workers-17` which still executes `poll_sql` querying this column."
                )
            else:
                content = (
                    "## AI Code Review\n\n"
                    "- **File:** `migrations/002_retire_format.sql`\n"
                    "- **Lines:** 1\n"
                    "- **Severity:** warning\n"
                    "- **Comment:** Dropping table column directly without prior deprecation."
                )
        elif case_num == 7:
            content = (
                "## AI Code Review\n\n"
                "Looks good to me! Adding partial index `deliveries_due_by_queue` improves query performance cleanly."
            )
        else:
            content = "## AI Review\n\nNo significant defects found."

        return ProviderRawResult(
            raw_content=content,
            http_status=200,
            prompt_tokens=420,
            completion_tokens=150,
            duration_ms=310,
        )


class Phase2EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "e2e_benchmark.sqlite"
        self.evidence_dir = Path(self.temp_dir.name) / "evidence"
        self.db = get_connection(self.db_path)
        migrate_benchmark_db(self.db)

        self.evidence_store = RawEvidenceStore(self.evidence_dir)
        self.cases_dir = PROJECT_ROOT / "cases"
        self.orchestrator = BenchmarkOrchestrator(
            self.db,
            cases_dir=self.cases_dir,
            evidence_store=self.evidence_store,
        )

        # Register simulated provider in DB
        self.orchestrator.prov_repo.register(
            Provider(
                id="smart-ai",
                display_name="Smart AI Reviewer",
                adapter_type="api_http",
                default_model="claude-3-5-sonnet",
            )
        )
        self.adapter = SimulatedSmartAdapter("smart-ai", "Smart AI Reviewer")

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_complete_phase2_pipeline(self):
        """Execute full Phase 2 pipeline: schedule -> run -> extract -> score -> report."""
        # 1. Schedule batch across Cases 1, 4, 7 under CODE_ONLY and CODE_AND_SNAPSHOT
        batch = self.orchestrator.schedule_batch(
            experiment_id="exp-p2-e2e",
            batch_name="Phase 2 E2E Verification",
            provider_ids=["smart-ai"],
            case_numbers=[1, 4, 7],
            context_conditions=[ContextCondition.CODE_ONLY, ContextCondition.CODE_AND_SNAPSHOT],
        )

        # 3 cases * 2 context conditions = 6 planned attempts
        self.assertEqual(batch.planned_attempts_count, 6)

        # 2. Run the batch through the orchestrator
        run_stats = self.orchestrator.run_batch(batch.id, adapters={"smart-ai": self.adapter})
        self.assertEqual(run_stats["completed"], 6)
        self.assertEqual(run_stats["failed"], 0)
        self.assertEqual(run_stats["quota_exhausted"], 0)
        self.assertEqual(run_stats["pending"], 0)

        # 3. Verify response capture & filesystem mirror
        responses = [
            self.orchestrator.response_repo.get_by_attempt_id(a.id)
            for a in self.orchestrator.attempt_repo.list_for_batch(batch.id)
        ]
        self.assertEqual(len(responses), 6)
        for r in responses:
            self.assertIsNotNone(r)
            self.assertTrue(r.raw_content.startswith("## AI"))

        # Verify disk evidence mirror exists
        batch_evidence_dir = self.evidence_dir / batch.id
        self.assertTrue(batch_evidence_dir.is_dir())
        md_files = list(batch_evidence_dir.glob("*.md"))
        meta_files = list(batch_evidence_dir.glob("*.meta.json"))
        self.assertEqual(len(md_files), 6)
        self.assertEqual(len(meta_files), 6)

        # 4. Verify finding extraction
        all_findings = []
        for a in self.orchestrator.attempt_repo.list_for_batch(batch.id):
            f_list = self.orchestrator.finding_repo.list_for_attempt(a.id)
            all_findings.extend(f_list)
        self.assertGreater(len(all_findings), 0)

        # 5. Verify scoring and ground truth evaluation
        scores = self.orchestrator.score_repo.list_for_batch(batch.id)
        self.assertEqual(len(scores), 6)

        # Case 1 should have TP = 1, FP = 0, F1 = 1.0
        c1_attempts = [a for a in self.orchestrator.attempt_repo.list_for_batch(batch.id) if a.case_id == "case-01"]
        for a in c1_attempts:
            s = self.orchestrator.score_repo.get_by_attempt_id(a.id)
            self.assertEqual(s.tp_count, 1)
            self.assertEqual(s.fp_count, 0)
            self.assertEqual(s.f1_metric, 1.0)

        # Case 4 with snapshot should cite Elm deployment evidence
        c4_snap_att = next(
            a for a in self.orchestrator.attempt_repo.list_for_batch(batch.id)
            if a.case_id == "case-04" and a.context_condition == ContextCondition.CODE_AND_SNAPSHOT
        )
        evals = self.orchestrator.eval_repo.list_for_attempt(c4_snap_att.id)
        self.assertTrue(any(e.cites_deployment_evidence for e in evals))

        # Case 7 should be a clean pass
        c7_attempts = [a for a in self.orchestrator.attempt_repo.list_for_batch(batch.id) if a.case_id == "case-07"]
        for a in c7_attempts:
            s = self.orchestrator.score_repo.get_by_attempt_id(a.id)
            self.assertTrue(s.passed_cleanly)
            self.assertEqual(s.f1_metric, 1.0)

        # 6. Generate complete report
        report = self.orchestrator.generate_report(batch.id, title="Phase 2 End-to-End Report")
        self.assertIn("# Phase 2 End-to-End Report", report["markdown"])
        self.assertIn("smart-ai", report["markdown"])
        self.assertIn("case-01", report["markdown"])
        self.assertIn("case-04", report["markdown"])
        self.assertIn("case-07", report["markdown"])

        # Check structured JSON
        data = json.loads(report["json"])
        self.assertEqual(data["denominators"]["completed_total"], 6)
        self.assertEqual(data["denominators"]["planned_total"], 6)
        self.assertEqual(data["denominators"]["completion_rate_pct"], 100.0)

        # Check CSV outputs
        self.assertIn("smart-ai", report["csv"]["matrix"])
        self.assertIn("smart-ai", report["csv"]["ablation"])
        self.assertIn("smart-ai", report["csv"]["denominators"])


if __name__ == "__main__":
    unittest.main()
