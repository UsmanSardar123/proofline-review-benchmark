"""Manual and web-based AI code review provider adapter."""

from typing import Optional

from benchmark.domain.enums import ContextCondition
from benchmark.providers.base import (
    BaseProviderAdapter,
    ProviderConfig,
    ProviderFatalError,
    ProviderRawResult,
    ReviewContext,
)


class ManualProviderAdapter(BaseProviderAdapter):
    """Adapter representing manual or web-imported AI code reviewers.

    Supports ChatGPT Web, Claude.ai Web, Proofline PR reviews, and custom manual inputs
    without requiring third-party API keys or incurring external API costs.
    """

    KNOWN_MODELS = {
        "chatgpt-web": ("ChatGPT Web (GPT-4o)", "gpt-4o"),
        "claude-web": ("Claude.ai Web (Claude 3.5 Sonnet)", "claude-3-5-sonnet"),
        "proofline": ("Proofline Hosted PR Reviewer", "proofline-pr"),
        "greptile": ("Greptile Reviewer", "greptile-v1"),
        "manual": ("Manual Code Reviewer", "manual-v1"),
    }

    def __init__(
        self,
        provider_id: str = "manual",
        display_name: Optional[str] = None,
        default_model: Optional[str] = None,
        config: Optional[ProviderConfig] = None,
        dry_run: bool = False,
        **kwargs,
    ):
        p_id = provider_id.lower()
        known_display, known_model = self.KNOWN_MODELS.get(
            p_id, (display_name or p_id.replace("-", " ").title(), default_model or "web-chat")
        )
        cfg = config or ProviderConfig(
            provider_id=p_id,
            display_name=display_name or known_display,
            default_model=default_model or known_model,
            dry_run=dry_run,
        )
        super().__init__(cfg)
        self.dry_run = dry_run

    def invoke_review(self, context: ReviewContext) -> ProviderRawResult:
        """Execute review dispatch.

        Manual reviews are captured externally and ingested via 'benchmark ingest'.
        In dry-run mode, returns a deterministic dry-run fixture for automated testing.
        """
        if self.dry_run:
            return self._invoke_dry_run(context)

        raise ProviderFatalError(
            f"Provider '{self.provider_id}' is a manual reviewer. "
            f"Generate prompt with 'benchmark prompt --case {context.case_number}' "
            f"and import the review using 'benchmark ingest'."
        )

    def _invoke_dry_run(self, context: ReviewContext) -> ProviderRawResult:
        """Deterministic dry-run fixture for manual provider testing."""
        case_num = context.case_number
        is_snap = context.context_condition == ContextCondition.CODE_AND_SNAPSHOT

        if case_num == 1:
            raw = (
                "### Review for Case 1: Cursor pagination bug\n\n"
                "- File: `reports.py:42-50`\n"
                "- Severity: `error`\n"
                "- Comment: Cursor pagination ordered by scheduled_at without tie-breaker breaks when multiple jobs share the same timestamp. Add an opaque tie-breaker column.\n"
            )
        elif case_num == 2:
            raw = (
                "### Review for Case 2: Stream export\n\n"
                "- File: `reports.py:50-57`\n"
                "- Severity: `error`\n"
                "- Comment: Manual CSV concatenation without escaping commas or quotes corrupts output. Use csv.writer with proper delimiter.\n"
            )
        elif case_num == 3:
            raw = (
                "### Review for Case 3: Batch deliveries\n\n"
                "- File: `reports.py:73-90`\n"
                "- Severity: `error`\n"
                "- Comment: Batch loop with range drops remaining unprocessed jobs when remainder exists. Handle remainder batch.\n"
            )
        elif case_num == 4:
            if is_snap:
                raw = (
                    "### Review for Case 4: Retire format column\n\n"
                    "- File: `migrations/002_retire_format.sql:1`\n"
                    "- Severity: `error`\n"
                    "- Comment: Dropping legacy_format column breaks active Elm site workers running older workers-17 revision polling that column from inventory-204.\n"
                )
            else:
                raw = "### Review for Case 4\n\nNo operational snapshot provided. Migration looks syntactically valid."
        elif case_num == 5:
            if is_snap:
                raw = (
                    "### Review for Case 5: Export batch size\n\n"
                    "- File: `reports.py:10`\n"
                    "- Severity: `error`\n"
                    "- Comment: Increasing EXPORT_BATCH_SIZE exceeds Cedar site receiver max_rows_per_request limit of 40 in archive-318. Receiver will reject oversized batches.\n"
                )
            else:
                raw = "### Review for Case 5\n\nBatch size change looks plausible."
        elif case_num == 6:
            if is_snap:
                raw = (
                    "### Review for Case 6: Delivery queue\n\n"
                    "- File: `reports.py:9`\n"
                    "- Severity: `error`\n"
                    "- Comment: Switching DELIVERY_QUEUE to report-dispatch leaves Elm site workers starved as they only subscribe to reports queue per subscriptions-416.\n"
                )
            else:
                raw = "### Review for Case 6\n\nQueue name updated."
        elif case_num in (7, 8):
            raw = f"### Review for Case {case_num}: Clean change\n\nCode change looks sound and well-structured. No defects detected. Approved."
        else:
            raw = f"### Review for Case {case_num}\n\nReview completed."

        return ProviderRawResult(
            raw_content=raw,
            http_status=200,
            model_name=self.default_model,
            prompt_tokens=350,
            completion_tokens=90,
            duration_ms=45,
            execution_mode="dry_run",
        )
