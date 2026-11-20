"""Base interfaces and exceptions for AI code-review providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from benchmark.domain.enums import ContextCondition


class ProviderError(Exception):
    """Base exception for provider invocation failures."""
    pass


class ProviderQuotaError(ProviderError):
    """Raised when provider quota/rate limit is hit (e.g. HTTP 429)."""
    pass


class ProviderTransportError(ProviderError):
    """Raised on transient network/transport errors suitable for auto-retry."""
    pass


class ProviderFatalError(ProviderError):
    """Raised on non-retryable errors (e.g. HTTP 400 or invalid credentials)."""
    pass


@dataclass
class ReviewContext:
    case_id: str
    case_number: int
    pr_title: str
    pr_body: str
    base_commit: str
    head_commit: str
    patch_diff: str
    context_condition: ContextCondition
    snapshot_content: Optional[str] = None


@dataclass
class ProviderRawResult:
    raw_content: str
    http_status: Optional[int] = 200
    external_id: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    duration_ms: Optional[int] = None


class BaseProviderAdapter(ABC):
    """Abstract interface defining the contract for review providers."""

    provider_id: str
    display_name: str
    default_model: str

    @abstractmethod
    def invoke_review(self, context: ReviewContext) -> ProviderRawResult:
        """Trigger review analysis and return raw review output."""
        pass
