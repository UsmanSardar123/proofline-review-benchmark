"""Dataset partitioning and held-out evaluation isolation."""

from dataclasses import dataclass
from typing import Optional

from benchmark.domain.models import AttemptScore
from benchmark.scoring.metrics import ScoringCalculator


@dataclass
class GeneralizationReport:
    """Measures out-of-sample generalization between calibration and held-out test partitions."""
    calibration_count: int
    heldout_count: int
    calibration_f1: float
    heldout_f1: float
    generalization_delta: float  # heldout_f1 - calibration_f1
    calibration_precision: float
    heldout_precision: float
    calibration_recall: float
    heldout_recall: float
    is_overfitted: bool


class PartitionManager:
    """Manages strict segregation between calibration cases and held-out evaluation cases."""

    # Calibration set: Core logic, integrity, and benign index
    CALIBRATION_CASES = ["case-01", "case-02", "case-03", "case-07"]

    # Held-Out evaluation set: Complex operational deployment conflicts and contract changes
    HELDOUT_CASES = ["case-04", "case-05", "case-06", "case-08"]

    @classmethod
    def get_calibration_case_numbers(cls) -> list[int]:
        return [int(c.replace("case-", "")) for c in cls.CALIBRATION_CASES]

    @classmethod
    def get_heldout_case_numbers(cls) -> list[int]:
        return [int(c.replace("case-", "")) for c in cls.HELDOUT_CASES]

    @classmethod
    def verify_no_leakage(cls, evaluated_cases: list[str]) -> bool:
        """Verify that calibration runs do not contain held-out evaluation cases."""
        leakage = set(evaluated_cases).intersection(set(cls.HELDOUT_CASES))
        if leakage:
            raise ValueError(f"Anti-contamination violation: held-out cases leaked into calibration: {sorted(leakage)}")
        return True

    @classmethod
    def evaluate_generalization(
        cls,
        calibration_scores: list[AttemptScore],
        heldout_scores: list[AttemptScore],
    ) -> GeneralizationReport:
        """Compare performance across calibration vs held-out partitions to measure generalization."""
        cal_rollup = ScoringCalculator.calculate_aggregate_rollup(calibration_scores)
        held_rollup = ScoringCalculator.calculate_aggregate_rollup(heldout_scores)

        cal_f1 = cal_rollup["micro_f1"]
        held_f1 = held_rollup["micro_f1"]
        delta = round(held_f1 - cal_f1, 4)

        # Overfitting can only be judged when BOTH partitions have scored attempts.
        # With an empty partition the missing F1 defaults to 0.0, which previously
        # produced a false overfitting alert.
        both_present = cal_rollup["count"] > 0 and held_rollup["count"] > 0
        is_overfitted = both_present and (cal_f1 - held_f1) > 0.25

        return GeneralizationReport(
            calibration_count=cal_rollup["count"],
            heldout_count=held_rollup["count"],
            calibration_f1=cal_f1,
            heldout_f1=held_f1,
            generalization_delta=delta,
            calibration_precision=cal_rollup["micro_precision"],
            heldout_precision=held_rollup["micro_precision"],
            calibration_recall=cal_rollup["micro_recall"],
            heldout_recall=held_rollup["micro_recall"],
            is_overfitted=is_overfitted,
        )
