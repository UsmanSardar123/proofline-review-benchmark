"""Evaluation metric calculations: precision, recall, F1, and aggregate rollups."""

from dataclasses import dataclass
from typing import Optional

from benchmark.domain.models import AttemptScore


@dataclass
class MetricSummary:
    """Consolidated precision, recall, and F1 metrics with zero-denominator handling."""
    tp_count: int
    fp_count: int
    fn_count: int
    vuf_count: int
    duplicate_count: int
    precision: float
    recall: float
    f1_score: float
    passed_cleanly: bool
    mean_specificity: float = 0.0
    mean_actionability: float = 0.0
    mean_evidence: float = 0.0


class ScoringCalculator:
    """Calculates standardized benchmark metrics with deterministic zero-denominator handling."""

    @staticmethod
    def calculate_metrics(
        tp: int,
        fp: int,
        fn: int,
        vuf: int = 0,
        duplicates: int = 0,
        is_clean_case: bool = False,
        mean_specificity: float = 0.0,
        mean_actionability: float = 0.0,
        mean_evidence: float = 0.0,
    ) -> MetricSummary:
        """Calculate precision, recall, and F1 handling edge cases and benign PRs."""
        if is_clean_case:
            # On benign PRs (Cases 07 & 08):
            # A clean review (0 False Positives) is a perfect outcome: P=1.0, R=1.0, F1=1.0
            # A false alarm (FP > 0) is a defect penalty: P=0.0, R=1.0, F1=0.0
            passed_cleanly = (fp == 0)
            precision = 1.0 if passed_cleanly else 0.0
            recall = 1.0 if passed_cleanly else 0.0
            f1 = 1.0 if passed_cleanly else 0.0

            return MetricSummary(
                tp_count=0,
                fp_count=fp,
                fn_count=0,
                vuf_count=vuf,
                duplicate_count=duplicates,
                precision=precision,
                recall=recall,
                f1_score=f1,
                passed_cleanly=passed_cleanly,
                mean_specificity=mean_specificity,
                mean_actionability=mean_actionability,
                mean_evidence=mean_evidence,
            )

        # Defect PRs (Cases 01–06):
        precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        passed_cleanly = (tp > 0 and fp == 0)

        return MetricSummary(
            tp_count=tp,
            fp_count=fp,
            fn_count=fn,
            vuf_count=vuf,
            duplicate_count=duplicates,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1, 4),
            passed_cleanly=passed_cleanly,
            mean_specificity=mean_specificity,
            mean_actionability=mean_actionability,
            mean_evidence=mean_evidence,
        )

    @staticmethod
    def calculate_aggregate_rollup(scores: list[AttemptScore]) -> dict:
        """Compute micro-average and macro-average metrics across an attempt score list."""
        if not scores:
            return {
                "count": 0,
                "tp_total": 0,
                "fp_total": 0,
                "fn_total": 0,
                "vuf_total": 0,
                "clean_passes": 0,
                "micro_precision": 0.0,
                "micro_recall": 0.0,
                "micro_f1": 0.0,
                "macro_f1": 0.0,
            }

        total_tp = sum(s.tp_count for s in scores)
        total_fp = sum(s.fp_count for s in scores)
        total_fn = sum(s.fn_count for s in scores)
        total_vuf = sum(s.vuf_count for s in scores)
        clean_passes = sum(1 for s in scores if s.passed_cleanly)

        micro_p = (total_tp / (total_tp + total_fp)) if (total_tp + total_fp) > 0 else (1.0 if clean_passes > 0 else 0.0)
        micro_r = (total_tp / (total_tp + total_fn)) if (total_tp + total_fn) > 0 else (1.0 if clean_passes > 0 else 0.0)
        micro_f1 = (2 * micro_p * micro_r / (micro_p + micro_r)) if (micro_p + micro_r) > 0 else 0.0

        valid_f1s = [s.f1_metric for s in scores if s.f1_metric is not None]
        macro_f1 = sum(valid_f1s) / len(valid_f1s) if valid_f1s else 0.0

        return {
            "count": len(scores),
            "tp_total": total_tp,
            "fp_total": total_fp,
            "fn_total": total_fn,
            "vuf_total": total_vuf,
            "clean_passes": clean_passes,
            "micro_precision": round(micro_p, 4),
            "micro_recall": round(micro_r, 4),
            "micro_f1": round(micro_f1, 4),
            "macro_f1": round(macro_f1, 4),
        }
