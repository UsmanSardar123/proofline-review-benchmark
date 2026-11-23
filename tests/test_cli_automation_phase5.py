"""Automated tests for Phase 5: CLI, reporting workflows, execution automation, and recovery."""

from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest

from benchmark.cases.registry import CaseRegistry
from benchmark.cli.commands import (
    cmd_calibrate,
    cmd_init_db,
    cmd_list_batches,
    cmd_list_cases,
    cmd_list_providers,
    cmd_report,
    cmd_resume,
    cmd_run,
    cmd_show_attempt,
)
from benchmark.cli.main import build_parser, main
from benchmark.db.connection import get_connection
from benchmark.db.migrations import get_current_version, migrate_benchmark_db
from benchmark.db.repositories import (
    AttemptRepository,
    AttemptScoreRepository,
    BatchRepository,
    CaseRepository,
    EvaluationRepository,
    ExperimentRepository,
    FindingRepository,
    GroundTruthRepository,
    ProviderRepository,
    ResponseRepository,
    RunEventRepository,
)
from benchmark.domain.enums import AttemptStatus, AttemptType, ContextCondition
from benchmark.domain.models import ExecutionBatch, Experiment, Provider, ReviewAttempt, ReviewResponse, RunEvent
from benchmark.orchestrator.engine import BenchmarkOrchestrator
from benchmark.providers.mock import MockProviderAdapter
from benchmark.scoring.calibration import CalibrationRegistry
from benchmark.scoring.heldout import PartitionManager


class CLIParserAndArgumentTests(unittest.TestCase):
    """Test CLI argument parsing, valid command construction, and invalid argument handling."""

    def setUp(self):
        self.parser = build_parser()

    def test_valid_commands_parse_correctly(self):
        # 1. init-db
        args = self.parser.parse_args(["init-db"])
        self.assertEqual(args.command, "init-db")

        # 2. list-cases
        args = self.parser.parse_args(["list-cases", "--partition", "calibration"])
        self.assertEqual(args.command, "list-cases")
        self.assertEqual(args.partition, "calibration")

        # 3. list-providers
        args = self.parser.parse_args(["list-providers"])
        self.assertEqual(args.command, "list-providers")

        # 4. list-batches
        args = self.parser.parse_args(["list-batches", "--limit", "15"])
        self.assertEqual(args.command, "list-batches")
        self.assertEqual(args.limit, 15)

        # 5. run
        args = self.parser.parse_args([
            "run",
            "--providers", "mock,anthropic",
            "--cases", "1,2,3",
            "--context", "code-only",
            "--repeats", "2",
            "--dry-run",
            "--calibration-profile", "strict-v1",
            "--output-dir", "reports/",
            "--title", "Test Title",
        ])
        self.assertEqual(args.command, "run")
        self.assertEqual(args.providers, "mock,anthropic")
        self.assertEqual(args.cases, "1,2,3")
        self.assertEqual(args.context, "code-only")
        self.assertEqual(args.repeats, 2)
        self.assertTrue(args.dry_run)
        self.assertEqual(args.calibration_profile, "strict-v1")
        self.assertEqual(args.output_dir, "reports/")
        self.assertEqual(args.title, "Test Title")

        # 6. resume
        args = self.parser.parse_args([
            "resume",
            "--batch-id", "batch-123456",
            "--resume-quota",
            "--dry-run",
        ])
        self.assertEqual(args.command, "resume")
        self.assertEqual(args.batch_id, "batch-123456")
        self.assertTrue(args.resume_quota)
        self.assertTrue(args.dry_run)

        # 7. report
        args = self.parser.parse_args([
            "report",
            "--batch-id", "batch-123456",
            "--format", "json",
            "--stdout",
        ])
        self.assertEqual(args.command, "report")
        self.assertEqual(args.batch_id, "batch-123456")
        self.assertEqual(args.format, "json")
        self.assertTrue(args.stdout)

        # 8. show-attempt
        args = self.parser.parse_args([
            "show-attempt",
            "--attempt-id", "att-abcdef",
            "--full",
        ])
        self.assertEqual(args.command, "show-attempt")
        self.assertEqual(args.attempt_id, "att-abcdef")
        self.assertTrue(args.full)

        # 9. calibrate
        args = self.parser.parse_args([
            "calibrate",
            "--batch-id", "batch-123456",
            "--profile", "standard-v1",
        ])
        self.assertEqual(args.command, "calibrate")
        self.assertEqual(args.batch_id, "batch-123456")
        self.assertEqual(args.profile, "standard-v1")

    def test_missing_subcommand_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            with redirect_stderr(StringIO()):
                self.parser.parse_args([])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_invalid_subcommand_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            with redirect_stderr(StringIO()):
                self.parser.parse_args(["unknown-command"])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_missing_required_arguments_exit(self):
        # resume missing --batch-id
        with self.assertRaises(SystemExit):
            with redirect_stderr(StringIO()):
                self.parser.parse_args(["resume"])

        # report missing --batch-id
        with self.assertRaises(SystemExit):
            with redirect_stderr(StringIO()):
                self.parser.parse_args(["report"])

        # show-attempt missing --attempt-id
        with self.assertRaises(SystemExit):
            with redirect_stderr(StringIO()):
                self.parser.parse_args(["show-attempt"])


class CLIExecutionAndAutomationTests(unittest.TestCase):
    """Integration tests for CLI command execution, orchestration, reports, and recovery."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp_dir.name) / "test_benchmark.sqlite")
        self.reports_dir = Path(self.tmp_dir.name) / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        os.environ["BENCHMARK_EVIDENCE_DIR"] = str(Path(self.tmp_dir.name) / "evidence")

    def tearDown(self):
        self.tmp_dir.cleanup()
        os.environ.pop("BENCHMARK_EVIDENCE_DIR", None)

    def test_init_db_creates_and_migrates_schema(self):
        buf = StringIO()
        with redirect_stdout(buf):
            ret = cmd_init_db(db_path=self.db_path)
        self.assertEqual(ret, 0)
        output = buf.getvalue()
        self.assertIn("[OK] Benchmark database initialized at:", output)
        self.assertIn("Applied migrations: [1, 2]", output)

        # Re-running init-db is idempotent
        buf2 = StringIO()
        with redirect_stdout(buf2):
            ret2 = cmd_init_db(db_path=self.db_path)
        self.assertEqual(ret2, 0)
        self.assertIn("Schema is up to date", buf2.getvalue())

    def test_list_cases_with_partitions(self):
        cmd_init_db(db_path=self.db_path)

        # 1. All cases
        buf_all = StringIO()
        with redirect_stdout(buf_all):
            ret = cmd_list_cases(partition="all", db_path=self.db_path)
        self.assertEqual(ret, 0)
        self.assertIn("Total cases listed: 8", buf_all.getvalue())
        self.assertIn("case-01", buf_all.getvalue())
        self.assertIn("case-08", buf_all.getvalue())

        # 2. Calibration partition
        buf_cal = StringIO()
        with redirect_stdout(buf_cal):
            ret = cmd_list_cases(partition="calibration", db_path=self.db_path)
        self.assertEqual(ret, 0)
        self.assertIn("Total cases listed: 4", buf_cal.getvalue())
        self.assertIn("case-01", buf_cal.getvalue())
        self.assertIn("case-07", buf_cal.getvalue())
        self.assertNotIn("case-04", buf_cal.getvalue())

        # 3. Held-out partition
        buf_held = StringIO()
        with redirect_stdout(buf_held):
            ret = cmd_list_cases(partition="heldout", db_path=self.db_path)
        self.assertEqual(ret, 0)
        self.assertIn("Total cases listed: 4", buf_held.getvalue())
        self.assertIn("case-04", buf_held.getvalue())
        self.assertIn("case-08", buf_held.getvalue())
        self.assertNotIn("case-01", buf_held.getvalue())

        # 4. Invalid partition
        buf_err = StringIO()
        with redirect_stderr(buf_err):
            ret_bad = cmd_list_cases(partition="invalid", db_path=self.db_path)
        self.assertEqual(ret_bad, 1)

    def test_list_providers_output(self):
        buf = StringIO()
        with redirect_stdout(buf):
            ret = cmd_list_providers()
        self.assertEqual(ret, 0)
        out = buf.getvalue()
        self.assertIn("mock", out)
        self.assertIn("anthropic", out)
        self.assertIn("openai", out)
        self.assertIn("coderabbit", out)

    def test_run_batch_execution_and_reports(self):
        cmd_init_db(db_path=self.db_path)

        buf = StringIO()
        with redirect_stdout(buf):
            ret = cmd_run(
                experiment_id="exp-test-e2e",
                batch_name="E2E Test Batch",
                providers="mock",
                cases="1,2,7",
                context="code-only",
                repeats=1,
                dry_run=True,
                calibration_profile="standard-v1",
                output_dir=str(self.reports_dir),
                title="E2E Execution Report",
                db_path=self.db_path,
            )
        self.assertEqual(ret, 0)
        out = buf.getvalue()
        self.assertIn("PROOF-LINE AI REVIEW BENCHMARK EXECUTION", out)
        self.assertIn("BATCH EXECUTION COMPLETE", out)
        self.assertIn("Completed:         3", out)

        # Verify exported files exist
        exported_files = list(self.reports_dir.glob("*"))
        self.assertGreaterEqual(len(exported_files), 6)
        md_files = list(self.reports_dir.glob("*.md"))
        json_files = list(self.reports_dir.glob("*.json"))
        csv_files = list(self.reports_dir.glob("*.csv"))

        self.assertEqual(len(md_files), 1)
        self.assertEqual(len(json_files), 1)
        self.assertEqual(len(csv_files), 4)

        # Verify JSON report structure
        json_data = json.loads(json_files[0].read_text(encoding="utf-8"))
        self.assertEqual(json_data["title"], "E2E Execution Report")
        self.assertIn("matrix", json_data)
        self.assertIn("denominators", json_data)
        self.assertIn("partition_comparison", json_data)

    def test_run_batch_validation_errors(self):
        cmd_init_db(db_path=self.db_path)

        # 1. Invalid provider
        buf = StringIO()
        with redirect_stderr(buf):
            ret = cmd_run(providers="invalid-provider", cases="1", db_path=self.db_path)
        self.assertEqual(ret, 1)
        self.assertIn("Unknown provider 'invalid-provider'", buf.getvalue())

        # 2. Invalid case number
        buf = StringIO()
        with redirect_stderr(buf):
            ret = cmd_run(providers="mock", cases="99", db_path=self.db_path)
        self.assertEqual(ret, 1)
        self.assertIn("Case number out of range", buf.getvalue())

        # 3. Invalid context condition
        buf = StringIO()
        with redirect_stderr(buf):
            ret = cmd_run(providers="mock", cases="1", context="bad-context", db_path=self.db_path)
        self.assertEqual(ret, 1)
        self.assertIn("Invalid context 'bad-context'", buf.getvalue())

        # 4. Unknown calibration profile
        buf = StringIO()
        with redirect_stderr(buf):
            ret = cmd_run(providers="mock", cases="1", calibration_profile="unknown-profile", db_path=self.db_path)
        self.assertEqual(ret, 1)
        self.assertIn("Unknown calibration profile", buf.getvalue())

    def test_interrupted_run_and_recovery_workflow(self):
        """Simulate an interrupted batch with RUNNING and QUOTA_EXHAUSTED attempts, then recover."""
        conn = get_connection(self.db_path)
        try:
            migrate_benchmark_db(conn)

            exp_repo = ExperimentRepository(conn)
            exp_repo.create(Experiment(id="exp-recovery", name="Recovery Test", scoring_protocol_version="v1.0"))

            case_repo = CaseRepository(conn)
            case_reg = CaseRegistry()
            for num in [1, 2, 3, 7]:
                case_repo.register(case_reg.load_case(num))

            batch_repo = BatchRepository(conn)
            att_repo = AttemptRepository(conn)
            prov_repo = ProviderRepository(conn)
            event_repo = RunEventRepository(conn)

            prov_repo.register(
                Provider(
                    id="mock",
                    display_name="Mock Reviewer",
                    adapter_type="mock",
                    default_model="mock-v1",
                )
            )

            batch_id = "batch-crash-test"
            batch_repo.create(
                ExecutionBatch(
                    id=batch_id,
                    experiment_id="exp-recovery",
                    batch_name="Crash Recovery Test",
                    planned_attempts_count=4,
                    status="running",
                )
            )

            # Attempt 1: Already COMPLETED
            att_1 = ReviewAttempt(
                id="att-rec-1",
                batch_id=batch_id,
                provider_id="mock",
                case_id="case-01",
                context_condition=ContextCondition.CODE_ONLY,
                model_name="mock-v1",
                settings_hash="h1",
                base_commit="9b5ac64",
                head_commit="b422577",
                status=AttemptStatus.COMPLETED,
            )
            att_repo.create(att_1)

            # Attempt 2: Stuck in RUNNING (e.g. process killed mid-execution)
            att_2 = ReviewAttempt(
                id="att-rec-2",
                batch_id=batch_id,
                provider_id="mock",
                case_id="case-02",
                context_condition=ContextCondition.CODE_ONLY,
                model_name="mock-v1",
                settings_hash="h2",
                base_commit="9b5ac64",
                head_commit="9d551b8",
                status=AttemptStatus.RUNNING,
            )
            att_repo.create(att_2)

            # Attempt 3: Stopped due to QUOTA_EXHAUSTED
            att_3 = ReviewAttempt(
                id="att-rec-3",
                batch_id=batch_id,
                provider_id="mock",
                case_id="case-03",
                context_condition=ContextCondition.CODE_ONLY,
                model_name="mock-v1",
                settings_hash="h3",
                base_commit="9b5ac64",
                head_commit="6cca1e9",
                status=AttemptStatus.QUOTA_EXHAUSTED,
                error_reason="Rate limit 429",
            )
            att_repo.create(att_3)

            # Attempt 4: Still PENDING
            att_4 = ReviewAttempt(
                id="att-rec-4",
                batch_id=batch_id,
                provider_id="mock",
                case_id="case-07",
                context_condition=ContextCondition.CODE_ONLY,
                model_name="mock-v1",
                settings_hash="h4",
                base_commit="9b5ac64",
                head_commit="68ef658",
                status=AttemptStatus.PENDING,
            )
            att_repo.create(att_4)
            conn.commit()
        finally:
            conn.close()

        # Step 1: Resume without --resume-quota
        # Orphaned RUNNING (att-rec-2) and PENDING (att-rec-4) should be executed to COMPLETED
        # QUOTA_EXHAUSTED (att-rec-3) should remain halted
        buf_res1 = StringIO()
        with redirect_stdout(buf_res1):
            ret = cmd_resume(
                batch_id=batch_id,
                resume_quota=False,
                dry_run=True,
                db_path=self.db_path,
            )
        self.assertEqual(ret, 0)
        out1 = buf_res1.getvalue()
        self.assertIn("Completed:         3", out1)
        self.assertIn("Quota Exhausted:   1", out1)

        # Verify crash recovery event was logged in DB
        conn = get_connection(self.db_path)
        try:
            events = RunEventRepository(conn).list_for_attempt("att-rec-2")
            crash_events = [e for e in events if e.event_type == "CRASH_RECOVERY"]
            self.assertEqual(len(crash_events), 1)
        finally:
            conn.close()

        # Step 2: Resume with --resume-quota
        # Should now re-attempt att-rec-3 and complete all 4 attempts
        buf_res2 = StringIO()
        with redirect_stdout(buf_res2):
            ret2 = cmd_resume(
                batch_id=batch_id,
                resume_quota=True,
                dry_run=True,
                output_dir=str(self.reports_dir),
                db_path=self.db_path,
            )
        self.assertEqual(ret2, 0)
        out2 = buf_res2.getvalue()
        self.assertIn("Completed:         4", out2)
        self.assertIn("Quota Exhausted:   0", out2)

        # Batch record is now marked 'completed'
        conn = get_connection(self.db_path)
        try:
            batch_after = BatchRepository(conn).get_by_id(batch_id)
            self.assertEqual(batch_after.status, "completed")
        finally:
            conn.close()

    def test_show_attempt_audit_traceability(self):
        """Verify show-attempt traces review back to commit, response, findings, ground truth, and score."""
        cmd_init_db(db_path=self.db_path)
        cmd_run(
            providers="mock",
            cases="1",
            context="code-only",
            dry_run=True,
            db_path=self.db_path,
        )

        conn = get_connection(self.db_path)
        try:
            att = AttemptRepository(conn).list_for_batch(
                BatchRepository(conn).list_all(limit=1)[0].id
            )[0]
        finally:
            conn.close()

        buf = StringIO()
        with redirect_stdout(buf):
            ret = cmd_show_attempt(attempt_id=att.id, full_response=True, db_path=self.db_path)
        self.assertEqual(ret, 0)
        out = buf.getvalue()

        # Audit checkpoints
        self.assertIn(f"REVIEW ATTEMPT AUDIT & TRACEABILITY REPORT: {att.id}", out)
        self.assertIn("1. CAPTURED REVIEW RESPONSE", out)
        self.assertIn("2. EXTRACTED FINDINGS & EVALUATIONS", out)
        self.assertIn("3. GROUND TRUTH DEFECT COMPARISON & SCORING", out)
        self.assertIn("4. LIFECYCLE AUDIT LOG", out)
        self.assertIn("Ground Truth Defect: [gt-case-01]", out)
        self.assertIn("Commit Range:", out)

    def test_calibrate_profile_inspection_and_generalization(self):
        cmd_init_db(db_path=self.db_path)
        # Execute batch with both calibration and heldout cases
        cmd_run(
            providers="mock",
            cases="1,2,4,5",
            context="code-only",
            dry_run=True,
            db_path=self.db_path,
        )

        conn = get_connection(self.db_path)
        try:
            batch = BatchRepository(conn).list_all(limit=1)[0]
        finally:
            conn.close()

        buf = StringIO()
        with redirect_stdout(buf):
            ret = cmd_calibrate(batch_id=batch.id, db_path=self.db_path)
        self.assertEqual(ret, 0)
        out = buf.getvalue()
        self.assertIn("CALIBRATION PROFILES & PARAMETER FINGERPRINTS", out)
        self.assertIn("OUT-OF-SAMPLE GENERALIZATION ANALYSIS", out)
        self.assertIn("Calibration Attempts (2):", out)
        self.assertIn("Held-Out Attempts (2):", out)
        self.assertIn("Generalization Delta", out)

    def test_heldout_isolation_anti_leak_verification(self):
        """Verify that held-out cases are never leaked into calibration evaluation."""
        # Attempting to verify a list with held-out cases should fail with ValueError
        with self.assertRaises(ValueError) as ctx:
            PartitionManager.verify_no_leakage(["case-01", "case-04"])
        self.assertIn("Anti-contamination violation", str(ctx.exception))
        self.assertIn("case-04", str(ctx.exception))

        # Calibration only passes cleanly
        self.assertTrue(PartitionManager.verify_no_leakage(["case-01", "case-02", "case-03", "case-07"]))

    def test_main_cli_entrypoint_end_to_end(self):
        """Test invoking CLI through main() function with argument lists."""
        ret_init = main(["--db", self.db_path, "init-db"])
        self.assertEqual(ret_init, 0)

        ret_cases = main(["--db", self.db_path, "list-cases"])
        self.assertEqual(ret_cases, 0)

        ret_prov = main(["--db", self.db_path, "list-providers"])
        self.assertEqual(ret_prov, 0)

        ret_run = main([
            "--db", self.db_path,
            "run",
            "--providers", "mock",
            "--cases", "1,7",
            "--context", "code-only",
            "--dry-run",
            "--output-dir", str(self.reports_dir),
        ])
        self.assertEqual(ret_run, 0)

        ret_batches = main(["--db", self.db_path, "list-batches"])
        self.assertEqual(ret_batches, 0)


if __name__ == "__main__":
    unittest.main()
