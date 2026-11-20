"""Scoring, evaluation, calibration, and held-out partition package."""

from benchmark.scoring.calibration import (
    CalibrationProfile,
    CalibrationRegistry,
    LENIENT_PROFILE,
    STANDARD_PROFILE,
    STRICT_PROFILE,
)
from benchmark.scoring.heldout import GeneralizationReport, PartitionManager
from benchmark.scoring.matcher import FindingMatcher, MatchingConfig, MatchResult
from benchmark.scoring.metrics import MetricSummary, ScoringCalculator
from benchmark.scoring.quality import FindingQualityEvaluator, FindingQualityMetrics
from benchmark.scoring.service import STANDARD_GROUND_TRUTHS, ScoringService

__all__ = [
    "ScoringService",
    "STANDARD_GROUND_TRUTHS",
    "CalibrationProfile",
    "CalibrationRegistry",
    "STANDARD_PROFILE",
    "STRICT_PROFILE",
    "LENIENT_PROFILE",
    "FindingMatcher",
    "MatchingConfig",
    "MatchResult",
    "FindingQualityEvaluator",
    "FindingQualityMetrics",
    "MetricSummary",
    "ScoringCalculator",
    "GeneralizationReport",
    "PartitionManager",
]
