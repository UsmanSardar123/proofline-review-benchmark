"""Context and deployment snapshot management for review conditions."""

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Optional

from benchmark.cases.registry import CaseRegistry
from benchmark.config import PROJECT_ROOT
from benchmark.domain.enums import ContextCondition
from benchmark.providers.base import ReviewContext


class ContextSafetyError(RuntimeError):
    """Raised when context contains forbidden benchmark answers or evaluation data."""
    pass


class ContextManager:
    """Prepares and validates review context under CODE_ONLY and CODE_AND_SNAPSHOT conditions."""

    FORBIDDEN_KEYWORDS = [
        "ground_truth",
        "answer_key",
        "expected_finding",
        "grader_note",
        "rubric",
        "GT-0",
    ]

    def __init__(self, registry: Optional[CaseRegistry] = None, repo_root: Optional[Path] = None):
        self.registry = registry or CaseRegistry()
        self.repo_root = repo_root or PROJECT_ROOT

    def verify_context_safety(self, text: str) -> tuple[bool, list[str]]:
        """Assert that no answer keys or internal evaluation rubric texts leak into context."""
        violations = []
        lower = text.lower()
        for kw in self.FORBIDDEN_KEYWORDS:
            if kw.lower() in lower:
                violations.append(f"Forbidden evaluation token leaked in review context: {kw}")
        return len(violations) == 0, violations

    def build_context(
        self,
        case_number: int,
        condition: ContextCondition,
        base_commit: Optional[str] = None,
        head_commit: Optional[str] = None,
        patch_diff: Optional[str] = None,
    ) -> ReviewContext:
        """Construct a standardized, provenance-tracked ReviewContext for a benchmark case."""
        case = self.registry.get_case(case_number)

        # Resolve diff
        if patch_diff is None:
            patch_path = self.repo_root / case.patch_relpath
            patch_diff = patch_path.read_text(encoding="utf-8") if patch_path.is_file() else ""

        # Resolve snapshot based on condition
        snapshot_content = None
        if condition == ContextCondition.CODE_AND_SNAPSHOT and case.has_deployment_snapshot:
            snapshot_content = case.snapshot_content

        base_ref = base_commit or case.baseline_commit
        head_ref = head_commit or case.target_commit

        # Provenance audit metadata
        provenance = {
            "case_id": case.id,
            "case_number": case.case_number,
            "condition": condition.value,
            "base_commit": base_ref,
            "head_commit": head_ref,
            "patch_path": case.patch_relpath,
            "has_snapshot": snapshot_content is not None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Calculate reproducible hash of all input data
        raw_payload = f"{case.id}:{base_ref}:{head_ref}:{condition.value}:{patch_diff}:{snapshot_content or ''}"
        context_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

        context = ReviewContext(
            case_id=case.id,
            case_number=case.case_number,
            pr_title=case.title,
            pr_body=case.pr_description,
            base_commit=base_ref,
            head_commit=head_ref,
            patch_diff=patch_diff,
            context_condition=condition,
            snapshot_content=snapshot_content,
            context_hash=context_hash,
            provenance=provenance,
        )

        # Enforce safety check on formatted prompt
        prompt = self.format_review_prompt(context)
        is_safe, violations = self.verify_context_safety(prompt)
        if not is_safe:
            raise ContextSafetyError(f"Review context safety violation: {violations}")

        return context

    @staticmethod
    def format_review_prompt(context: ReviewContext, custom_instructions: Optional[str] = None) -> str:
        """Generate the standardized prompt presented to AI code reviewers."""
        sections = [
            f"# Pull Request Review: {context.pr_title}\n",
            "## Description",
            context.pr_body.strip(),
        ]

        if context.context_condition == ContextCondition.CODE_AND_SNAPSHOT and context.snapshot_content:
            sections.extend([
                "\n## Operational & Deployment Context",
                context.snapshot_content.strip(),
            ])

        sections.extend([
            "\n## Proposed Code Changes (Git Diff)",
            "```diff",
            context.patch_diff.strip(),
            "```",
        ])

        if custom_instructions:
            sections.extend([
                "\n## Instructions",
                custom_instructions.strip(),
            ])
        else:
            sections.extend([
                "\n## Instructions",
                "Review the proposed changes above against the application baseline.",
                "Identify any logic bugs, data integrity issues, regressions, operational risks,",
                "or deployment conflicts. State clearly which file and line are affected and explain the issue.",
            ])

        return "\n".join(sections)
