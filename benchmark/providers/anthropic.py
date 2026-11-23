"""Anthropic Claude code-review provider adapter."""

from dataclasses import dataclass
import json
import time
from typing import Optional
import urllib.error
import urllib.request

from benchmark.domain.enums import ContextCondition
from benchmark.providers.base import (
    BaseProviderAdapter,
    ProviderAuthenticationError,
    ProviderConfig,
    ProviderQuotaError,
    ProviderRawResult,
    ProviderTransportError,
    ReviewContext,
)

SYSTEM_PROMPT = """You are a senior software engineer and principal systems architect performing a rigorous code review on a pull request.
Review the proposed changes against the provided baseline application.
Identify any:
1. Logic bugs or boundary condition oversights.
2. Data integrity defects or regression risks.
3. Operational, configuration, or deployment conflicts (especially when operational context is provided).
4. Performance bottlenecks or scalability hazards.

Format your review clearly with:
- Summary of changes
- Critical issues and findings (naming file and line numbers)
- Recommendations and suggested fixes
"""


@dataclass
class AnthropicConfig(ProviderConfig):
    """Configuration specific to Anthropic API."""
    api_url: str = "https://api.anthropic.com/v1/messages"
    anthropic_version: str = "2023-06-01"
    system_prompt: str = SYSTEM_PROMPT
    dry_run: bool = False  # for offline testing without billable API calls


class AnthropicAdapter(BaseProviderAdapter):
    """Adapter for Anthropic Claude (e.g. claude-3-5-sonnet, claude-3-7-sonnet)."""

    provider_id = "anthropic"
    display_name = "Anthropic Claude"
    default_model = "claude-sonnet-5-5"

    def __init__(self, config: Optional[AnthropicConfig] = None, **kwargs):
        cfg = config or AnthropicConfig(
            provider_id=self.provider_id,
            display_name=self.display_name,
            default_model=self.default_model,
            api_key_env_var="ANTHROPIC_API_KEY",
            **kwargs,
        )
        super().__init__(cfg)
        self.anthropic_config: AnthropicConfig = cfg

    def build_payload(self, context: ReviewContext) -> dict:
        """Construct the standardized Anthropic messages request payload."""
        from benchmark.cases.context import ContextManager
        prompt_text = ContextManager.format_review_prompt(context)
        return {
            "model": self.anthropic_config.default_model,
            "max_tokens": self.anthropic_config.max_tokens,
            "temperature": self.anthropic_config.temperature,
            "system": self.anthropic_config.system_prompt,
            "messages": [
                {"role": "user", "content": prompt_text}
            ],
        }

    def invoke_review(self, context: ReviewContext) -> ProviderRawResult:
        """Send review request to Anthropic API or return deterministic dry-run fixture."""
        if self.anthropic_config.dry_run:
            return self._invoke_dry_run(context)

        api_key = self.get_api_key()
        payload = self.build_payload(context)
        data = json.dumps(payload).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": self.anthropic_config.anthropic_version,
            "User-Agent": "Proofline-Benchmark-Engine/1.0",
            **self.anthropic_config.extra_headers,
        }

        req = urllib.request.Request(
            self.anthropic_config.api_url,
            data=data,
            headers=headers,
            method="POST",
        )

        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.anthropic_config.timeout_seconds) as resp:
                body = resp.read().decode("utf-8")
                status = resp.status
                duration_ms = int((time.perf_counter() - t0) * 1000)

                parsed = json.loads(body)
                content_blocks = parsed.get("content", [])
                raw_text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
                usage = parsed.get("usage", {})

                return ProviderRawResult(
                    raw_content=raw_text,
                    http_status=status,
                    external_id=parsed.get("id"),
                    prompt_tokens=usage.get("input_tokens"),
                    completion_tokens=usage.get("output_tokens"),
                    duration_ms=duration_ms,
                    model_name=parsed.get("model", self.default_model),
                    finish_reason=parsed.get("stop_reason"),
                    response_headers=dict(resp.headers),
                )
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="replace")
            self.handle_http_error(err.code, err_body, dict(err.headers))
        except urllib.error.URLError as err:
            reason_str = str(err.reason).lower()
            if "timed out" in reason_str or isinstance(err.reason, TimeoutError):
                raise ProviderTransportError(f"Anthropic API request timed out after {self.anthropic_config.timeout_seconds}s") from err
            raise ProviderTransportError(f"Anthropic API connection error: {err.reason}") from err
        except TimeoutError as err:
            raise ProviderTransportError(f"Anthropic API request timed out after {self.anthropic_config.timeout_seconds}s") from err

    def _invoke_dry_run(self, context: ReviewContext) -> ProviderRawResult:
        """Simulate Anthropic response for automated offline tests."""
        case_num = context.case_number
        is_snap = context.context_condition == ContextCondition.CODE_AND_SNAPSHOT

        if case_num == 1:
            findings = "- **File:** `reports.py`\n- **Lines:** 45-48\n- **Severity:** critical\n- **Comment:** Cursor pagination query relies on `scheduled_at < ?` without tie-breaker. Multiple deliveries scheduled for the same second will be skipped or duplicated."
        elif case_num == 2:
            findings = "- **File:** `reports.py`\n- **Lines:** 53-56\n- **Severity:** critical\n- **Comment:** Manual CSV formatting using string join without escaping commas or quotes corrupts CSV exports."
        elif case_num == 3:
            findings = "- **File:** `reports.py`\n- **Lines:** 77-85\n- **Severity:** critical\n- **Comment:** Batch processing loop drops remaining queued jobs when total jobs is not a multiple of batch_size."
        elif case_num == 4:
            if is_snap and context.snapshot_content and "elm" in context.snapshot_content.lower():
                findings = "- **File:** `migrations/002_retire_format.sql`\n- **Lines:** 1\n- **Severity:** critical\n- **Comment:** Dropping `legacy_format` column breaks active Elm site workers running revision `workers-17` which still executes `poll_sql` querying this column."
            else:
                findings = "- **File:** `migrations/002_retire_format.sql`\n- **Lines:** 1\n- **Severity:** warning\n- **Comment:** Dropping table column directly without prior deprecation period."
        elif case_num == 5:
            if is_snap and context.snapshot_content and "cedar" in context.snapshot_content.lower():
                findings = "- **File:** `reports.py`\n- **Lines:** 10\n- **Severity:** critical\n- **Comment:** Increasing `EXPORT_BATCH_SIZE` to 50 exceeds Cedar site receiver `max_rows_per_request` limit of 40."
            else:
                findings = "- **File:** `reports.py`\n- **Lines:** 10\n- **Severity:** info\n- **Comment:** Batch size increased to 50; monitor throughput."
        elif case_num == 6:
            if is_snap and context.snapshot_content and "elm" in context.snapshot_content.lower():
                findings = "- **File:** `reports.py`\n- **Lines:** 9\n- **Severity:** critical\n- **Comment:** Renaming `DELIVERY_QUEUE` to 'report-dispatch' starves Elm site workers because Elm only subscribes to 'reports'."
            else:
                findings = "- **File:** `reports.py`\n- **Lines:** 9\n- **Severity:** info\n- **Comment:** Changed delivery queue name."
        elif case_num in (7, 8):
            findings = "Looks good to me! No blocking defects identified in this change. Approved."
        else:
            findings = "- Inspected proposed patch changes against baseline application."

        content = (
            f"## Claude Review: {context.pr_title}\n\n"
            f"### Actionable Findings\n{findings}\n\n"
            "### Recommendation\nVerify boundary conditions and operational environment before deployment."
        )
        return ProviderRawResult(
            raw_content=content,
            http_status=200,
            external_id=f"msg_claude_{context.case_number}",
            prompt_tokens=320,
            completion_tokens=90,
            duration_ms=65,
            model_name=self.default_model,
            finish_reason="end_turn",
            execution_mode="dry_run",
        )
