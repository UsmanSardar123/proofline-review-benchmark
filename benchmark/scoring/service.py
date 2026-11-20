"""Scoring service and ground truth evaluation for review findings."""

from datetime import datetime, timezone
from typing import Optional
import uuid

from benchmark.db.repositories import (
    AttemptRepository,
    AttemptScoreRepository,
    CaseRepository,
    EvaluationRepository,
    FindingRepository,
    GroundTruthRepository,
)
from benchmark.domain.enums import AttemptStatus, ContextCondition, DefectCategory, EvaluationClass
from benchmark.domain.models import (
    AttemptScore,
    FindingEvaluation,
    GroundTruthDefect,
    ReviewAttempt,
    ReviewFinding,
)
from benchmark.scoring.calibration import CalibrationProfile, STANDARD_PROFILE
from benchmark.scoring.matcher import FindingMatcher, MatchResult
from benchmark.scoring.metrics import MetricSummary, ScoringCalculator
from benchmark.scoring.quality import FindingQualityEvaluator


STANDARD_GROUND_TRUTHS = {
    "case-01": {
        "defect_category": DefectCategory.LOGIC_BUG,
        "description": "Cursor pagination by scheduled_at without tie-breaker breaks when multiple jobs share the same timestamp",
        "target_file": "reports.py",
        "target_lines": "42-50",
        "requires_snapshot": False,
        "expected_action": "BLOCK_PR",
        "detection_keywords": ["cursor", "scheduled_at", "tie", "duplicate", "pagination", "order by", "opaque"],
        "evidence_keywords": [],
    },
    "case-02": {
        "defect_category": DefectCategory.DATA_INTEGRITY,
        "description": "Manual CSV concatenation without escaping commas or quotes corrupts output when report name has special characters",
        "target_file": "reports.py",
        "target_lines": "50-57",
        "requires_snapshot": False,
        "expected_action": "BLOCK_PR",
        "detection_keywords": ["csv", "escape", "comma", "quote", "format", "join", "writer", "delimiter"],
        "evidence_keywords": [],
    },
    "case-03": {
        "defect_category": DefectCategory.LOGIC_BUG,
        "description": "Batching loop with range(0, len(jobs) - batch_size + 1, batch_size) drops remaining jobs when len(jobs) < 20 or non-multiple of 20",
        "target_file": "reports.py",
        "target_lines": "73-90",
        "requires_snapshot": False,
        "expected_action": "BLOCK_PR",
        "detection_keywords": ["batch", "range", "remainder", "drop", "skip", "batch_size", "unprocessed", "len(jobs)", "off-by-one"],
        "evidence_keywords": [],
    },
    "case-04": {
        "defect_category": DefectCategory.DEPLOYMENT_CONFLICT,
        "description": "Dropping legacy_format column breaks active Elm site workers running older workers-17 revision polling that column",
        "target_file": "migrations/002_retire_format.sql",
        "target_lines": "1",
        "requires_snapshot": True,
        "expected_action": "BLOCK_PR",
        "detection_keywords": ["legacy_format", "drop column", "elm", "workers-17", "poll_sql", "active worker", "backward"],
        "evidence_keywords": ["elm", "workers-17", "inventory-204", "poll_sql", "active worker"],
    },
    "case-05": {
        "defect_category": DefectCategory.CONFIG_LIMIT,
        "description": "Increasing EXPORT_BATCH_SIZE to 50 exceeds Cedar site receiver max_rows_per_request limit of 40",
        "target_file": "reports.py",
        "target_lines": "10",
        "requires_snapshot": True,
        "expected_action": "BLOCK_PR",
        "detection_keywords": ["cedar", "batch size", "export_batch_size", "40", "max_rows", "receiver", "limit", "reject", "oversized"],
        "evidence_keywords": ["cedar", "max_rows_per_request", "archive-318", "archive-11", "40"],
    },
    "case-06": {
        "defect_category": DefectCategory.DEPLOYMENT_CONFLICT,
        "description": "Switching DELIVERY_QUEUE to 'report-dispatch' leaves Elm site workers starved as they only subscribe to 'reports'",
        "target_file": "reports.py",
        "target_lines": "9",
        "requires_snapshot": True,
        "expected_action": "BLOCK_PR",
        "detection_keywords": ["elm", "delivery_queue", "report-dispatch", "subscribe", "consumer", "queue", "starve", "orphan"],
        "evidence_keywords": ["elm", "subscribed_queues", "subscriptions-416", "report-dispatch"],
    },
    "case-07": {
        "defect_category": DefectCategory.PERFORMANCE,
        "description": "Benign/Clean PR: Adds deliveries_due_by_queue partial index for pending deliveries. Expected action is APPROVE.",
        "target_file": "migrations/002_pending_by_queue.sql",
        "target_lines": "1-2",
        "requires_snapshot": False,
        "expected_action": "APPROVE",
        "detection_keywords": [],
        "evidence_keywords": [],
    },
    "case-08": {
        "defect_category": DefectCategory.CONTRACT_CHANGE,
        "description": "Benign/Clean PR: Adds total count to summary dictionary. Expected action is APPROVE.",
        "target_file": "reports.py",
        "target_lines": "86",
        "requires_snapshot": False,
        "expected_action": "APPROVE",
        "detection_keywords": [],
        "evidence_keywords": [],
    },
}


class ScoringService:
    """Evaluates extracted review findings against ground truth and calculates scores."""

    def __init__(
        self,
        db,
        calibration_profile: Optional[CalibrationProfile] = None,
    ):
        self.db = db
        self.gt_repo = GroundTruthRepository(db)
        self.case_repo = CaseRepository(db)
        self.attempt_repo = AttemptRepository(db)
        self.finding_repo = FindingRepository(db)
        self.eval_repo = EvaluationRepository(db)
        self.score_repo = AttemptScoreRepository(db)

        self.calibration_profile = calibration_profile or STANDARD_PROFILE
        self.matcher = FindingMatcher(self.calibration_profile.to_matching_config())
        self.quality_evaluator = FindingQualityEvaluator()

    def set_calibration_profile(self, profile: CalibrationProfile) -> None:
        """Update active calibration profile for scoring and matching."""
        self.calibration_profile = profile
        self.matcher = FindingMatcher(profile.to_matching_config())

    def seed_ground_truths(self, case_ids: Optional[list[str]] = None) -> list[GroundTruthDefect]:
        """Seed authoritative ground truth definitions into ground_truth_defects table."""
        seeded = []
        for case_id, meta in STANDARD_GROUND_TRUTHS.items():
            if case_ids is not None and case_id not in case_ids:
                continue
            # Only seed if case is registered in DB to satisfy FOREIGN KEY constraint
            if not self.case_repo.get_by_id(case_id):
                continue
            gt_id = f"gt-{case_id}"
            defect = GroundTruthDefect(
                id=gt_id,
                case_id=case_id,
                defect_category=meta["defect_category"],
                description=meta["description"],
                target_file=meta["target_file"],
                target_lines=meta["target_lines"],
                requires_snapshot=meta["requires_snapshot"],
                expected_action=meta["expected_action"],
            )
            self.gt_repo.save(defect)
            seeded.append(defect)
        return seeded

    def evaluate_attempt(self, attempt_id: str) -> AttemptScore:
        """Evaluate findings for an attempt against ground truth and persist AttemptScore."""
        attempt = self.attempt_repo.get_by_id(attempt_id)
        if not attempt:
            raise ValueError(f"Attempt not found: {attempt_id}")

        findings = self.finding_repo.list_for_attempt(attempt_id)
        case_id = attempt.case_id
        meta = STANDARD_GROUND_TRUTHS.get(case_id)
        
        # Ensure ground truth is seeded for this case
        gt_defects = self.gt_repo.list_for_case(case_id)
        if not gt_defects and case_id in STANDARD_GROUND_TRUTHS:
            self.seed_ground_truths([case_id])
            gt_defects = self.gt_repo.list_for_case(case_id)
        gt = gt_defects[0] if gt_defects else None

        now_str = datetime.now(timezone.utc).isoformat()
        score_id = f"score-{uuid.uuid4().hex[:12]}"

        # Handle non-completed attempts
        if attempt.status != AttemptStatus.COMPLETED:
            is_clean_case = meta and meta["expected_action"] == "APPROVE"
            score = AttemptScore(
                id=score_id,
                attempt_id=attempt_id,
                tp_count=0,
                fp_count=0,
                fn_count=0 if is_clean_case else 1,
                vuf_count=0,
                precision_rate=0.0,
                recall_rate=0.0,
                f1_metric=0.0,
                passed_cleanly=False,
                computed_at=now_str,
            )
            return self.score_repo.save(score)

        is_clean_case = meta and meta["expected_action"] == "APPROVE"

        if is_clean_case:
            # Case 07 and 08: Clean changes
            # Any finding reporting high/critical severity or claiming a bug is false positive
            fp_count = 0
            vuf_count = 0
            evaluations = []
            quality_list = []

            for f in findings:
                sev = (f.reported_severity or "").lower()
                q = self.quality_evaluator.evaluate_finding(f, cites_deployment_evidence=False)
                quality_list.append(q)

                is_spurious_defect = sev in ("high", "critical", "error", "blocker") or any(
                    kw in f.summary.lower() for kw in ["bug", "defect", "error", "broken", "vulnerability"]
                )
                if is_spurious_defect:
                    fp_count += 1
                    classification = EvaluationClass.FALSE_POSITIVE
                    rationale = "Spurious defect reported on clean change"
                else:
                    vuf_count += 1
                    classification = EvaluationClass.VALID_UNEXPECTED
                    rationale = "Non-blocking code quality observation"

                eval_rec = FindingEvaluation(
                    id=f"eval-{uuid.uuid4().hex[:12]}",
                    finding_id=f.id,
                    classification=classification,
                    ground_truth_id=gt.id if gt else None,
                    cites_deployment_evidence=False,
                    evaluator_type="rule_matcher",
                    rationale=rationale,
                    evaluated_at=now_str,
                )
                evaluations.append(eval_rec)

            self.eval_repo.save_all(evaluations)

            mean_spec = sum(q.specificity_score for q in quality_list) / len(quality_list) if quality_list else 1.0
            mean_act = sum(q.actionability_score for q in quality_list) / len(quality_list) if quality_list else 1.0

            metric = ScoringCalculator.calculate_metrics(
                tp=0,
                fp=fp_count,
                fn=0,
                vuf=vuf_count,
                duplicates=0,
                is_clean_case=True,
                mean_specificity=round(mean_spec, 2),
                mean_actionability=round(mean_act, 2),
            )

            score = AttemptScore(
                id=score_id,
                attempt_id=attempt_id,
                tp_count=0,
                fp_count=metric.fp_count,
                fn_count=0,
                vuf_count=metric.vuf_count,
                precision_rate=metric.precision,
                recall_rate=metric.recall,
                f1_metric=metric.f1_score,
                passed_cleanly=metric.passed_cleanly,
                computed_at=now_str,
            )
            return self.score_repo.save(score)

        # Cases 01-06: Changes containing genuine defects
        detection_keywords = meta.get("detection_keywords", []) if meta else []
        evidence_keywords = meta.get("evidence_keywords", []) if meta else []

        tp_count = 0
        fp_count = 0
        duplicate_count = 0
        vuf_count = 0
        matched_gt = False
        evaluations = []
        quality_list = []

        for f in findings:
            # Use FindingMatcher for robust location and semantic matching
            match_res: MatchResult = self.matcher.match(
                finding=f,
                defect=gt,
                detection_keywords=detection_keywords,
                evidence_keywords=evidence_keywords,
            )
            q = self.quality_evaluator.evaluate_finding(f, match_res.cites_deployment_evidence)
            quality_list.append(q)

            if match_res.is_match:
                if not matched_gt:
                    matched_gt = True
                    tp_count += 1
                    classification = EvaluationClass.TRUE_POSITIVE
                    rationale = f"Accurately detected ground truth defect for {case_id}. {match_res.rationale}"
                else:
                    duplicate_count += 1
                    classification = EvaluationClass.DUPLICATE
                    rationale = f"Subsequent duplicate comment addressing defect. {match_res.rationale}"
            else:
                sev = (f.reported_severity or "").lower()
                if sev in ("high", "critical", "error", "blocker"):
                    fp_count += 1
                    classification = EvaluationClass.FALSE_POSITIVE
                    rationale = f"Reported non-existent or mischaracterized defect. {match_res.rationale}"
                else:
                    vuf_count += 1
                    classification = EvaluationClass.VALID_UNEXPECTED
                    rationale = f"General code review suggestion. {match_res.rationale}"

            eval_rec = FindingEvaluation(
                id=f"eval-{uuid.uuid4().hex[:12]}",
                finding_id=f.id,
                classification=classification,
                ground_truth_id=gt.id if gt else None,
                cites_deployment_evidence=match_res.cites_deployment_evidence,
                evaluator_type="rule_matcher",
                rationale=rationale,
                evaluated_at=now_str,
            )
            evaluations.append(eval_rec)

        self.eval_repo.save_all(evaluations)

        fn_count = 0 if matched_gt else 1

        mean_spec = sum(q.specificity_score for q in quality_list) / len(quality_list) if quality_list else 0.0
        mean_act = sum(q.actionability_score for q in quality_list) / len(quality_list) if quality_list else 0.0
        mean_ev = sum(q.evidence_score for q in quality_list) / len(quality_list) if quality_list else 0.0

        metric = ScoringCalculator.calculate_metrics(
            tp=tp_count,
            fp=fp_count,
            fn=fn_count,
            vuf=vuf_count,
            duplicates=duplicate_count,
            is_clean_case=False,
            mean_specificity=round(mean_spec, 2),
            mean_actionability=round(mean_act, 2),
            mean_evidence=round(mean_ev, 2),
        )

        score = AttemptScore(
            id=score_id,
            attempt_id=attempt_id,
            tp_count=metric.tp_count,
            fp_count=metric.fp_count,
            fn_count=metric.fn_count,
            vuf_count=metric.vuf_count,
            precision_rate=metric.precision,
            recall_rate=metric.recall,
            f1_metric=metric.f1_score,
            passed_cleanly=metric.passed_cleanly,
            computed_at=now_str,
        )
        return self.score_repo.save(score)

    def evaluate_batch(self, batch_id: str) -> list[AttemptScore]:
        """Evaluate and score all attempts in an execution batch."""
        attempts = self.attempt_repo.list_for_batch(batch_id)
        scores = []
        for att in attempts:
            score = self.evaluate_attempt(att.id)
            scores.append(score)
        return scores
