"""Benchmark matrix generators for provider comparisons, ablation studies, and denominators."""

from dataclasses import dataclass, field
from typing import Any, Optional

from benchmark.db.repositories import (
    AttemptRepository,
    AttemptScoreRepository,
    BatchRepository,
    CaseRepository,
    EvaluationRepository,
    FindingRepository,
    ProviderRepository,
)
from benchmark.domain.enums import AttemptStatus, ContextCondition


@dataclass
class MatrixCell:
    status: str
    outcome: str
    f1_score: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    duration_ms: Optional[int] = None
    findings_count: int = 0
    cites_evidence: bool = False


@dataclass
class ProviderSummary:
    provider_id: str
    total_planned: int = 0
    completed: int = 0
    tp_count: int = 0
    fp_count: int = 0
    fn_count: int = 0
    clean_passes: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    mean_duration_ms: float = 0.0


@dataclass
class ProviderCaseMatrix:
    batch_id: str
    providers: list[str]
    cases: list[str]
    matrix: dict[str, dict[str, MatrixCell]]  # provider_id -> case_id -> MatrixCell
    provider_summaries: dict[str, ProviderSummary] = field(default_factory=dict)


@dataclass
class AblationRow:
    provider_id: str
    case_id: str
    code_only_status: str
    code_only_f1: Optional[float]
    code_only_detected: bool
    code_only_cites_evidence: bool
    snapshot_status: str
    snapshot_f1: Optional[float]
    snapshot_detected: bool
    snapshot_cites_evidence: bool
    f1_delta: float
    evidence_gain: bool


@dataclass
class AblationMatrix:
    batch_id: str
    cases_analyzed: list[str]
    rows: list[AblationRow] = field(default_factory=list)


@dataclass
class ProviderDenominator:
    provider_id: str
    planned: int = 0
    completed: int = 0
    quota_halted: int = 0
    failed: int = 0
    pending: int = 0
    completion_rate_pct: float = 0.0


@dataclass
class DenominatorSummary:
    batch_id: str
    planned_total: int = 0
    completed_total: int = 0
    quota_halted_total: int = 0
    failed_total: int = 0
    pending_total: int = 0
    completion_rate_pct: float = 0.0
    providers: dict[str, ProviderDenominator] = field(default_factory=dict)


class BenchmarkMatrixGenerator:
    """Generates comparison matrices, ablation tables, and denominator summaries from DB."""

    def __init__(self, db):
        self.db = db
        self.batch_repo = BatchRepository(db)
        self.attempt_repo = AttemptRepository(db)
        self.score_repo = AttemptScoreRepository(db)
        self.finding_repo = FindingRepository(db)
        self.eval_repo = EvaluationRepository(db)
        self.case_repo = CaseRepository(db)
        self.prov_repo = ProviderRepository(db)

    def generate_provider_case_matrix(
        self,
        batch_id: str,
        context_condition: Optional[ContextCondition] = None,
    ) -> ProviderCaseMatrix:
        """Generate provider-versus-case comparison matrix for a batch."""
        attempts = self.attempt_repo.list_for_batch(batch_id)
        if context_condition:
            attempts = [a for a in attempts if a.context_condition == context_condition]

        providers = sorted(list({a.provider_id for a in attempts}))
        cases = sorted(list({a.case_id for a in attempts}))

        matrix: dict[str, dict[str, MatrixCell]] = {p: {} for p in providers}
        provider_stats: dict[str, dict[str, Any]] = {
            p: {
                "total": 0,
                "completed": 0,
                "tp": 0,
                "fp": 0,
                "fn": 0,
                "clean_passes": 0,
                "durations": [],
            }
            for p in providers
        }

        for att in attempts:
            p_id = att.provider_id
            c_id = att.case_id
            provider_stats[p_id]["total"] += 1

            if att.status != AttemptStatus.COMPLETED:
                matrix[p_id][c_id] = MatrixCell(
                    status=att.status.value,
                    outcome=att.status.value,
                    duration_ms=att.duration_ms,
                )
                continue

            provider_stats[p_id]["completed"] += 1
            if att.duration_ms:
                provider_stats[p_id]["durations"].append(att.duration_ms)

            score = self.score_repo.get_by_attempt_id(att.id)
            evals = self.eval_repo.list_for_attempt(att.id)
            findings = self.finding_repo.list_for_attempt(att.id)
            cites_evidence = any(e.cites_deployment_evidence for e in evals)

            if score:
                provider_stats[p_id]["tp"] += score.tp_count
                provider_stats[p_id]["fp"] += score.fp_count
                provider_stats[p_id]["fn"] += score.fn_count
                if score.passed_cleanly:
                    provider_stats[p_id]["clean_passes"] += 1

                if score.passed_cleanly and score.tp_count == 0 and score.fp_count == 0:
                    outcome = "CLEAN_PASS"
                elif score.tp_count > 0 and score.fp_count == 0:
                    outcome = "TRUE_POSITIVE"
                elif score.tp_count > 0 and score.fp_count > 0:
                    outcome = "MIXED"
                elif score.fp_count > 0:
                    outcome = "FALSE_POSITIVE"
                else:
                    outcome = "FALSE_NEGATIVE"

                matrix[p_id][c_id] = MatrixCell(
                    status=att.status.value,
                    outcome=outcome,
                    f1_score=score.f1_metric,
                    precision=score.precision_rate,
                    recall=score.recall_rate,
                    duration_ms=att.duration_ms,
                    findings_count=len(findings),
                    cites_evidence=cites_evidence,
                )
            else:
                matrix[p_id][c_id] = MatrixCell(
                    status=att.status.value,
                    outcome="UNSCORED",
                    duration_ms=att.duration_ms,
                    findings_count=len(findings),
                    cites_evidence=cites_evidence,
                )

        # Compute provider summary rollups
        summaries: dict[str, ProviderSummary] = {}
        for p_id in providers:
            st = provider_stats[p_id]
            tp = st["tp"]
            fp = st["fp"]
            fn = st["fn"]
            prec = (tp / (tp + fp)) if (tp + fp) > 0 else (1.0 if st["clean_passes"] > 0 else 0.0)
            rec = (tp / (tp + fn)) if (tp + fn) > 0 else (1.0 if st["clean_passes"] > 0 else 0.0)
            f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
            mean_dur = sum(st["durations"]) / len(st["durations"]) if st["durations"] else 0.0

            summaries[p_id] = ProviderSummary(
                provider_id=p_id,
                total_planned=st["total"],
                completed=st["completed"],
                tp_count=tp,
                fp_count=fp,
                fn_count=fn,
                clean_passes=st["clean_passes"],
                precision=round(prec, 4),
                recall=round(rec, 4),
                f1_score=round(f1, 4),
                mean_duration_ms=round(mean_dur, 1),
            )

        return ProviderCaseMatrix(
            batch_id=batch_id,
            providers=providers,
            cases=cases,
            matrix=matrix,
            provider_summaries=summaries,
        )

    def generate_ablation_matrix(
        self,
        batch_id: str,
        target_case_ids: Optional[list[str]] = None,
    ) -> AblationMatrix:
        """Generate ablation study comparing CODE_ONLY vs CODE_AND_SNAPSHOT performance."""
        attempts = self.attempt_repo.list_for_batch(batch_id)
        if target_case_ids is None:
            # Default to snapshot cases (case-04, case-05, case-06)
            target_case_ids = ["case-04", "case-05", "case-06"]

        providers = sorted(list({a.provider_id for a in attempts}))
        rows: list[AblationRow] = []

        for p_id in providers:
            for c_id in target_case_ids:
                att_code = next(
                    (a for a in attempts if a.provider_id == p_id and a.case_id == c_id and a.context_condition == ContextCondition.CODE_ONLY),
                    None,
                )
                att_snap = next(
                    (a for a in attempts if a.provider_id == p_id and a.case_id == c_id and a.context_condition == ContextCondition.CODE_AND_SNAPSHOT),
                    None,
                )

                if not att_code and not att_snap:
                    continue

                code_status = att_code.status.value if att_code else "NOT_RUN"
                snap_status = att_snap.status.value if att_snap else "NOT_RUN"

                code_score = self.score_repo.get_by_attempt_id(att_code.id) if att_code else None
                snap_score = self.score_repo.get_by_attempt_id(att_snap.id) if att_snap else None

                code_evals = self.eval_repo.list_for_attempt(att_code.id) if att_code else []
                snap_evals = self.eval_repo.list_for_attempt(att_snap.id) if att_snap else []

                code_detected = (code_score.tp_count > 0) if code_score else False
                snap_detected = (snap_score.tp_count > 0) if snap_score else False

                code_cites = any(e.cites_deployment_evidence for e in code_evals)
                snap_cites = any(e.cites_deployment_evidence for e in snap_evals)

                code_f1 = code_score.f1_metric if code_score else 0.0
                snap_f1 = snap_score.f1_metric if snap_score else 0.0
                f1_delta = round((snap_f1 or 0.0) - (code_f1 or 0.0), 4)
                evidence_gain = snap_cites and not code_cites

                rows.append(
                    AblationRow(
                        provider_id=p_id,
                        case_id=c_id,
                        code_only_status=code_status,
                        code_only_f1=code_f1,
                        code_only_detected=code_detected,
                        code_only_cites_evidence=code_cites,
                        snapshot_status=snap_status,
                        snapshot_f1=snap_f1,
                        snapshot_detected=snap_detected,
                        snapshot_cites_evidence=snap_cites,
                        f1_delta=f1_delta,
                        evidence_gain=evidence_gain,
                    )
                )

        return AblationMatrix(
            batch_id=batch_id,
            cases_analyzed=target_case_ids,
            rows=rows,
        )

    def generate_denominator_summary(self, batch_id: str) -> DenominatorSummary:
        """Generate visibility table of planned vs completed/quota/failed denominators."""
        batch = self.batch_repo.get_by_id(batch_id)
        attempts = self.attempt_repo.list_for_batch(batch_id)

        providers = sorted(list({a.provider_id for a in attempts}))
        prov_map: dict[str, ProviderDenominator] = {}

        total_planned = batch.planned_attempts_count if batch else len(attempts)
        total_completed = 0
        total_quota = 0
        total_failed = 0
        total_pending = 0

        for p_id in providers:
            p_attempts = [a for a in attempts if a.provider_id == p_id]
            planned = len(p_attempts)
            completed = sum(1 for a in p_attempts if a.status == AttemptStatus.COMPLETED)
            quota_halted = sum(1 for a in p_attempts if a.status == AttemptStatus.QUOTA_EXHAUSTED)
            failed = sum(1 for a in p_attempts if a.status == AttemptStatus.FAILED)
            pending = sum(1 for a in p_attempts if a.status == AttemptStatus.PENDING)

            total_completed += completed
            total_quota += quota_halted
            total_failed += failed
            total_pending += pending

            pct = round((completed / planned * 100), 1) if planned > 0 else 0.0
            prov_map[p_id] = ProviderDenominator(
                provider_id=p_id,
                planned=planned,
                completed=completed,
                quota_halted=quota_halted,
                failed=failed,
                pending=pending,
                completion_rate_pct=pct,
            )

        total_pct = round((total_completed / total_planned * 100), 1) if total_planned > 0 else 0.0

        return DenominatorSummary(
            batch_id=batch_id,
            planned_total=total_planned,
            completed_total=total_completed,
            quota_halted_total=total_quota,
            failed_total=total_failed,
            pending_total=total_pending,
            completion_rate_pct=total_pct,
            providers=prov_map,
        )
