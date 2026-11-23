"""OpenAI GPT-6.1 Sol / GPT-4o code-review provider adapter."""

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
class OpenAIConfig(ProviderConfig):
    """Configuration specific to OpenAI API."""
    api_url: str = "https://api.openai.com/v1/chat/completions"
    system_prompt: str = SYSTEM_PROMPT
    dry_run: bool = False  # for offline testing without billable API calls


class OpenAIAdapter(BaseProviderAdapter):
    """Adapter for OpenAI models (e.g. gpt-6.1-sol, gpt-6-luna, gpt-4o)."""

    provider_id = "openai"
    display_name = "OpenAI GPT-6.1 Sol"
    default_model = "gpt-6.1-sol"

    def __init__(self, config: Optional[OpenAIConfig] = None, **kwargs):
        cfg = config or OpenAIConfig(
            provider_id=self.provider_id,
            display_name=self.display_name,
            default_model=self.default_model,
            api_key_env_var="OPENAI_API_KEY",
            **kwargs,
        )
        super().__init__(cfg)
        self.openai_config: OpenAIConfig = cfg

    def build_payload(self, context: ReviewContext) -> dict:
        """Construct the standardized OpenAI chat completions payload."""
        from benchmark.cases.context import ContextManager
        prompt_text = ContextManager.format_review_prompt(context)
        return {
            "model": self.openai_config.default_model,
            "temperature": self.openai_config.temperature,
            "max_tokens": self.openai_config.max_tokens,
            "messages": [
                {"role": "system", "content": self.openai_config.system_prompt},
                {"role": "user", "content": prompt_text},
            ],
        }

    def invoke_review(self, context: ReviewContext) -> ProviderRawResult:
        """Send review request to OpenAI API or return deterministic dry-run fixture."""
        if self.openai_config.dry_run:
            return self._invoke_dry_run(context)

        api_key = self.get_api_key()
        payload = self.build_payload(context)
        data = json.dumps(payload).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Proofline-Benchmark-Engine/1.0",
            **self.openai_config.extra_headers,
        }

        req = urllib.request.Request(
            self.openai_config.api_url,
            data=data,
            headers=headers,
            method="POST",
        )

        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.openai_config.timeout_seconds) as resp:
                body = resp.read().decode("utf-8")
                status = resp.status
                duration_ms = int((time.perf_counter() - t0) * 1000)

                parsed = json.loads(body)
                choices = parsed.get("choices", [])
                raw_text = choices[0].get("message", {}).get("content", "") if choices else ""
                usage = parsed.get("usage", {})

                return ProviderRawResult(
                    raw_content=raw_text,
                    http_status=status,
                    external_id=parsed.get("id"),
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens"),
                    duration_ms=duration_ms,
                    model_name=parsed.get("model", self.default_model),
                    finish_reason=choices[0].get("finish_reason") if choices else None,
                    response_headers=dict(resp.headers),
                )
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="replace")
            self.handle_http_error(err.code, err_body, dict(err.headers))
        except urllib.error.URLError as err:
            reason_str = str(err.reason).lower()
            if "timed out" in reason_str or isinstance(err.reason, TimeoutError):
                raise ProviderTransportError(f"OpenAI API request timed out after {self.openai_config.timeout_seconds}s") from err
            raise ProviderTransportError(f"OpenAI API connection error: {err.reason}") from err
        except TimeoutError as err:
            raise ProviderTransportError(f"OpenAI API request timed out after {self.openai_config.timeout_seconds}s") from err

    def _invoke_dry_run(self, context: ReviewContext) -> ProviderRawResult:
        """Simulate OpenAI response for automated offline tests."""
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
            f"## GPT-4o Review: {context.pr_title}\n\n"
            f"### Actionable Findings\n{findings}\n\n"
            "### Recommendation\nAdd comprehensive regression tests and verify deployment environment."
        )
        return ProviderRawResult(
            raw_content=content,
            http_status=200,
            external_id=f"chatcmpl_gpt_{context.case_number}",
            prompt_tokens=310,
            completion_tokens=85,
            duration_ms=60,
            model_name=self.default_model,
            finish_reason="stop",
            execution_mode="dry_run",
        )
