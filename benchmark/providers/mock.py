"""Mock provider adapter for testing, dry-runs, and deterministic validation."""

from benchmark.providers.base import (
    BaseProviderAdapter,
    ProviderFatalError,
    ProviderQuotaError,
    ProviderRawResult,
    ProviderTransportError,
    ReviewContext,
)


class MockProviderAdapter(BaseProviderAdapter):
    """Deterministic mock provider used to test orchestrator lifecycles."""

    def __init__(
        self,
        provider_id: str = "mock-reviewer",
        display_name: str = "Mock AI Reviewer",
        default_model: str = "mock-model-v1",
        mode: str = "success",
    ):
        self.provider_id = provider_id
        self.display_name = display_name
        self.default_model = default_model
        self.mode = mode
        self.calls = 0

    def invoke_review(self, context: ReviewContext) -> ProviderRawResult:
        self.calls += 1

        if self.mode == "quota":
            raise ProviderQuotaError(f"Simulated rate limit for {self.provider_id}")

        if self.mode == "fatal":
            raise ProviderFatalError(f"Simulated fatal error for {self.provider_id}")

        if self.mode == "retry_once":
            if self.calls == 1:
                raise ProviderTransportError(f"Simulated transient error on attempt {self.calls}")

        # Normal successful review output
        return ProviderRawResult(
            raw_content=(
                f"### Mock Review for Case {context.case_number}: {context.pr_title}\n\n"
                f"Inspected diff against baseline {context.base_commit}.\n"
                f"Context condition: {context.context_condition.value}.\n"
                "Result: Analysis completed cleanly."
            ),
            http_status=200,
            external_id=f"mock-rev-{context.case_number}-{self.calls}",
            prompt_tokens=250,
            completion_tokens=60,
            duration_ms=45,
        )
