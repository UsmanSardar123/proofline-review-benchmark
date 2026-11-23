"""Safe automated campaign runner for Cloudflare Workers AI evaluations.

Enforces zero-cost guarantees, pre-execution ground truth anti-leak verification,
sequential execution with fail-closed stops, and isolated genuine evidence preservation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Optional

from benchmark.cases.context import ContextManager
from benchmark.cases.registry import CaseRegistry
from benchmark.config import PROJECT_ROOT
from benchmark.db.connection import get_connection
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
from benchmark.domain.models import ExecutionBatch, Experiment, Provider, ReviewAttempt, RunEvent
from benchmark.orchestrator.engine import BenchmarkOrchestrator
from benchmark.providers.base import ProviderError, ProviderQuotaError, ReviewContext
from benchmark.providers.cloudflare import (
    CONSERVATIVE_SAFETY_NEURON_LIMIT,
    CloudflareAdapter,
    CloudflareConfig,
    DEFAULT_MODEL,
    NeuronTracker,
)
from benchmark.scoring.calibration import CalibrationRegistry
from benchmark.scoring.service import ScoringService


ALLOWED_CAMPAIGN_CASES = [3, 4, 5, 6, 7, 8]


class CampaignValidationError(Exception):
    """Raised when case validation, scope boundaries, or anti-leak checks fail."""
    pass


class CampaignBudgetError(Exception):
    """Raised when Neuron budget or zero-cost safety constraints are violated."""
    pass


@dataclass
class CasePreflightAudit:
    """Preflight validation record for an individual benchmark case."""
    case_number: int
    case_id: str
    case_title: str
    context_condition: str
    ground_truth_count: int
    defect_categories: list[str]
    prompt_length_chars: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_neurons: int
    leak_check_passed: bool
    status: str = "VALID"
    error_message: Optional[str] = None


@dataclass
class CampaignPreflightResult:
    """Result of complete pre-execution audit for the campaign."""
    is_valid: bool
    allowed_cases: list[int]
    total_estimated_input_tokens: int
    total_estimated_output_tokens: int
    total_estimated_neurons: int
    current_neurons_consumed: int
    conservative_daily_limit: int
    remaining_daily_budget: int
    model_name: str
    case_audits: list[CasePreflightAudit] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class CampaignCaseExecutionResult:
    """Outcome of an individual case execution within the campaign."""
    case_number: int
    case_id: str
    attempt_id: str
    status: str  # COMPLETED, FAILED, SKIPPED, DRY_RUN
    http_status: Optional[int] = None
    duration_ms: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    neurons_consumed: Optional[int] = None
    tp_count: int = 0
    fp_count: int = 0
    fn_count: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    passed_cleanly: bool = False
    evidence_file: Optional[str] = None
    content_hash_sha256: Optional[str] = None
    error: Optional[str] = None


@dataclass
class CampaignSummaryReport:
    """Final aggregate report for the campaign."""
    batch_id: str
    mode: str  # 'dry_run' or 'live'
    model_name: str
    total_planned: int
    completed: int
    failed: int
    skipped: int
    total_duration_ms: int
    total_input_tokens: int
    total_output_tokens: int
    total_neurons_consumed: int
    initial_neurons_used: int
    final_neurons_used: int
    remaining_budget_neurons: int
    actual_dollar_cost: float
    micro_precision: float
    micro_recall: float
    micro_f1: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    case_results: list[CampaignCaseExecutionResult] = field(default_factory=list)
    halt_reason: Optional[str] = None


class SafeCampaignRunner:
    """Orchestrates safe automated execution of Cases 03-08 with strict zero-cost enforcement."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        model_name: str = DEFAULT_MODEL,
        daily_neuron_limit: int = CONSERVATIVE_SAFETY_NEURON_LIMIT,
        max_input_tokens: int = 4096,
        max_output_tokens: int = 1536,
    ):
        self.db_path = db_path
        self._conn = get_connection(db_path)
        self.case_registry = CaseRegistry()
        self.context_manager = ContextManager()
        self.gt_repo = GroundTruthRepository(self._conn)
        self.exp_repo = ExperimentRepository(self._conn)
        self.batch_repo = BatchRepository(self._conn)
        self.attempt_repo = AttemptRepository(self._conn)
        self.resp_repo = ResponseRepository(self._conn)
        self.score_repo = AttemptScoreRepository(self._conn)
        self.neuron_tracker = NeuronTracker()
        self.orchestrator = BenchmarkOrchestrator(self._conn)
        self.model_name = model_name
        self.daily_neuron_limit = daily_neuron_limit
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens

    def audit_preflight(
        self,
        target_cases: Optional[list[int]] = None,
        context_condition: ContextCondition = ContextCondition.CODE_ONLY,
    ) -> CampaignPreflightResult:
        """Thorough preflight audit of all campaign cases, prompts, and neuron budget."""
        cases_to_run = target_cases or list(ALLOWED_CAMPAIGN_CASES)
        errors: list[str] = []

        # 1. Enforce strict scope boundary
        for c_num in cases_to_run:
            if c_num not in ALLOWED_CAMPAIGN_CASES:
                err = f"Scope violation: Case {c_num} is outside authorized campaign scope ({ALLOWED_CAMPAIGN_CASES})."
                errors.append(err)

        if errors:
            return CampaignPreflightResult(
                is_valid=False,
                allowed_cases=ALLOWED_CAMPAIGN_CASES,
                total_estimated_input_tokens=0,
                total_estimated_output_tokens=0,
                total_estimated_neurons=0,
                current_neurons_consumed=0,
                conservative_daily_limit=self.daily_neuron_limit,
                remaining_daily_budget=0,
                model_name=self.model_name,
                errors=errors,
            )

        # 2. Check Neuron tracker status (fail-closed)
        try:
            current_used = self.neuron_tracker.get_daily_used_neurons()
        except Exception as exc:
            errors.append(f"NeuronTracker verification failed (fail-closed): {exc}")
            current_used = self.daily_neuron_limit

        remaining_budget = max(0, self.daily_neuron_limit - current_used)

        case_audits: list[CasePreflightAudit] = []
        tot_in_tokens = 0
        tot_out_tokens = 0
        tot_neurons = 0

        # 3. Audit each individual case
        for c_num in cases_to_run:
            try:
                case = self.case_registry.load_case(c_num)
            except Exception as exc:
                errors.append(f"Failed to load Case {c_num}: {exc}")
                continue

            gts = self.gt_repo.list_for_case(case.id)
            if not gts:
                # Attempt to seed ground truths if missing
                self.orchestrator.scoring_service.seed_ground_truths([case.id])
                gts = self.gt_repo.list_for_case(case.id)

            if not gts:
                errors.append(f"Case {case.id} has no ground-truth defects registered.")
                continue

            defect_categories = [gt.defect_category.value for gt in gts]

            # Build exact prompt
            ctx = self.context_manager.build_context(c_num, context_condition)
            prompt_text = self.context_manager.format_review_prompt(ctx)
            prompt_chars = len(prompt_text)
            est_in = max(prompt_chars // 4, 50)
            est_out = min(self.max_output_tokens, 750)

            # Check input token boundary
            if est_in > self.max_input_tokens:
                errors.append(f"Case {case.id} prompt tokens ({est_in}) exceed max_input_tokens ({self.max_input_tokens}).")

            # Check ground-truth anti-leak protections
            leak_detected = False
            lower_prompt = prompt_text.lower()
            diff_idx = lower_prompt.find("## proposed code changes")
            non_diff_text = lower_prompt[:diff_idx] if diff_idx != -1 else lower_prompt

            for gt in gts:
                # 1. Must never contain ground truth defect identifier anywhere in prompt
                if gt.id.lower() in lower_prompt:
                    errors.append(f"LEAK DETECTED in Case {case.id}: prompt contains defect ID '{gt.id}'.")
                    leak_detected = True

                # 2. Must never contain explicit ground-truth answer labels or category headers
                for header in ("defect category:", "ground truth:", "expected action:", "expected defect:"):
                    if header in lower_prompt:
                        errors.append(f"LEAK DETECTED in Case {case.id}: prompt contains ground truth header '{header}'.")
                        leak_detected = True

                # 3. Non-diff PR metadata (title/description) must never leak defect explanation
                desc_words = [w.lower() for w in gt.description.split() if len(w) > 3]
                for i in range(len(desc_words) - 3):
                    chunk = " ".join(desc_words[i:i+4])
                    if chunk in non_diff_text:
                        errors.append(f"LEAK DETECTED in Case {case.id}: PR description contains defect explanation phrase '{chunk}'.")
                        leak_detected = True
                        break

                # 4. Must never contain expected verdict / action tag
                if f"expected_action: {gt.expected_action.lower()}" in lower_prompt or f"verdict: {gt.expected_action.lower()}" in lower_prompt:
                    errors.append(f"LEAK DETECTED in Case {case.id}: prompt contains expected action '{gt.expected_action}'.")
                    leak_detected = True

            # Ensure CODE_ONLY never contains snapshot files
            if context_condition == ContextCondition.CODE_ONLY and ctx.snapshot_content:
                errors.append(f"CONTEXT VIOLATION in Case {case.id}: CODE_ONLY prompt contains deployment snapshot.")
                leak_detected = True

            # Estimate compute
            est_neurons = self.neuron_tracker.estimate_neurons(self.model_name, est_in, est_out)
            tot_in_tokens += est_in
            tot_out_tokens += est_out
            tot_neurons += est_neurons

            case_audits.append(
                CasePreflightAudit(
                    case_number=c_num,
                    case_id=case.id,
                    case_title=case.title,
                    context_condition=context_condition.value,
                    ground_truth_count=len(gts),
                    defect_categories=defect_categories,
                    prompt_length_chars=prompt_chars,
                    estimated_input_tokens=est_in,
                    estimated_output_tokens=est_out,
                    estimated_neurons=est_neurons,
                    leak_check_passed=not leak_detected,
                    status="VALID" if not leak_detected else "FAILED_LEAK_CHECK",
                )
            )

        # 4. Enforce aggregate budget limit
        if (current_used + tot_neurons) > self.daily_neuron_limit:
            errors.append(
                f"Budget violation: Total required Neurons ({tot_neurons}) plus current usage ({current_used}) "
                f"exceeds conservative daily limit ({self.daily_neuron_limit})."
            )

        is_valid = (len(errors) == 0) and all(a.leak_check_passed for a in case_audits)

        return CampaignPreflightResult(
            is_valid=is_valid,
            allowed_cases=cases_to_run,
            total_estimated_input_tokens=tot_in_tokens,
            total_estimated_output_tokens=tot_out_tokens,
            total_estimated_neurons=tot_neurons,
            current_neurons_consumed=current_used,
            conservative_daily_limit=self.daily_neuron_limit,
            remaining_daily_budget=remaining_budget,
            model_name=self.model_name,
            case_audits=case_audits,
            errors=errors,
        )

    def execute_dry_run(
        self,
        target_cases: Optional[list[int]] = None,
        context_condition: ContextCondition = ContextCondition.CODE_ONLY,
    ) -> CampaignSummaryReport:
        """Simulate campaign execution in dry-run mode without external network requests."""
        audit = self.audit_preflight(target_cases=target_cases, context_condition=context_condition)
        if not audit.is_valid:
            raise CampaignValidationError(f"Campaign preflight failed validation: {'; '.join(audit.errors)}")

        case_results: list[CampaignCaseExecutionResult] = []
        tot_in = 0
        tot_out = 0
        tot_neurons = 0

        for a in audit.case_audits:
            simulated_content = (
                f"# Simulated Review for {a.case_id}\n\n"
                f"### Finding: Boundary Check\n"
                f"- **Severity:** High\n"
                f"- **Target:** reports.py\n"
                f"Simulated dry-run review response for campaign case {a.case_number}."
            )
            sim_sha = hashlib.sha256(simulated_content.encode("utf-8")).hexdigest()

            tot_in += a.estimated_input_tokens
            tot_out += a.estimated_output_tokens
            tot_neurons += a.estimated_neurons

            case_results.append(
                CampaignCaseExecutionResult(
                    case_number=a.case_number,
                    case_id=a.case_id,
                    attempt_id=f"dry-att-case{a.case_number:02d}",
                    status="DRY_RUN",
                    http_status=200,
                    duration_ms=50,
                    prompt_tokens=a.estimated_input_tokens,
                    completion_tokens=a.estimated_output_tokens,
                    neurons_consumed=a.estimated_neurons,
                    tp_count=1,
                    fp_count=0,
                    fn_count=0,
                    precision=1.0,
                    recall=1.0,
                    f1_score=1.0,
                    passed_cleanly=True,
                    evidence_file=f"dry_run/{a.case_id}.md",
                    content_hash_sha256=sim_sha,
                )
            )

        return CampaignSummaryReport(
            batch_id="dry-run-campaign-cases-03-08",
            mode="dry_run",
            model_name=self.model_name,
            total_planned=len(case_results),
            completed=len(case_results),
            failed=0,
            skipped=0,
            total_duration_ms=300,
            total_input_tokens=tot_in,
            total_output_tokens=tot_out,
            total_neurons_consumed=tot_neurons,
            initial_neurons_used=audit.current_neurons_consumed,
            final_neurons_used=audit.current_neurons_consumed,  # No actual neurons consumed in dry-run
            remaining_budget_neurons=audit.remaining_daily_budget,
            actual_dollar_cost=0.0,
            micro_precision=1.0,
            micro_recall=1.0,
            micro_f1=1.0,
            macro_precision=1.0,
            macro_recall=1.0,
            macro_f1=1.0,
            case_results=case_results,
        )

    def execute_live_campaign(
        self,
        authorized: bool = False,
        target_cases: Optional[list[int]] = None,
        context_condition: ContextCondition = ContextCondition.CODE_ONLY,
    ) -> CampaignSummaryReport:
        """Sequentially execute genuine live reviews with fail-closed stop on any error."""
        if not authorized:
            raise PermissionError(
                "Live campaign execution not authorized. You must pass authorized=True with explicit user approval."
            )

        audit = self.audit_preflight(target_cases=target_cases, context_condition=context_condition)
        if not audit.is_valid:
            raise CampaignValidationError(f"Campaign preflight failed validation: {'; '.join(audit.errors)}")

        initial_neurons = self.neuron_tracker.get_daily_used_neurons()
        cases_to_run = target_cases or list(ALLOWED_CAMPAIGN_CASES)

        # Ensure parent experiment exists
        exp_id = "exp-cloudflare-campaign"
        if not self.exp_repo.get_by_id(exp_id):
            self.exp_repo.create(
                Experiment(
                    id=exp_id,
                    name="Cloudflare Workers AI Campaign",
                    scoring_protocol_version="v1.0",
                )
            )

        # Create campaign execution batch
        batch_id = f"batch-campaign-{datetime.now(timezone.utc).strftime('%m%d%H%M')}"
        batch = ExecutionBatch(
            id=batch_id,
            experiment_id=exp_id,
            batch_name=f"Cloudflare Workers AI Campaign (Cases {cases_to_run[0]:02d}-{cases_to_run[-1]:02d})",
            planned_attempts_count=len(cases_to_run),
            status="running",
        )
        self.batch_repo.create(batch)

        # Pre-create all scheduled review attempts in PENDING state
        scheduled_attempts: dict[int, ReviewAttempt] = {}
        for c_num in cases_to_run:
            case = self.case_registry.load_case(c_num)
            self.orchestrator.case_repo.register(case)
            self.orchestrator.scoring_service.seed_ground_truths([case.id])

            att_id = f"att-cf-c{c_num:02d}-{datetime.now(timezone.utc).strftime('%H%M%S')}"
            attempt = ReviewAttempt(
                id=att_id,
                batch_id=batch_id,
                provider_id="cloudflare",
                case_id=case.id,
                context_condition=context_condition,
                model_name=self.model_name,
                settings_hash="settings:cloudflare:campaign:v1",
                base_commit=case.baseline_commit,
                head_commit=case.target_commit,
                attempt_type=AttemptType.INITIAL,
                attempt_number=1,
                status=AttemptStatus.PENDING,
            )
            self.attempt_repo.create(attempt)
            scheduled_attempts[c_num] = attempt

        self._conn.commit()

        # Instantiate live Cloudflare adapter with strict zero-cost configuration
        adapter = CloudflareAdapter(
            CloudflareConfig(
                provider_id="cloudflare",
                display_name="Cloudflare Workers AI",
                default_model=self.model_name,
                api_key_env_var="CLOUDFLARE_API_TOKEN",
                account_id_env_var="CLOUDFLARE_ACCOUNT_ID",
                daily_neuron_limit=self.daily_neuron_limit,
                max_input_tokens=self.max_input_tokens,
                max_output_tokens=self.max_output_tokens,
                max_tokens=self.max_output_tokens,
                max_retries=0,  # Strict zero-retry policy
                allow_paid_overage=False,  # Strict zero-cost policy
            )
        )

        case_results: list[CampaignCaseExecutionResult] = []
        halt_reason: Optional[str] = None
        total_duration = 0
        total_in_tok = 0
        total_out_tok = 0

        # Sequentially execute each case
        for c_num in cases_to_run:
            att = scheduled_attempts[c_num]

            # Pre-invocation budget check (re-checked before every individual case dispatch)
            curr_used = self.neuron_tracker.get_daily_used_neurons()
            case_audit = next((ca for ca in audit.case_audits if ca.case_number == c_num), None)
            case_est = case_audit.estimated_neurons if case_audit else 100
            if (curr_used + case_est) > self.daily_neuron_limit:
                halt_reason = (
                    f"HALTED: Daily Neuron budget ceiling reached before Case {c_num}. "
                    f"Current usage: {curr_used}, Needed: {case_est}, Daily Limit: {self.daily_neuron_limit}."
                )
                break

            try:
                t0 = time.perf_counter()
                completed_attempt = self.orchestrator.execute_attempt(att, adapter, max_retries=0)
                dur = completed_attempt.duration_ms or int((time.perf_counter() - t0) * 1000)
                total_duration += dur

                if completed_attempt.status != AttemptStatus.COMPLETED:
                    halt_reason = f"HALTED: Attempt {att.id} ended in status {completed_attempt.status.value}: {completed_attempt.error_reason}"
                    case_results.append(
                        CampaignCaseExecutionResult(
                            case_number=c_num,
                            case_id=att.case_id,
                            attempt_id=att.id,
                            status="FAILED",
                            error=completed_attempt.error_reason,
                        )
                    )
                    break

                # Retrieve saved response and scores
                resp = self.resp_repo.get_by_attempt_id(att.id)
                score = self.score_repo.get_by_attempt_id(att.id)

                p_tok = resp.prompt_tokens or 0
                c_tok = resp.completion_tokens or 0
                total_in_tok += p_tok
                total_out_tok += c_tok

                # Calculate neurons for this attempt
                case_neurons = self.neuron_tracker.estimate_neurons(self.model_name, p_tok, c_tok)

                # Locate saved evidence file
                ev_dir = PROJECT_ROOT / "evidence" / "raw" / batch_id
                ev_file = ev_dir / f"{att.id}.md"
                ev_meta = ev_dir / f"{att.id}.meta.json"
                meta_data = json.loads(ev_meta.read_text(encoding="utf-8")) if ev_meta.is_file() else {}

                case_results.append(
                    CampaignCaseExecutionResult(
                        case_number=c_num,
                        case_id=att.case_id,
                        attempt_id=att.id,
                        status="COMPLETED",
                        http_status=resp.http_status,
                        duration_ms=dur,
                        prompt_tokens=p_tok,
                        completion_tokens=c_tok,
                        neurons_consumed=case_neurons,
                        tp_count=score.tp_count if score else 0,
                        fp_count=score.fp_count if score else 0,
                        fn_count=score.fn_count if score else 0,
                        precision=score.precision_rate if score else 0.0,
                        recall=score.recall_rate if score else 0.0,
                        f1_score=score.f1_metric if score else 0.0,
                        passed_cleanly=score.passed_cleanly if score else False,
                        evidence_file=str(ev_file),
                        content_hash_sha256=meta_data.get("content_hash_sha256"),
                    )
                )

            except Exception as exc:
                halt_reason = f"HALTED: Unexpected error during Case {c_num} execution: {exc}"
                case_results.append(
                    CampaignCaseExecutionResult(
                        case_number=c_num,
                        case_id=att.case_id,
                        attempt_id=att.id,
                        status="FAILED",
                        error=str(exc),
                    )
                )
                break

        final_neurons = self.neuron_tracker.get_daily_used_neurons()
        actual_campaign_neurons = max(0, final_neurons - initial_neurons)

        # Mark skipped cases if halted early
        executed_cases = {res.case_number for res in case_results}
        skipped_count = 0
        for c_num in cases_to_run:
            if c_num not in executed_cases:
                skipped_count += 1
                case_results.append(
                    CampaignCaseExecutionResult(
                        case_number=c_num,
                        case_id=f"case-{c_num:02d}",
                        attempt_id=f"skipped-{c_num}",
                        status="SKIPPED",
                        error=f"Skipped due to campaign halt: {halt_reason}",
                    )
                )

        # Update batch status
        completed_count = sum(1 for r in case_results if r.status == "COMPLETED")
        failed_count = sum(1 for r in case_results if r.status == "FAILED")
        batch_status = "completed" if (completed_count == len(cases_to_run)) else "interrupted"
        self.batch_repo.update_status(batch_id, batch_status, datetime.now(timezone.utc).isoformat())
        self._conn.commit()

        # Calculate micro and macro metrics
        tot_tp = sum(r.tp_count for r in case_results if r.status == "COMPLETED")
        tot_fp = sum(r.fp_count for r in case_results if r.status == "COMPLETED")
        tot_fn = sum(r.fn_count for r in case_results if r.status == "COMPLETED")

        micro_p = tot_tp / (tot_tp + tot_fp) if (tot_tp + tot_fp) > 0 else 0.0
        micro_r = tot_tp / (tot_tp + tot_fn) if (tot_tp + tot_fn) > 0 else 0.0
        micro_f1 = (2 * micro_p * micro_r) / (micro_p + micro_r) if (micro_p + micro_r) > 0 else 0.0

        completed_results = [r for r in case_results if r.status == "COMPLETED"]
        if completed_results:
            macro_p = sum(r.precision for r in completed_results) / len(completed_results)
            macro_r = sum(r.recall for r in completed_results) / len(completed_results)
            macro_f1 = sum(r.f1_score for r in completed_results) / len(completed_results)
        else:
            macro_p, macro_r, macro_f1 = 0.0, 0.0, 0.0

        return CampaignSummaryReport(
            batch_id=batch_id,
            mode="live",
            model_name=self.model_name,
            total_planned=len(cases_to_run),
            completed=completed_count,
            failed=failed_count,
            skipped=skipped_count,
            total_duration_ms=total_duration,
            total_input_tokens=total_in_tok,
            total_output_tokens=total_out_tok,
            total_neurons_consumed=actual_campaign_neurons,
            initial_neurons_used=initial_neurons,
            final_neurons_used=final_neurons,
            remaining_budget_neurons=max(0, self.daily_neuron_limit - final_neurons),
            actual_dollar_cost=0.0,
            micro_precision=round(micro_p, 4),
            micro_recall=round(micro_r, 4),
            micro_f1=round(micro_f1, 4),
            macro_precision=round(macro_p, 4),
            macro_recall=round(macro_r, 4),
            macro_f1=round(macro_f1, 4),
            case_results=case_results,
            halt_reason=halt_reason,
        )
