"""Base interfaces, configuration, and exception hierarchy for AI review providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import hashlib
import os
import time
from typing import Optional

from benchmark.domain.enums import ContextCondition


class ProviderError(Exception):
    """Base exception for provider invocation failures."""
    pass


class ProviderQuotaError(ProviderError):
    """Raised when provider quota/rate limit is hit (e.g. HTTP 429, credit depletion)."""
    pass


class ProviderTransportError(ProviderError):
    """Raised on transient network/transport errors suitable for auto-retry."""
    pass


class ProviderFatalError(ProviderError):
    """Raised on non-retryable errors (e.g. HTTP 400 Bad Request or malformed schema)."""
    pass


class ProviderAuthenticationError(ProviderFatalError):
    """Raised when credentials are missing or rejected (e.g. HTTP 401, 403)."""
    pass


@dataclass
class ProviderConfig:
    """Standardized configuration options for an AI provider integration."""
    provider_id: str
    display_name: str
    default_model: str
    api_key_env_var: Optional[str] = None
    api_url: Optional[str] = None
    timeout_seconds: float = 30.0
    max_retries: int = 2
    backoff_factor: float = 0.2
    temperature: float = 0.0
    max_tokens: int = 2048
    extra_headers: dict[str, str] = field(default_factory=dict)
    dry_run: bool = False
    # When True, adapters in 'auto' mode may fall back to synthetic fixtures if no
    # credentials/CLI are available. Default False: missing credentials raise.
    allow_fixture_fallback: bool = False


@dataclass
class ReviewContext:
    """Full context provided to an AI code reviewer."""
    case_id: str
    case_number: int
    pr_title: str
    pr_body: str
    base_commit: str
    head_commit: str
    patch_diff: str
    context_condition: ContextCondition
    snapshot_content: Optional[str] = None
    context_hash: str = ""
    provenance: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.context_hash:
            data = f"{self.case_id}:{self.base_commit}:{self.head_commit}:{self.context_condition.value}:{self.patch_diff}:{self.snapshot_content or ''}"
            self.context_hash = hashlib.sha256(data.encode("utf-8")).hexdigest()


@dataclass
class ProviderRawResult:
    """Standardized response container for raw review execution output."""
    raw_content: str
    http_status: Optional[int] = 200
    external_id: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    duration_ms: Optional[int] = None
    model_name: str = ""
    finish_reason: Optional[str] = None
    response_headers: dict = field(default_factory=dict)
    # Provenance of the content: 'live' for genuine reviewer output; 'fixture',
    # 'dry_run' or 'mock' for synthetic offline output.
    execution_mode: str = "live"


class BaseProviderAdapter(ABC):
    """Abstract interface defining standard provider operations, auth, and error handling."""

    provider_id: str
    display_name: str
    default_model: str
    config: ProviderConfig

    def __init__(self, config: Optional[ProviderConfig] = None):
        if config:
            self.config = config
            self.provider_id = config.provider_id
            self.display_name = config.display_name
            self.default_model = config.default_model
        else:
            self.config = ProviderConfig(
                provider_id=getattr(self, "provider_id", "base-provider"),
                display_name=getattr(self, "display_name", "Base Provider"),
                default_model=getattr(self, "default_model", "default-model"),
            )

    def get_api_key(self) -> Optional[str]:
        """Safely retrieve the provider API credential from the environment."""
        if not self.config.api_key_env_var:
            return None
        key = os.environ.get(self.config.api_key_env_var)
        if not key or not key.strip():
            raise ProviderAuthenticationError(
                f"Missing API credential in environment variable: {self.config.api_key_env_var}"
            )
        return key.strip()

    def validate_configuration(self) -> bool:
        """Verify that provider configuration and credentials are valid without billable call."""
        if not self.config.dry_run and self.config.api_key_env_var:
            self.get_api_key()
        return True

    @staticmethod
    def mask_secret(secret: Optional[str]) -> str:
        """Mask credentials for safe audit logging."""
        if not secret:
            return "<none>"
        if len(secret) <= 8:
            return "***"
        return f"{secret[:3]}...{secret[-4:]}"

    def handle_http_error(self, status_code: int, response_text: str, headers: Optional[dict] = None) -> None:
        """Map HTTP error status codes into domain-specific ProviderError exceptions."""
        headers = headers or {}
        lower_body = response_text.lower()

        if status_code == 429 or "rate_limit" in lower_body or "quota" in lower_body:
            raise ProviderQuotaError(f"[{self.provider_id}] Quota/rate limit exceeded (HTTP {status_code}): {response_text}")

        if status_code in (401, 403):
            raise ProviderAuthenticationError(f"[{self.provider_id}] Authentication failed (HTTP {status_code}): {response_text}")

        if status_code in (400, 422):
            raise ProviderFatalError(f"[{self.provider_id}] Invalid request (HTTP {status_code}): {response_text}")

        if status_code in (500, 502, 503, 504):
            raise ProviderTransportError(f"[{self.provider_id}] Gateway/Server error (HTTP {status_code}): {response_text}")

        raise ProviderError(f"[{self.provider_id}] Unexpected HTTP error (HTTP {status_code}): {response_text}")

    def execute_with_retry(self, context: ReviewContext) -> ProviderRawResult:
        """Execute review invocation with automatic exponential backoff on transport errors."""
        retries = 0
        max_retries = self.config.max_retries
        backoff = self.config.backoff_factor

        while True:
            t0 = time.perf_counter()
            try:
                result = self.invoke_review(context)
                if result.duration_ms is None:
                    result.duration_ms = int((time.perf_counter() - t0) * 1000)
                if not result.model_name:
                    result.model_name = self.default_model
                return result
            except ProviderTransportError as err:
                retries += 1
                if retries > max_retries:
                    raise ProviderTransportError(f"Transport retries exhausted ({max_retries}/{max_retries}): {err}") from err
                time.sleep(backoff * (2 ** (retries - 1)))
            # Quota and Fatal errors are immediately propagated without retry

    @abstractmethod
    def invoke_review(self, context: ReviewContext) -> ProviderRawResult:
        """Subclass implementation of actual review request dispatch."""
        pass
