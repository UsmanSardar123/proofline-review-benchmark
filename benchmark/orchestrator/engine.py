"""Execution engine and run lifecycle orchestrator for the benchmark system."""

from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Optional
import uuid

from benchmark.cases.registry import CaseRegistry
from benchmark.collector.collector import ReviewCollector
from benchmark.collector.storage import RawEvidenceStore
from benchmark.config import PROJECT_ROOT
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
from benchmark.domain.models import (
    ExecutionBatch,
    Experiment,
    Provider,
    ReviewAttempt,
    ReviewResponse,
    RunEvent,
)
from benchmark.eval.extractor import FindingExtractor
from benchmark.providers.base import (
    BaseProviderAdapter,
    ProviderFatalError,
    ProviderQuotaError,
    ProviderTransportError,
    ReviewContext,
)
from benchmark.providers.registry import ProviderRegistry
from benchmark.reporting.formatters import BenchmarkReportGenerator
from benchmark.scoring.service import ScoringService


class BenchmarkOrchestrator:
    """Coordinates batch scheduling, attempt execution, idempotency, and recovery."""

    def __init__(
        self,
        db,
        cases_dir: Optional[Path] = None,
        evidence_store: Optional[RawEvidenceStore] = None,
    ):
        self.db = db
        self.exp_repo = ExperimentRepository(db)
        self.batch_repo = BatchRepository(db)
        self.prov_repo = ProviderRepository(db)
        self.case_repo = CaseRepository(db)
        self.attempt_repo = AttemptRepository(db)
        self.response_repo = ResponseRepository(db)
        self.event_repo = RunEventRepository(db)
        self.case_registry = CaseRegistry(cases_dir)
        self.collector = ReviewCollector(self.response_repo, evidence_store=evidence_store)
        self.finding_repo = FindingRepository(db)
        self.score_repo = AttemptScoreRepository(db)
        self.eval_repo = EvaluationRepository(db)
        self.extractor = FindingExtractor()
        self.scoring_service = ScoringService(db)
        self.report_generator = BenchmarkReportGenerator(db)
        self.provider_registry = ProviderRegistry()

    def schedule_batch(
        self,
        experiment_id: str,
        batch_name: str,
        provider_ids: list[str],
        case_numbers: list[int],
        context_conditions: list[ContextCondition],
        repeat_count: int = 1,
    ) -> ExecutionBatch:
        """Initialize an execution batch and pre-create all scheduled review attempts."""
        # Ensure experiment exists
        if not self.exp_repo.get_by_id(experiment_id):
            self.exp_repo.create(
                Experiment(
                    id=experiment_id,
                    name=f"Experiment {experiment_id}",
                    scoring_protocol_version="v1.0",
                )
            )

        # Pre-register cases
        cases = []
        for num in case_numbers:
            case = self.case_registry.load_case(num)
            self.case_repo.register(case)
            cases.append(case)

        # Seed ground truths for registered cases
        self.scoring_service.seed_ground_truths([c.id for c in cases])

        # Pre-calculate exact planned denominator
        total_planned = len(provider_ids) * len(cases) * len(context_conditions) * repeat_count
        batch_id = f"batch-{uuid.uuid4().hex[:8]}"
        batch = ExecutionBatch(
            id=batch_id,
            experiment_id=experiment_id,
            batch_name=batch_name,
            planned_attempts_count=total_planned,
            status="pending",
        )
        self.batch_repo.create(batch)

        # Pre-create ReviewAttempt records in PENDING state
        for p_id in provider_ids:
            prov = self.prov_repo.get_by_id(p_id)
            if not prov and p_id.lower() in self.provider_registry.list_registered():
                # Auto-register known provider from registry into DB
                adapter_cls = self.provider_registry._adapters[p_id.lower()]
                adapter_instance = adapter_cls(dry_run=True)
                prov = self.prov_repo.register(
                    Provider(
                        id=p_id,
                        display_name=adapter_instance.display_name,
                        adapter_type="api_http" if "mock" not in p_id.lower() else "mock",
                        default_model=adapter_instance.default_model,
                    )
                )
            default_model = prov.default_model if prov else "default-model"

            for case in cases:
                for cond in context_conditions:
                    for rep in range(1, repeat_count + 1):
                        attempt_id = f"att-{uuid.uuid4().hex[:12]}"
                        attempt_type = AttemptType.INITIAL if rep == 1 else AttemptType.INTENTIONAL_REPEAT

                        attempt = ReviewAttempt(
                            id=attempt_id,
                            batch_id=batch_id,
                            provider_id=p_id,
                            case_id=case.id,
                            context_condition=cond,
                            model_name=default_model,
                            settings_hash="settings:default:v1",
                            base_commit=case.baseline_commit,
                            head_commit=case.target_commit,
                            attempt_type=attempt_type,
                            attempt_number=rep,
                            status=AttemptStatus.PENDING,
                        )
                        self.attempt_repo.create(attempt)

        self.event_repo.log(
            RunEvent(
                batch_id=batch_id,
                event_type="BATCH_SCHEDULED",
                message=f"Scheduled batch {batch_name} with {total_planned} planned attempts",
            )
        )
        return batch

    def execute_attempt(
        self,
        attempt: ReviewAttempt,
        adapter: BaseProviderAdapter,
        max_retries: int = 2,
    ) -> ReviewAttempt:
        """Execute a single review attempt through its state transitions."""
        # Idempotency guard: do not re-run completed attempts
        current = self.attempt_repo.get_by_id(attempt.id)
        if current and current.status == AttemptStatus.COMPLETED:
            return current

        # Load case details
        case = self.case_repo.get_by_id(attempt.case_id)
        if not case:
            case = self.case_registry.load_case(int(attempt.case_id.replace("case-", "")))

        patch_full = PROJECT_ROOT / case.patch_relpath
        diff_text = patch_full.read_text(encoding="utf-8") if patch_full.is_file() else ""

        context = ReviewContext(
            case_id=case.id,
            case_number=case.case_number,
            pr_title=case.title,
            pr_body=case.pr_description,
            base_commit=case.baseline_commit,
            head_commit=case.target_commit,
            patch_diff=diff_text,
            context_condition=attempt.context_condition,
            snapshot_content=case.snapshot_content if attempt.context_condition == ContextCondition.CODE_AND_SNAPSHOT else None,
        )

        # Transition: PENDING -> RUNNING
        start_ts = datetime.now(timezone.utc).isoformat()
        self.attempt_repo.mark_running(attempt.id, started_at=start_ts)
        self.event_repo.log(
            RunEvent(
                batch_id=attempt.batch_id,
                attempt_id=attempt.id,
                event_type="STATE_TRANSITION",
                from_state=AttemptStatus.PENDING.value,
                to_state=AttemptStatus.RUNNING.value,
                message=f"Dispatched attempt {attempt.id} to {adapter.display_name}",
            )
        )

        retries_done = 0
        while retries_done <= max_retries:
            t0 = time.perf_counter()
            try:
                result = adapter.invoke_review(context)
                duration_ms = result.duration_ms or int((time.perf_counter() - t0) * 1000)

                # Collect, normalize, and persist review response (DB and disk mirror)
                self.collector.collect(attempt, result)

                # Transition: RUNNING -> COMPLETED
                comp_ts = datetime.now(timezone.utc).isoformat()
                self.attempt_repo.mark_completed(attempt.id, completed_at=comp_ts, duration_ms=duration_ms)
                self.event_repo.log(
                    RunEvent(
                        batch_id=attempt.batch_id,
                        attempt_id=attempt.id,
                        event_type="STATE_TRANSITION",
                        from_state=AttemptStatus.RUNNING.value,
                        to_state=AttemptStatus.COMPLETED.value,
                        message=f"Review completed successfully in {duration_ms}ms",
                    )
                )

                # Extract findings and evaluate attempt against ground truth
                resp = self.response_repo.get_by_attempt_id(attempt.id)
                if resp:
                    findings = self.extractor.extract_findings(resp)
                    self.finding_repo.save_all(findings)
                self.scoring_service.evaluate_attempt(attempt.id)

                return self.attempt_repo.get_by_id(attempt.id)

            except ProviderQuotaError as exc:
                # Quota stop: 429 / credit exhaustion
                self.attempt_repo.mark_quota_exhausted(attempt.id, str(exc))
                self.scoring_service.evaluate_attempt(attempt.id)
                self.event_repo.log(
                    RunEvent(
                        batch_id=attempt.batch_id,
                        attempt_id=attempt.id,
                        event_type="QUOTA_EXHAUSTED",
                        from_state=AttemptStatus.RUNNING.value,
                        to_state=AttemptStatus.QUOTA_EXHAUSTED.value,
                        message=f"Provider quota exhausted: {exc}",
                    )
                )
                return self.attempt_repo.get_by_id(attempt.id)

            except ProviderTransportError as exc:
                if retries_done < max_retries:
                    retries_done += 1
                    self.attempt_repo.increment_retry(attempt.id)
                    self.event_repo.log(
                        RunEvent(
                            batch_id=attempt.batch_id,
                            attempt_id=attempt.id,
                            event_type="RETRY_ATTEMPTED",
                            message=f"Transient transport failure (retry {retries_done}/{max_retries}): {exc}",
                        )
                    )
                    time.sleep(0.05)  # brief backoff
                    continue
                else:
                    self.attempt_repo.mark_failed(attempt.id, f"Transport retries exhausted: {exc}")
                    self.scoring_service.evaluate_attempt(attempt.id)
                    self.event_repo.log(
                        RunEvent(
                            batch_id=attempt.batch_id,
                            attempt_id=attempt.id,
                            event_type="STATE_TRANSITION",
                            from_state=AttemptStatus.RUNNING.value,
                            to_state=AttemptStatus.FAILED.value,
                            message=f"Failed after {max_retries} retries: {exc}",
                        )
                    )
                    return self.attempt_repo.get_by_id(attempt.id)

            except Exception as exc:
                self.attempt_repo.mark_failed(attempt.id, str(exc))
                self.scoring_service.evaluate_attempt(attempt.id)
                self.event_repo.log(
                    RunEvent(
                        batch_id=attempt.batch_id,
                        attempt_id=attempt.id,
                        event_type="STATE_TRANSITION",
                        from_state=AttemptStatus.RUNNING.value,
                        to_state=AttemptStatus.FAILED.value,
                        message=f"Fatal attempt failure: {exc}",
                    )
                )
                return self.attempt_repo.get_by_id(attempt.id)

        return self.attempt_repo.get_by_id(attempt.id)

    def schedule_intentional_repeat(self, original_attempt_id: str) -> ReviewAttempt:
        """Schedule an intentional repeat for a previously attempted provider-case pair."""
        orig = self.attempt_repo.get_by_id(original_attempt_id)
        if not orig:
            raise ValueError(f"Original attempt not found: {original_attempt_id}")

        all_batch = self.attempt_repo.list_for_batch(orig.batch_id)
        matching = [
            a for a in all_batch
            if a.provider_id == orig.provider_id and a.case_id == orig.case_id and a.context_condition == orig.context_condition
        ]
        next_attempt_number = max(a.attempt_number for a in matching) + 1

        repeat_id = f"att-{uuid.uuid4().hex[:12]}"
        repeat_attempt = ReviewAttempt(
            id=repeat_id,
            batch_id=orig.batch_id,
            provider_id=orig.provider_id,
            case_id=orig.case_id,
            context_condition=orig.context_condition,
            model_name=orig.model_name,
            settings_hash=orig.settings_hash,
            base_commit=orig.base_commit,
            head_commit=orig.head_commit,
            attempt_type=AttemptType.INTENTIONAL_REPEAT,
            parent_attempt_id=original_attempt_id,
            attempt_number=next_attempt_number,
            status=AttemptStatus.PENDING,
        )
        self.attempt_repo.create(repeat_attempt)

        self.event_repo.log(
            RunEvent(
                batch_id=orig.batch_id,
                attempt_id=repeat_id,
                event_type="REPEAT_SCHEDULED",
                message=f"Scheduled intentional repeat #{next_attempt_number} linked to parent {original_attempt_id}",
            )
        )
        return repeat_attempt

    def recover_and_resume_batch(
        self,
        batch_id: str,
        adapters: dict[str, BaseProviderAdapter],
        resume_quota: bool = False,
    ) -> dict:
        """Recover from an interrupted run and resume incomplete attempts."""
        batch = self.batch_repo.get_by_id(batch_id)
        if not batch:
            raise ValueError(f"Batch not found: {batch_id}")

        attempts = self.attempt_repo.list_for_batch(batch_id)

        # Crash recovery: Reset any attempt stuck in RUNNING without a response
        for att in attempts:
            if att.status == AttemptStatus.RUNNING:
                resp = self.response_repo.get_by_attempt_id(att.id)
                if not resp:
                    # Incomplete; reset to PENDING
                    self.attempt_repo.update_status(att.id, AttemptStatus.PENDING)
                    self.event_repo.log(
                        RunEvent(
                            batch_id=batch_id,
                            attempt_id=att.id,
                            event_type="CRASH_RECOVERY",
                            from_state=AttemptStatus.RUNNING.value,
                            to_state=AttemptStatus.PENDING.value,
                            message="Crash recovery: reset orphaned RUNNING attempt back to PENDING",
                        )
                    )

        # Refresh attempts after crash reset
        attempts = self.attempt_repo.list_for_batch(batch_id)
        to_run = []
        for att in attempts:
            if att.status == AttemptStatus.PENDING:
                to_run.append(att)
            elif att.status == AttemptStatus.QUOTA_EXHAUSTED and resume_quota:
                to_run.append(att)

        for att in to_run:
            adapter = adapters.get(att.provider_id)
            if not adapter:
                continue
            self.execute_attempt(att, adapter)

        # Tally final batch status
        all_now = self.attempt_repo.list_for_batch(batch_id)
        completed = sum(1 for a in all_now if a.status == AttemptStatus.COMPLETED)
        quota_halt = sum(1 for a in all_now if a.status == AttemptStatus.QUOTA_EXHAUSTED)
        failed = sum(1 for a in all_now if a.status == AttemptStatus.FAILED)
        pending = sum(1 for a in all_now if a.status == AttemptStatus.PENDING)

        if pending == 0 and quota_halt == 0:
            self.batch_repo.update_status(batch_id, "completed", datetime.now(timezone.utc).isoformat())
        elif quota_halt > 0:
            self.batch_repo.update_status(batch_id, "quota_halted")
        else:
            self.batch_repo.update_status(batch_id, "running")

        return {
            "batch_id": batch_id,
            "planned": batch.planned_attempts_count,
            "completed": completed,
            "quota_exhausted": quota_halt,
            "failed": failed,
            "pending": pending,
        }

    def run_batch(
        self,
        batch_id: str,
        adapters: Optional[dict[str, BaseProviderAdapter]] = None,
        dry_run: bool = False,
    ) -> dict:
        """Execute all pending attempts for a batch using configured provider adapters."""
        active_adapters = dict(adapters or {})
        attempts = self.attempt_repo.list_for_batch(batch_id)
        for att in attempts:
            if att.status == AttemptStatus.PENDING:
                if att.provider_id not in active_adapters:
                    try:
                        active_adapters[att.provider_id] = self.provider_registry.get_adapter(
                            att.provider_id, dry_run=dry_run
                        )
                    except KeyError:
                        pass
                adapter = active_adapters.get(att.provider_id)
                if adapter:
                    self.execute_attempt(att, adapter)

        all_now = self.attempt_repo.list_for_batch(batch_id)
        completed = sum(1 for a in all_now if a.status == AttemptStatus.COMPLETED)
        quota_halt = sum(1 for a in all_now if a.status == AttemptStatus.QUOTA_EXHAUSTED)
        failed = sum(1 for a in all_now if a.status == AttemptStatus.FAILED)
        pending = sum(1 for a in all_now if a.status == AttemptStatus.PENDING)

        if pending == 0 and quota_halt == 0:
            self.batch_repo.update_status(batch_id, "completed", datetime.now(timezone.utc).isoformat())
        elif quota_halt > 0:
            self.batch_repo.update_status(batch_id, "quota_halted")
        else:
            self.batch_repo.update_status(batch_id, "running")

        batch = self.batch_repo.get_by_id(batch_id)
        return {
            "batch_id": batch_id,
            "planned": batch.planned_attempts_count if batch else len(all_now),
            "completed": completed,
            "quota_exhausted": quota_halt,
            "failed": failed,
            "pending": pending,
        }

    def generate_report(self, batch_id: str, title: Optional[str] = None) -> dict:
        """Generate a complete structured benchmark report (Markdown, CSV, JSON) for a batch."""
        return self.report_generator.generate_full_report(batch_id, title=title or f"Proofline AI Review Benchmark ({batch_id})")
