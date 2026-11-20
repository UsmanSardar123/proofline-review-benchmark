"""Scoring service and ground truth evaluation for review findings."""

from datetime import datetime, timezone
import re
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

    def __init__(self, db):
        self.db = db
        self.gt_repo = GroundTruthRepository(db)
        self.case_repo = CaseRepository(db)
        self.attempt_repo = AttemptRepository(db)
        self.finding_repo = FindingRepository(db)
        self.eval_repo = EvaluationRepository(db)
        self.score_repo = AttemptScoreRepository(db)

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

            for f in findings:
                sev = (f.reported_severity or "").lower()
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

            passed_cleanly = (fp_count == 0)
            precision = 1.0 if passed_cleanly else 0.0
            recall = 1.0 if passed_cleanly else 0.0
            f1 = 1.0 if passed_cleanly else 0.0

            score = AttemptScore(
                id=score_id,
                attempt_id=attempt_id,
                tp_count=0,
                fp_count=fp_count,
                fn_count=0,
                vuf_count=vuf_count,
                precision_rate=precision,
                recall_rate=recall,
                f1_metric=f1,
                passed_cleanly=passed_cleanly,
                computed_at=now_str,
            )
            return self.score_repo.save(score)

        # Cases 01-06: Changes containing genuine defects
        target_file = meta["target_file"] if meta else ""
        detection_keywords = meta.get("detection_keywords", []) if meta else []
        evidence_keywords = meta.get("evidence_keywords", []) if meta else []

        tp_count = 0
        fp_count = 0
        fn_count = 0
        vuf_count = 0
        matched_gt = False
        evaluations = []

        for f in findings:
            text_to_check = f"{f.summary} {f.raw_comment_slice or ''}".lower()
            file_match = not target_file or not f.file_path or (target_file.lower() in f.file_path.lower())
            
            # Check for keyword match
            has_keyword = any(kw.lower() in text_to_check for kw in detection_keywords)
            
            # Check if this finding detects the ground truth defect
            if file_match and has_keyword:
                cites_evidence = any(ekw.lower() in text_to_check for ekw in evidence_keywords)
                if not matched_gt:
                    matched_gt = True
                    tp_count += 1
                    classification = EvaluationClass.TRUE_POSITIVE
                    rationale = f"Accurately detected ground truth defect for {case_id}"
                else:
                    classification = EvaluationClass.DUPLICATE
                    rationale = "Subsequent comment addressing the same defect"
            else:
                cites_evidence = False
                sev = (f.reported_severity or "").lower()
                if sev in ("high", "critical", "error", "blocker"):
                    fp_count += 1
                    classification = EvaluationClass.FALSE_POSITIVE
                    rationale = "Reported non-existent or mischaracterized defect"
                else:
                    vuf_count += 1
                    classification = EvaluationClass.VALID_UNEXPECTED
                    rationale = "General code review suggestion"

            eval_rec = FindingEvaluation(
                id=f"eval-{uuid.uuid4().hex[:12]}",
                finding_id=f.id,
                classification=classification,
                ground_truth_id=gt.id if gt else None,
                cites_deployment_evidence=cites_evidence,
                evaluator_type="rule_matcher",
                rationale=rationale,
                evaluated_at=now_str,
            )
            evaluations.append(eval_rec)

        self.eval_repo.save_all(evaluations)

        if not matched_gt:
            fn_count = 1

        precision = (tp_count / (tp_count + fp_count)) if (tp_count + fp_count) > 0 else 0.0
        recall = (tp_count / (tp_count + fn_count)) if (tp_count + fn_count) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        passed_cleanly = (tp_count > 0 and fp_count == 0)

        score = AttemptScore(
            id=score_id,
            attempt_id=attempt_id,
            tp_count=tp_count,
            fp_count=fp_count,
            fn_count=fn_count,
            vuf_count=vuf_count,
            precision_rate=round(precision, 4),
            recall_rate=round(recall, 4),
            f1_metric=round(f1, 4),
            passed_cleanly=passed_cleanly,
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
