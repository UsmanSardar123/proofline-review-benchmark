"""OpenAI GPT-4o code-review provider adapter."""

from dataclasses import dataclass
import json
import time
from typing import Optional
import urllib.error
import urllib.request

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
    """Adapter for OpenAI models (e.g. gpt-4o, gpt-4o-mini, o1)."""

    provider_id = "openai"
    display_name = "OpenAI GPT-4o"
    default_model = "gpt-4o"

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
            raise ProviderTransportError(f"OpenAI API connection error: {err.reason}") from err

    def _invoke_dry_run(self, context: ReviewContext) -> ProviderRawResult:
        """Simulate OpenAI response for automated offline tests."""
        findings = f"- In `reports.py`: Analyzed patch diff for Case {context.case_number}."
        if context.snapshot_content:
            findings += "\n- Operational context reviewed: verified deployment environment."

        content = (
            f"## GPT-4o Review: {context.pr_title}\n\n"
            f"### Findings\n{findings}\n\n"
            "### Recommendation\nAdd comprehensive regression tests."
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
        )
