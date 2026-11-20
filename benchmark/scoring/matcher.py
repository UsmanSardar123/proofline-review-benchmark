"""Deterministic finding matcher linking review findings to ground truth defects."""

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Optional

from benchmark.domain.models import GroundTruthDefect, ReviewFinding


@dataclass
class MatchResult:
    """Result of comparing a single review finding against a ground truth defect."""
    is_match: bool
    location_matched: bool
    semantic_matched: bool
    cites_deployment_evidence: bool
    location_score: float = 0.0
    semantic_score: float = 0.0
    overall_confidence: float = 0.0
    rationale: str = ""


@dataclass
class MatchingConfig:
    """Configurable matching parameters used by FindingMatcher."""
    line_tolerance: int = 5
    require_file_match: bool = True
    min_keyword_matches: int = 1
    semantic_weight: float = 0.6
    location_weight: float = 0.4
    match_threshold: float = 0.45


class FindingMatcher:
    """Evaluates whether an extracted review finding corresponds to a ground truth defect."""

    def __init__(self, config: Optional[MatchingConfig] = None):
        self.config = config or MatchingConfig()

    @staticmethod
    def parse_line_range(line_str: Optional[str]) -> Optional[tuple[int, int]]:
        """Parse target lines string (e.g. '42-50' or '10') into (start, end) tuple."""
        if not line_str or not line_str.strip():
            return None
        parts = line_str.strip().split("-")
        try:
            if len(parts) == 1:
                val = int(parts[0])
                return (val, val)
            return (int(parts[0]), int(parts[1]))
        except ValueError:
            return None

    @staticmethod
    def normalize_path(path_str: Optional[str]) -> str:
        """Normalize file paths across Windows/POSIX separators."""
        if not path_str:
            return ""
        return str(Path(path_str)).replace("\\", "/").lower()

    def evaluate_location_match(
        self,
        finding: ReviewFinding,
        defect: GroundTruthDefect,
    ) -> tuple[bool, float]:
        """Check if finding file and line coordinates match ground truth within tolerance."""
        if not defect.target_file:
            return True, 1.0

        finding_file = self.normalize_path(finding.file_path)
        target_file = self.normalize_path(defect.target_file)

        # File path matching
        file_matched = False
        if not finding_file:
            # File omitted in finding: partial credit if text mentions file
            file_matched = False
        elif target_file in finding_file or finding_file in target_file:
            file_matched = True

        if not file_matched and self.config.require_file_match and finding_file:
            return False, 0.0

        # Line range matching
        target_range = self.parse_line_range(defect.target_lines)
        if not target_range or finding.line_start is None:
            # If no line numbers available, accept file match with moderate score
            score = 0.6 if file_matched else 0.2
            return file_matched, score

        t_start, t_end = target_range
        tol = self.config.line_tolerance
        window_start = max(1, t_start - tol)
        window_end = t_end + tol

        f_start = finding.line_start
        f_end = finding.line_end or f_start

        # Check line overlap or proximity
        lines_overlap = not (f_end < window_start or f_start > window_end)
        if lines_overlap:
            exact_overlap = not (f_end < t_start or f_start > t_end)
            score = 1.0 if exact_overlap else 0.8
            return True, score

        # Line was specified but outside tolerance
        return False, 0.3 if file_matched else 0.0

    def evaluate_semantic_match(
        self,
        finding: ReviewFinding,
        detection_keywords: list[str],
        evidence_keywords: list[str],
    ) -> tuple[bool, float, bool]:
        """Check if finding content contains relevant defect keywords and citations."""
        text_corpus = f"{finding.summary} {finding.raw_comment_slice or ''}".lower()

        if not detection_keywords:
            return True, 1.0, False

        matched_kws = [kw for kw in detection_keywords if kw.lower() in text_corpus]
        cites_evidence = any(ekw.lower() in text_corpus for ekw in evidence_keywords) if evidence_keywords else False

        match_count = len(matched_kws)
        is_semantic_match = match_count >= self.config.min_keyword_matches

        semantic_score = min(1.0, match_count / max(1, min(len(detection_keywords), 3)))
        return is_semantic_match, semantic_score, cites_evidence

    def match(
        self,
        finding: ReviewFinding,
        defect: GroundTruthDefect,
        detection_keywords: list[str],
        evidence_keywords: list[str],
    ) -> MatchResult:
        """Perform comprehensive matching combining location, semantics, and evidence."""
        loc_matched, loc_score = self.evaluate_location_match(finding, defect)
        sem_matched, sem_score, cites_evidence = self.evaluate_semantic_match(
            finding, detection_keywords, evidence_keywords
        )

        overall_confidence = (
            (loc_score * self.config.location_weight) +
            (sem_score * self.config.semantic_weight)
        )

        is_match = (
            (loc_matched or sem_matched) and
            overall_confidence >= self.config.match_threshold and
            (sem_matched or not detection_keywords)
        )

        rationale = (
            f"Confidence: {overall_confidence:.2f} (loc={loc_score:.2f}, sem={sem_score:.2f}). "
            f"LocMatched={loc_matched}, SemMatched={sem_matched}."
        )

        return MatchResult(
            is_match=is_match,
            location_matched=loc_matched,
            semantic_matched=sem_matched,
            cites_deployment_evidence=cites_evidence,
            location_score=loc_score,
            semantic_score=sem_score,
            overall_confidence=round(overall_confidence, 4),
            rationale=rationale,
        )
