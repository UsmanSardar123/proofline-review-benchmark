"""Finding quality evaluation: specificity, evidence grounding, and actionability."""

from dataclasses import dataclass
import re
from typing import Optional

from benchmark.domain.models import ReviewFinding


@dataclass
class FindingQualityMetrics:
    """Quality and specificity metrics for an individual review finding."""
    has_file_target: bool
    has_line_target: bool
    specificity_score: float  # 0.0 to 1.0
    evidence_score: float     # 0.0 to 1.0
    actionability_score: float  # 0.0 to 1.0
    severity_weight: float    # 0.2 to 1.0 based on reported severity
    overall_quality: float    # 0.0 to 1.0 composite


class FindingQualityEvaluator:
    """Evaluates the structural and empirical quality of AI review comments."""

    ACTION_KEYWORDS = [
        "suggest", "recommend", "consider", "replace", "fix", "instead",
        "should", "add", "change", "use", "update", "verify", "remove"
    ]

    SEVERITY_WEIGHTS = {
        "critical": 1.0,
        "high": 1.0,
        "severe": 1.0,
        "error": 0.8,
        "blocker": 1.0,
        "warning": 0.5,
        "warn": 0.5,
        "medium": 0.5,
        "info": 0.2,
        "low": 0.2,
        "note": 0.2,
    }

    def evaluate_finding(
        self,
        finding: ReviewFinding,
        cites_deployment_evidence: bool = False,
    ) -> FindingQualityMetrics:
        """Calculate quality scores for a given review finding."""
        has_file = bool(finding.file_path and finding.file_path.strip())
        has_line = finding.line_start is not None

        # Specificity: line + file = 1.0, file only = 0.6, neither = 0.2
        if has_file and has_line:
            specificity = 1.0
        elif has_file:
            specificity = 0.6
        else:
            specificity = 0.2

        # Evidence Grounding
        evidence = 1.0 if cites_deployment_evidence else 0.0

        # Actionability: presence of concrete recommendations or code snippets
        text = f"{finding.summary} {finding.raw_comment_slice or ''}".lower()
        has_code_snippet = "```" in text or "`" in text
        action_match_count = sum(1 for kw in self.ACTION_KEYWORDS if re.search(rf"\b{kw}\b", text))

        actionability = 0.2
        if has_code_snippet and action_match_count >= 1:
            actionability = 1.0
        elif has_code_snippet or action_match_count >= 2:
            actionability = 0.8
        elif action_match_count == 1:
            actionability = 0.5

        # Severity Weighting
        sev = (finding.reported_severity or "warning").lower()
        sev_weight = self.SEVERITY_WEIGHTS.get(sev, 0.5)

        # Composite quality score
        composite = (
            (specificity * 0.45) +
            (actionability * 0.35) +
            (evidence * 0.20)
        )

        return FindingQualityMetrics(
            has_file_target=has_file,
            has_line_target=has_line,
            specificity_score=round(specificity, 2),
            evidence_score=round(evidence, 2),
            actionability_score=round(actionability, 2),
            severity_weight=round(sev_weight, 2),
            overall_quality=round(composite, 2),
        )
